import fcntl
import os
from pathlib import Path
import signal
import time

from .desktop_volume import DesktopVolume
from .input_monitor import InputMonitor


def main():
    if os.geteuid() == 0:
        raise SystemExit("Run the desktop agent as your normal desktop user")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    lock = (runtime / "open-fatshield-agent.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    monitor = None
    try:
        while not stopped:
            if monitor is None:
                try:
                    monitor = InputMonitor(media_handler=DesktopVolume())
                except Exception as exc:
                    print(f"Waiting for desktop audio: {exc}", flush=True)
                    time.sleep(3)
                    continue
            monitor.discover(Path("/proc/bus/input/devices").read_text())
            monitor.poll()
            time.sleep(0.1)
    finally:
        if monitor is not None:
            monitor.close()
        lock.close()
