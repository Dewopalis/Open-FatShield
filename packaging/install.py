#!/usr/bin/env python3
"""Install from a reviewed checkout, or stage a package without system changes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1]
VERSION = "0.1.0-alpha.1"
PACKAGE = "shield-controller"
FILES = {
    "bin/shield-controller": "/usr/bin/shield-controller",
    "packaging/shield-controller.service": "/usr/lib/systemd/system/shield-controller.service",
    "packaging/shield-controller.desktop": "/usr/share/applications/shield-controller.desktop",
    "packaging/shield-controller-agent.desktop": "/etc/xdg/autostart/shield-controller-agent.desktop",
    "packaging/shield-controller-tray.desktop": "/etc/xdg/autostart/shield-controller-tray.desktop",
    "packaging/70-shield-controller.rules": "/usr/lib/udev/rules.d/70-shield-controller.rules",
}


def command(*arguments):
    subprocess.run(arguments, check=True, timeout=600)


def copy(source, destination, executable=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755 if executable else 0o644)


def stage(destination):
    def target(path):
        return destination / path.lstrip("/")
    for source, path in FILES.items():
        copy(SOURCE / source, target(path), path == "/usr/bin/shield-controller")
    for source in (SOURCE / "shield_controller").glob("*.py"):
        copy(source, target("/usr/lib/shield-controller/shield_controller") / source.name)
    config = target("/etc/shield-controller/config.json")
    if not config.exists():
        copy(SOURCE / "packaging/config.json", config)
    dkms = target(f"/usr/src/{PACKAGE}-{VERSION}")
    for source in (SOURCE / "driver").iterdir():
        if source.suffix in (".c", ".h") and not source.name.endswith(".mod.c") or source.name in ("Makefile", "Kconfig"):
            copy(source, dkms / "driver" / source.name)
    copy(SOURCE / "dkms.conf", dkms / "dkms.conf")
    copy(SOURCE / "packaging/dkms-build.sh", dkms / "packaging/dkms-build.sh", executable=True)
    for name in ("LICENSE", "README.md"):
        copy(SOURCE / name, target("/usr/share/doc/shield-controller") / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destdir", type=Path, help="Stage files only; do not build or activate anything")
    parser.add_argument("--enable", action="store_true", help="Start the service and enable it at boot")
    parser.add_argument("--app-only", action="store_true", help="Refresh application files without rebuilding or restarting the installed driver")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--purge", action="store_true", help="Also delete saved pairing/configuration during uninstall")
    args = parser.parse_args()
    if args.destdir:
        if args.uninstall or args.enable or args.purge or args.app_only:
            parser.error("--destdir cannot be combined with activation or uninstall")
        stage(args.destdir.resolve())
        print("Package staged; no system configuration was changed.")
        return
    if os.geteuid() != 0:
        parser.error("System installation needs sudo; staging with --destdir does not")
    if args.purge and not args.uninstall:
        parser.error("--purge requires --uninstall")
    if args.app_only:
        if args.enable or args.uninstall or args.purge:
            parser.error("--app-only cannot be combined with other actions")
        if not Path(f"/var/lib/dkms/{PACKAGE}/{VERSION}").is_dir():
            parser.error("Install the full package before using --app-only")
        stage(Path("/"))
        command("systemctl", "daemon-reload")
        command("udevadm", "control", "--reload-rules")
        print("Application updated; the running driver was left connected.")
        print("As your normal user, run: shield-controller gui")
        return
    if args.uninstall:
        command("systemctl", "disable", "--now", "shield-controller.service")
        command("dkms", "remove", f"{PACKAGE}/{VERSION}", "--all")
        for path in FILES.values():
            Path(path).unlink(missing_ok=True)
        for path in ("/usr/lib/shield-controller", f"/usr/src/{PACKAGE}-{VERSION}", "/usr/share/doc/shield-controller"):
            if Path(path).exists():
                shutil.rmtree(path)
        if args.purge:
            for path in ("/etc/shield-controller", "/var/lib/shield-controller"):
                if Path(path).exists():
                    shutil.rmtree(path)
        command("systemctl", "daemon-reload")
        command("udevadm", "control", "--reload-rules")
        print("Uninstalled. Log out to stop an already-running desktop volume agent.")
        return
    for executable in ("dkms", "nmcli", "iw", "hostapd", "hostapd_cli", "modprobe", "systemctl", "udevadm", "make"):
        if not shutil.which(executable):
            parser.error(f"Missing prerequisite: {executable}; see README.md")
    kernel = os.uname().release
    if not Path(f"/lib/modules/{kernel}/build/Makefile").is_file():
        parser.error(f"Install matching headers for the running kernel {kernel}")
    was_active = subprocess.run(["systemctl", "is-active", "--quiet", "shield-controller.service"]).returncode == 0
    if was_active:
        command("systemctl", "stop", "shield-controller.service")
    # DKMS refuses to add an existing version. Rebuild it explicitly for upgrades.
    registered = Path(f"/var/lib/dkms/{PACKAGE}/{VERSION}").exists()
    if registered:
        command("dkms", "remove", f"{PACKAGE}/{VERSION}", "--all")
    stage(Path("/"))
    command("dkms", "add", f"{PACKAGE}/{VERSION}")
    command("dkms", "build", f"{PACKAGE}/{VERSION}", "-k", kernel)
    command("dkms", "install", f"{PACKAGE}/{VERSION}", "-k", kernel)
    command("systemctl", "daemon-reload")
    command("udevadm", "control", "--reload-rules")
    if args.enable:
        command("systemctl", "enable", "--now", "shield-controller.service")
    elif was_active:
        command("systemctl", "start", "shield-controller.service")
    print("Installed. As your normal desktop user, run: shield-controller pair")
    print("Optional automatic startup: shield-controller enable")


if __name__ == "__main__":
    main()
