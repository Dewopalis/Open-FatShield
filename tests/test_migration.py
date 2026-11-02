import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def installer_module():
    spec = importlib.util.spec_from_file_location("migration_installer", ROOT / "packaging/install.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    return installer


class MigrationTest(unittest.TestCase):
    def test_saved_pairing_configuration_and_fault_guard_are_preserved(self):
        installer = installer_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"etc/shield-controller/config.json": '{"interface":"wlan7"}',
                     "var/lib/shield-controller/network.json": '{"saved":"pairing"}',
                     "run/shield-controller/kernel-fault": ""}
            for name, value in files.items():
                source = root / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(value)
            installer.migrate_legacy_files(root)
            for name, value in files.items():
                self.assertEqual((root / name).read_text(), value)  # Legacy backup remains.
                self.assertEqual((root / name.replace("shield-controller", "open-fatshield")).read_text(), value)
            state = root / "var/lib/open-fatshield"
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)
            self.assertEqual((state / "network.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / "run/open-fatshield").stat().st_mode & 0o777, 0o755)

    def test_existing_new_pairing_is_never_overwritten(self):
        installer = installer_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("shield-controller", "old"), ("open-fatshield", "new")):
                path = root / "var/lib" / name / "network.json"
                path.parent.mkdir(parents=True)
                path.write_text(value)
            installer.migrate_legacy_files(root)
            self.assertEqual((root / "var/lib/open-fatshield/network.json").read_text(), "new")

    def test_legacy_cleanup_keeps_state_and_new_installation(self):
        installer = installer_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in installer.FILES.values():
                new = root / path.lstrip("/")
                new.parent.mkdir(parents=True, exist_ok=True)
                new.write_text("new")
                old = root / path.lstrip("/").replace("open-fatshield", "shield-controller")
                old.write_text("legacy")
            saved = root / "var/lib/shield-controller/network.json"
            saved.parent.mkdir(parents=True)
            saved.write_text("saved")
            installer.remove_legacy_files(root)
            for path in installer.FILES.values():
                self.assertTrue((root / path.lstrip("/")).exists())
                self.assertFalse((root / path.lstrip("/").replace("open-fatshield", "shield-controller")).exists())
            self.assertEqual(saved.read_text(), "saved")

    def test_only_installed_legacy_desktop_commands_are_terminated(self):
        installer = installer_module()
        self.assertTrue(installer.is_legacy_desktop(["python3", "/usr/bin/shield-controller", "agent"]))
        self.assertTrue(installer.is_legacy_desktop(["/usr/bin/shield-controller", "tray"]))
        for args in (["python3", "/usr/bin/open-fatshield", "agent"],
                     ["/usr/bin/shield-controller", "status"], ["/tmp/shield-controller", "gui"],
                     ["other", "--text", "/usr/bin/shield-controller", "agent"]):
            self.assertFalse(installer.is_legacy_desktop(args))

    def run_upgrade(self, root, *, active=True, build_fails=False, stale_resources=False):
        installer = installer_module()
        old_source = root / "usr/src/shield-controller-0.1.0-alpha.1"
        old_source.mkdir(parents=True)
        registration = root / "var/lib/dkms/shield-controller/0.1.0-alpha.1/source"
        registration.parent.mkdir(parents=True)
        registration.symlink_to(old_source)
        unit = root / "usr/lib/systemd/system/shield-controller.service"
        unit.parent.mkdir(parents=True)
        unit.write_text("legacy unit")
        pairing = root / "var/lib/shield-controller/network.json"
        pairing.parent.mkdir(parents=True)
        pairing.write_text('{"saved":"pairing"}')
        headers = root / "lib/modules/test-kernel/build/Makefile"
        headers.parent.mkdir(parents=True)
        headers.touch()
        if stale_resources:
            ownership = root / "run/shield-controller/ownership.json"
            ownership.parent.mkdir(parents=True)
            ownership.write_text("{}")

        def rooted(*parts):
            path = Path(*parts)
            return root / path.relative_to("/") if path.is_absolute() else path

        def command(*arguments):
            if build_fails and arguments[:2] == ("dkms", "build"):
                raise subprocess.CalledProcessError(1, arguments)

        def service_state(action, service):
            return service == "shield-controller.service" and (action == "is-enabled" or active)

        with patch.object(installer, "Path", rooted), patch.object(installer.os, "geteuid", return_value=0), \
             patch.object(installer.os, "uname", return_value=SimpleNamespace(release="test-kernel")), \
             patch.object(installer.shutil, "which", return_value="/usr/bin/tool"), \
             patch.object(installer, "service_state", side_effect=service_state), \
             patch.object(installer, "stop_legacy_desktop") as stop_helpers, \
             patch.object(installer, "command", side_effect=command) as commands, \
             patch("sys.argv", ["install.py"]), patch("builtins.print"):
            error = None
            try:
                installer.main()
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                error = exc
        return installer, commands, stop_helpers, error

    def test_full_upgrade_transfers_pairing_and_startup_state(self):
        for active in (True, False):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                installer, commands, stop_helpers, error = self.run_upgrade(root, active=active)
                self.assertIsNone(error)
                calls = [call.args for call in commands.call_args_list]
                build = next(i for i, call in enumerate(calls) if call[:2] == ("dkms", "build"))
                stop = calls.index(("systemctl", "disable", "--now", "shield-controller.service"))
                install = next(i for i, call in enumerate(calls) if call[:2] == ("dkms", "install"))
                self.assertLess(build, stop)
                self.assertLess(stop, install)
                expected = ("systemctl", "enable", "--now", "open-fatshield.service") if active else (
                    "systemctl", "enable", "open-fatshield.service")
                self.assertIn(expected, calls)
                self.assertIn(("dkms", "remove", "shield-controller/0.1.0-alpha.1", "--all"), calls)
                self.assertFalse((root / "usr/bin/shield-controller").exists())
                self.assertTrue((root / "usr/bin/open-fatshield").exists())
                self.assertEqual((root / "var/lib/open-fatshield/network.json").read_text(), '{"saved":"pairing"}')
                stop_helpers.assert_called_once()

    def test_failed_build_leaves_legacy_service_and_package_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installer, commands, stop_helpers, error = self.run_upgrade(root, build_fails=True)
            self.assertIsInstance(error, subprocess.CalledProcessError)
            self.assertFalse(any(call.args[0] == "systemctl" for call in commands.call_args_list))
            self.assertTrue((root / "usr/lib/systemd/system/shield-controller.service").exists())
            self.assertTrue((root / "usr/src/shield-controller-0.1.0-alpha.1").exists())
            stop_helpers.assert_not_called()

    def test_stale_owned_resources_prevent_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            installer, commands, stop_helpers, error = self.run_upgrade(Path(directory), stale_resources=True)
            self.assertIsInstance(error, RuntimeError)
            self.assertFalse(any(call.args[:2] == ("dkms", "install") for call in commands.call_args_list))
