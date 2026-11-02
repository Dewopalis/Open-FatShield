import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from open_fatshield import daemon, network
from open_fatshield.config import load_config

ROOT = Path(__file__).resolve().parents[1]


class NetworkTest(unittest.TestCase):
    def test_same_channel_and_unsupported_bands(self):
        link = "Connected to 02:00:00:00:00:01 (on wlan0)\n\tfreq: 2427.0\n"
        self.assertEqual(network.channel_from_link(link)["channel"], 4)
        for frequency in (5180, 5975, 2484, 2428):
            with self.assertRaises(RuntimeError):
                network.channel_from_link(link.replace("2427.0", str(frequency)))

    def test_saved_identity_and_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "network.json"
            identity = network.new_identity("02:00:00:00:00:01")
            network.atomic_json(path, identity)
            self.assertEqual(network.load_identity(path), identity)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            text = network.hostapd_config("shield0", "/run/example", 4, identity)
            self.assertIn("channel=4\n", text)
            self.assertIn("wpa_passphrase=" + identity["passphrase"], text)
            self.assertNotIn("wps_pbc", text)
            self.assertNotIn("bridge=", text)
            identity["ssid"] += "\ninterface=wlan0"
            network.atomic_json(path, identity)
            with self.assertRaises(ValueError):
                network.load_identity(path)

    def test_reject_same_interface_and_unknown_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for value in ({"interface": "shield0"}, {"ap_interface": "../wlan0"}, {"disconnect_wifi": True}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_roaming_and_channel_changes_restart_only_controller(self):
        connection = {"interface": "wlan0", "uuid": "normal", "channel": 4,
                      "frequency": 2427, "bssid": "02:00:00:00:00:01"}
        with patch.object(network, "network_state", return_value=(100, "normal")), \
             patch.object(network, "run", return_value="Connected to 02:00:00:00:00:01\n freq: 2437"):
            self.assertFalse(network.still_connected(connection))


class CleanupTest(unittest.TestCase):
    def test_stale_recovery_never_deletes_normal_interface(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            network.atomic_json(runtime / "ownership.json", {"ap_interface": "wlan0", "parent_interface": "wlan0"})
            with patch.object(daemon, "RUNTIME", runtime), patch.object(daemon, "run") as run:
                with self.assertRaises(RuntimeError):
                    daemon.recover_owned_resources()
                run.assert_not_called()

    def test_unload_failure_still_removes_owned_ap_and_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            rule = runtime / "rule.conf"
            rule.write_text("[device-open-fatshield]\nmatch-device=interface-name:shield0\nmanaged=0\n")
            network.atomic_json(runtime / "ownership.json", {"ap_interface": "shield0", "parent_interface": "wlan0",
                                                             "module": True, "interface": True, "rule": True})
            original_exists = Path.exists
            def exists(path):
                return True if str(path) in ("/sys/module/ozwpan", "/sys/class/net/shield0") else original_exists(path)
            def run(*args):
                if args[0] == "modprobe":
                    raise subprocess.TimeoutExpired(args, 15)
                return ""
            with patch.object(daemon, "RUNTIME", runtime), patch.object(daemon, "RULE", rule), \
                 patch.object(Path, "exists", exists), patch.object(daemon, "run", side_effect=run) as commands:
                with self.assertRaises(RuntimeError):
                    daemon.recover_owned_resources()
            self.assertFalse(rule.exists())
            self.assertIn(("iw", "dev", "shield0", "del"), [c.args for c in commands.call_args_list])
            self.assertTrue((runtime / "ownership.json").exists())

    def test_no_kernel_messages_is_not_a_service_error(self):
        error = subprocess.CalledProcessError(1, "journalctl", output="-- No entries --")
        with patch.object(daemon, "run", side_effect=error):
            self.assertEqual(daemon.kernel_faults("today"), "")


class PackagingTest(unittest.TestCase):
    def test_staged_install_runs_and_preserves_configuration(self):
        spec = importlib.util.spec_from_file_location("installer", ROOT / "packaging/install.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            installer.stage(stage)
            executable = stage / "usr/bin/open-fatshield"
            result = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True)
            self.assertIn("0.2.0-alpha.1", result.stdout)
            config = stage / "etc/open-fatshield/config.json"
            config.write_text('{"interface":"wlan7"}')
            installer.stage(stage)
            self.assertEqual(json.loads(config.read_text())["interface"], "wlan7")
            source = stage / "usr/src/open-fatshield-0.2.0-alpha.1"
            self.assertTrue((source / "packaging/dkms-build.sh").stat().st_mode & 0o111)
            self.assertFalse(list(source.rglob("*.ko")))
            self.assertFalse(list(stage.rglob("*.pcap")))
            self.assertFalse(list(stage.rglob("network.json")))
