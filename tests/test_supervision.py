import subprocess
import sys
import unittest
from unittest.mock import MagicMock
from shield_controller.process_utils import bounded_run, stop_owned_process


class SupervisionTest(unittest.TestCase):
    def test_failed_command_has_a_bounded_wait(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            bounded_run((sys.executable, "-c", "import time; time.sleep(60)"), timeout=0.05)

    def test_even_sigkill_wait_is_bounded(self):
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("rmmod", 2)
        self.assertFalse(stop_owned_process(process))
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
