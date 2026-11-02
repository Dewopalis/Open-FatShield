#!/usr/bin/python3
"""Package-manager lifecycle hooks; never called while building a package."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from open_fatshield import __version__ as VERSION

PACKAGE = "open-fatshield"
SERVICE = PACKAGE + ".service"
MARKER = Path("/run/open-fatshield/package-upgrade.json")


def run(*args, check=True):
    return subprocess.run(args, check=check, timeout=600)


def systemd_running():
    return Path("/run/systemd/system").is_dir()


def prepare():
    if not systemd_running():
        return
    active = run("systemctl", "is-active", "--quiet", SERVICE, check=False).returncode == 0
    if MARKER.exists():
        active = active or json.loads(MARKER.read_text()).get("active", False)
    MARKER.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump({"active": active}, file)
    run("systemctl", "stop", SERVICE)


def versions():
    root = Path("/var/lib/dkms") / PACKAGE
    return [p.name for p in root.iterdir() if (p / "source").is_symlink()] if root.is_dir() else []


def resume():
    if not systemd_running() or not MARKER.exists():
        return
    if json.loads(MARKER.read_text()).get("active"):
        if run("modinfo", "ozwpan", check=False).returncode:
            print("Open FatShield: install matching kernel headers and rebuild DKMS before reconnecting.", file=sys.stderr)
            return
        run("systemctl", "start", SERVICE)
    MARKER.unlink(missing_ok=True)


def configure(external_dkms=False):
    if systemd_running():
        run("systemctl", "daemon-reload")
        run("udevadm", "control", "--reload-rules")
    if external_dkms:
        return  # Pacman's DKMS hook builds before our later resume hook.
    registered = versions()
    if VERSION not in registered:
        run("dkms", "add", "-m", PACKAGE, "-v", VERSION)
    kernel = os.uname().release
    headers = Path(f"/lib/modules/{kernel}/build/Makefile").is_file()
    if headers:
        run("dkms", "build", "-m", PACKAGE, "-v", VERSION, "-k", kernel)
    for version in registered:
        if version != VERSION:
            run("dkms", "remove", "-m", PACKAGE, "-v", version, "--all")
    if headers:
        run("dkms", "install", "-m", PACKAGE, "-v", VERSION, "-k", kernel, "--force")
        resume()
    else:
        print("Open FatShield installed. Matching running-kernel headers are missing; install them, then run sudo dkms autoinstall.", file=sys.stderr)


def remove(external_dkms=False):
    if systemd_running():
        run("systemctl", "disable", "--now", SERVICE)
    if not external_dkms:
        for version in versions():
            run("dkms", "remove", "-m", PACKAGE, "-v", version, "--all")
    MARKER.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "configure", "remove", "resume"))
    parser.add_argument("--external-dkms", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Package lifecycle hooks must run as root")
    if args.action == "prepare":
        prepare()
    elif args.action == "configure":
        configure(args.external_dkms)
    elif args.action == "remove":
        remove(args.external_dkms)
    else:
        resume()


if __name__ == "__main__":
    main()
