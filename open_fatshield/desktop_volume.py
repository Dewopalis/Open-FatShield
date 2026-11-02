"""Map SHIELD media keys from the gamepad node to the invoking user's audio."""
import os
import pwd
import subprocess
from .process_utils import bounded_run


def volume_arguments(code, value):
    if value not in (1, 2):
        return None
    if code == 113 and value == 1:
        return ("set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
    if code in (114, 115):
        return ("set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SINK@", "5%-" if code == 114 else "5%+")
    return None


class DesktopVolume:
    def __init__(self):
        uid = int(os.environ.get("SUDO_UID", str(os.getuid())))
        if uid == 0:
            raise RuntimeError("No invoking desktop user is available")
        user = pwd.getpwuid(uid).pw_name
        self.prefix = (("runuser", "-u", user, "--") if os.geteuid() == 0 else ())
        if os.geteuid() != 0 and os.getuid() != uid:
            raise RuntimeError("Cannot access another user's audio session")
        self.prefix += ("env", f"XDG_RUNTIME_DIR=/run/user/{uid}", "wpctl")
        bounded_run((*self.prefix, "get-volume", "@DEFAULT_AUDIO_SINK@"), timeout=3)
        print("Volume keys will control your desktop's default audio output.", flush=True)

    def handle(self, event_type, code, value):
        if event_type != 1:
            return
        arguments = volume_arguments(code, value)
        if arguments is None:
            return
        try:
            bounded_run((*self.prefix, *arguments), timeout=3)
            print({113: "Audio mute toggled", 114: "Audio volume decreased", 115: "Audio volume increased"}[code], flush=True)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Desktop volume action failed: {exc}", flush=True)
