import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location("native_" + name, ROOT / "packaging" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class NativePackageTest(unittest.TestCase):
    def test_debian_payload_has_config_protection_and_valid_hooks(self):
        builder = module("build_packages")
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            output = work / "out"
            output.mkdir()
            with patch.object(builder.subprocess, "run"):
                builder.deb(work, output)
            control = work / "payload/DEBIAN"
            self.assertEqual((control / "conffiles").read_text(), "/etc/open-fatshield/config.json\n")
            self.assertIn("Architecture: all", (control / "control").read_text())
            for name in ("preinst", "postinst", "prerm", "postrm"):
                subprocess.run(["sh", "-n", str(control / name)], check=True)
                self.assertEqual((control / name).stat().st_mode & 0o777, 0o755)
            self.assertTrue((work / "payload/usr/lib/open-fatshield/package-hooks.py").exists())
            self.assertFalse(list((work / "payload").rglob("*.ko")))

    def test_missing_headers_register_sources_without_claiming_module_built(self):
        hooks = module("native-hooks")
        with patch.object(hooks, "systemd_running", return_value=False), \
             patch.object(hooks, "versions", return_value=[]), \
             patch.object(hooks.Path, "is_file", return_value=False), \
             patch.object(hooks, "run") as commands, patch("builtins.print") as printed:
            hooks.configure()
        self.assertEqual(commands.call_count, 1)
        self.assertEqual(commands.call_args.args[:2], ("dkms", "add"))
        self.assertIn("headers", str(printed.call_args))

    def test_upgrade_restores_running_service_without_enabling_at_boot(self):
        hooks = module("native-hooks")
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(hooks, "MARKER", Path(directory) / "upgrade.json"), \
             patch.object(hooks, "systemd_running", return_value=True), \
             patch.object(hooks, "run", return_value=subprocess.CompletedProcess([], 0)) as commands:
            hooks.prepare()
            self.assertEqual(hooks.MARKER.stat().st_mode & 0o777, 0o600)
            hooks.resume()
            self.assertFalse(hooks.MARKER.exists())
            calls = [c.args for c in commands.call_args_list]
            self.assertIn(("systemctl", "stop", "open-fatshield.service"), calls)
            self.assertIn(("systemctl", "start", "open-fatshield.service"), calls)
            self.assertFalse(any("enable" in c for c in calls))

    def test_failed_new_module_build_does_not_remove_old_registration(self):
        hooks = module("native-hooks")
        def run(*args, **kwargs):
            if args[:2] == ("dkms", "build"):
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0)
        with patch.object(hooks, "systemd_running", return_value=False), \
             patch.object(hooks, "versions", return_value=["older"]), \
             patch.object(hooks.Path, "is_file", return_value=True), \
             patch.object(hooks, "run", side_effect=run) as commands:
            with self.assertRaises(subprocess.CalledProcessError):
                hooks.configure()
        self.assertFalse(any(c.args[:2] == ("dkms", "remove") for c in commands.call_args_list))
