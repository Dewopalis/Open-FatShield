import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from open_fatshield.input_monitor import INPUT_EVENT, InputMonitor, wireless_nodes


DEVICES = '''I: Bus=0003 Vendor=0955 Product=7210 Version=0111
N: Name="Wireless SHIELD"
P: Phys=usb-ozwpan-1/input0
H: Handlers=kbd event25 js0

I: Bus=0003 Vendor=0955 Product=7210 Version=0111
N: Name="Wired SHIELD"
P: Phys=usb-0000:00:14.0-1/input0
H: Handlers=kbd event11 js1

I: Bus=0003 Vendor=05ac Product=024f Version=0110
N: Name="Keyboard"
H: Handlers=kbd event7
'''


class InputMonitorTest(unittest.TestCase):
    def test_only_wireless_shield_nodes_are_selected(self):
        self.assertEqual(wireless_nodes(DEVICES), {"/dev/input/event25": "Wireless SHIELD"})

    def test_signed_axes_and_buttons_are_recorded(self):
        packet = (INPUT_EVENT.pack(1, 10, 3, 0, -1234) +
                  INPUT_EVENT.pack(1, 11, 1, 304, 1) +
                  INPUT_EVENT.pack(1, 12, 0, 0, 0))
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "events.jsonl"
            monitor = InputMonitor(logfile)
            with patch("open_fatshield.input_monitor.os.open", return_value=333) as opened, \
                 patch("open_fatshield.input_monitor.os.read", side_effect=[packet, BlockingIOError]), \
                 patch("open_fatshield.input_monitor.os.close") as closed, patch("builtins.print"):
                monitor.discover(DEVICES)
                monitor.poll()
                monitor.close()
            self.assertEqual(opened.call_count, 1)
            closed.assert_called_once_with(333)
            records = [json.loads(line) for line in logfile.read_text().splitlines()]
            self.assertEqual([(r["type"], r["code"], r["value"]) for r in records],
                             [(3, 0, -1234), (1, 304, 1)])


if __name__ == "__main__":
    unittest.main()
