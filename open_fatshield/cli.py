import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from . import __version__
from .config import RUNTIME, load_config
from .network import connected_network
from .process_utils import bounded_run

SERVICE = "open-fatshield.service"


def run(*args, timeout=20):
    return bounded_run(args, timeout=timeout)


def read_status():
    path = RUNTIME / "status.json"
    if not path.exists():
        return {"state": "stopped", "message": "Controller service is not running"}
    status = json.loads(path.read_text())
    result = subprocess.run(["systemctl", "is-active", "--quiet", SERVICE], timeout=5)
    if result.returncode and status.get("state") not in ("stopped", "kernel_fault"):
        return {"state": "stopped", "message": "Controller service is not running"}
    return status


def ensure_agent():
    if os.geteuid() != 0:
        executable = shutil.which("open-fatshield") or str(Path(__file__).parents[1] / "bin/open-fatshield")
        subprocess.Popen([sys.executable, executable, "agent"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def root_action(action):
    if os.geteuid() != 0:
        ensure_agent()
        executable = Path("/usr/bin/open-fatshield")
        if not executable.exists() or executable.stat().st_uid != 0 or executable.stat().st_mode & 0o022:
            raise RuntimeError("Install the root-owned application first with sudo python3 packaging/install.py")
        if not shutil.which("pkexec"):
            raise RuntimeError(f"Run: sudo {executable} {action}")
        result = subprocess.run(["pkexec", str(executable), action])
        if result.returncode:
            raise RuntimeError(f"{action} did not complete (authorization or service error)")
        return
    if action == "start":
        run("systemctl", "start", SERVICE)
        print("Controller service started. Use 'open-fatshield pair' for first-time pairing.")
    elif action == "stop":
        run("systemctl", "stop", SERVICE, timeout=80)
        print("Controller service stopped; normal Wi-Fi remains managed by NetworkManager.")
    elif action == "enable":
        run("systemctl", "enable", "--now", SERVICE)
        print("Controller service enabled at boot.")
    elif action == "disable":
        run("systemctl", "disable", "--now", SERVICE, timeout=80)
        print("Controller service disabled at boot and stopped.")
    elif action == "pair":
        run("systemctl", "start", SERVICE)
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            status = read_status()
            if status["state"] in ("ready", "connected"):
                interface = load_config()["ap_interface"]
                control = str(RUNTIME / "hostapd")
                # Replies must use /run: hostapd's PrivateTmp namespace cannot
                # see a client socket created in an external command's /tmp.
                output = run("hostapd_cli", "-s", control, "-p", control, "-i", interface, "wps_pbc")
                if "OK" not in output or "FAIL" in output:
                    raise RuntimeError("Could not start pairing: " + output)
                print("Pairing is open for two minutes. Unplug USB, then hold NVIDIA until it flashes.")
                return
            if status["state"] in ("waiting", "kernel_fault"):
                raise RuntimeError(status["message"])
            time.sleep(0.25)
        raise RuntimeError("Controller AP is not ready. Check 'open-fatshield status' and 'open-fatshield logs'.")


def doctor():
    problems = []
    for executable in ("nmcli", "iw", "hostapd", "hostapd_cli", "modprobe", "modinfo", "systemctl"):
        available = bool(shutil.which(executable))
        print(f"{'OK' if available else 'MISSING'}: {executable}")
        if not available:
            problems.append(executable)
    try:
        module = run("modinfo", "-n", "ozwpan")
        print("OK: installed kernel module " + module)
    except (OSError, subprocess.SubprocessError):
        print("MISSING: ozwpan for the running kernel; install/rebuild the DKMS package")
        problems.append("kernel module")
    try:
        network = connected_network(load_config())
        print(f"OK: connected 2.4 GHz Wi-Fi interface {network['interface']}, channel {network['channel']}")
    except Exception as exc:
        print("WAITING: " + str(exc))
    print("Kernel: " + os.uname().release)
    print("Volume control: " + ("wpctl available" if shutil.which("wpctl") else "install WirePlumber for desktop volume control"))
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="open-fatshield", description="Original SHIELD controller wireless support")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("command", choices=["start", "stop", "pair", "status", "enable", "disable", "doctor", "logs", "gui", "tray", "agent", "daemon", "cleanup"])
    parser.add_argument("--json", action="store_true", help="Machine-readable status")
    args = parser.parse_args(argv)
    try:
        if args.command in ("start", "stop", "pair", "enable", "disable"):
            root_action(args.command)
        elif args.command == "status":
            status = read_status()
            print(json.dumps(status) if args.json else status["message"])
        elif args.command == "doctor":
            return doctor()
        elif args.command == "logs":
            return subprocess.call(["journalctl", "-u", SERVICE, "-n", "100", "--no-pager"])
        elif args.command == "daemon":
            from .daemon import main as serve
            serve()
        elif args.command == "cleanup":
            if os.geteuid() != 0:
                raise RuntimeError("Cleanup runs as root through the system service")
            from .daemon import recover_owned_resources
            recover_owned_resources()
        elif args.command == "agent":
            from .agent import main as agent
            agent()
        elif args.command in ("gui", "tray"):
            from .tray import main as gui
            gui()
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"open-fatshield: {exc}", file=sys.stderr)
        output = getattr(exc, "output", None)
        if output:
            print(output, file=sys.stderr)
        return 1
    return 0
