import subprocess
import unittest
from unittest.mock import patch

from open_fatshield import cli


class PairCommandTest(unittest.TestCase):
    def test_pairing_reply_socket_is_visible_across_private_tmp(self):
        with patch.object(cli.os, "geteuid", return_value=0), \
             patch.object(cli, "read_status", return_value={"state": "ready"}), \
             patch.object(cli, "load_config", return_value={"ap_interface": "shield0"}), \
             patch.object(cli, "run", side_effect=["", "OK"]) as run, patch("builtins.print"):
            cli.root_action("pair")
        args = run.call_args.args
        self.assertEqual(args[args.index("-s") + 1], str(cli.RUNTIME / "hostapd"))
        self.assertEqual(args[args.index("-p") + 1], str(cli.RUNTIME / "hostapd"))

    def test_failed_pairing_preserves_actual_error(self):
        with patch.object(cli.os, "geteuid", return_value=0), \
             patch.object(cli, "read_status", return_value={"state": "ready"}), \
             patch.object(cli, "load_config", return_value={"ap_interface": "shield0"}), \
             patch.object(cli, "run", side_effect=["", "'WPS_PBC' command timed out."]):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                cli.root_action("pair")
