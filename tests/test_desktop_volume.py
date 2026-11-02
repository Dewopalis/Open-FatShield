from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shield_controller.desktop_volume import DesktopVolume, volume_arguments


class DesktopVolumeTest(unittest.TestCase):
    def test_only_media_key_presses_change_audio(self):
        self.assertIsNone(volume_arguments(312, 1))
        self.assertIsNone(volume_arguments(115, 0))
        self.assertIsNone(volume_arguments(113, 2))
        self.assertEqual(volume_arguments(113, 1), ("set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"))
        self.assertEqual(volume_arguments(114, 1)[-1], "5%-")
        self.assertEqual(volume_arguments(115, 2)[-1], "5%+")
        self.assertIn("1.0", volume_arguments(115, 1))

    def test_audio_commands_target_invoking_user_not_root(self):
        with patch.dict("os.environ", {"SUDO_UID": "1000"}), \
             patch("shield_controller.desktop_volume.os.geteuid", return_value=0), \
             patch("shield_controller.desktop_volume.pwd.getpwuid") as passwd, \
             patch("shield_controller.desktop_volume.bounded_run", return_value="Volume: 0.5") as run, \
             patch("builtins.print"):
            passwd.return_value.pw_name = "desktop-user"
            handler = DesktopVolume()
            handler.handle(1, 115, 1)
            handler.handle(1, 115, 0)
            handler.handle(3, 0, 32767)
        self.assertEqual(run.call_count, 2)  # availability read and one volume press
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ("runuser", "-u", "desktop-user", "--"))
        self.assertIn("XDG_RUNTIME_DIR=/run/user/1000", command)
        self.assertEqual(command[-1], "5%+")


if __name__ == "__main__":
    unittest.main()
