from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from open_fatshield.get_input_reports import read_reports


class ReportProbeTest(unittest.TestCase):
    def test_only_known_input_get_ioctl_is_used(self):
        seen = []
        def ioctl(descriptor, request, data, mutate):
            self.assertEqual(descriptor, 123)
            self.assertEqual(request, 0xC041480A)
            self.assertTrue(mutate)
            seen.append(data[0])
            data[1:3] = b"\x12\x34"
            return 3
        with patch("open_fatshield.get_input_reports.fcntl.ioctl", side_effect=ioctl), patch("builtins.print"):
            results = read_reports(123)
        self.assertEqual(seen, [1, 2])
        self.assertEqual([r["data"] for r in results], ["011234", "021234"])

    def test_failed_read_does_not_turn_into_a_write(self):
        with patch("open_fatshield.get_input_reports.fcntl.ioctl", side_effect=OSError("simulated read failure")) as ioctl, \
             patch("builtins.print"):
            results = read_reports(123)
        self.assertEqual(ioctl.call_count, 2)
        self.assertTrue(all("error" in r for r in results))
        self.assertTrue(all(call.args[1] == 0xC041480A for call in ioctl.call_args_list))


if __name__ == "__main__":
    unittest.main()
