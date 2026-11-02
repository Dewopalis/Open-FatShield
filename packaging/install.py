#!/usr/bin/env python3
"""Install from a reviewed checkout, or stage a package without system changes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import re
import signal
import time

SOURCE = Path(__file__).resolve().parents[1]
VERSION = "0.2.0-alpha.1"
PACKAGE = "open-fatshield"
FILES = {
    "bin/open-fatshield": "/usr/bin/open-fatshield",
    "packaging/open-fatshield.service": "/usr/lib/systemd/system/open-fatshield.service",
    "packaging/open-fatshield.desktop": "/usr/share/applications/open-fatshield.desktop",
    "packaging/open-fatshield-agent.desktop": "/etc/xdg/autostart/open-fatshield-agent.desktop",
    "packaging/open-fatshield-tray.desktop": "/etc/xdg/autostart/open-fatshield-tray.desktop",
    "packaging/70-open-fatshield.rules": "/usr/lib/udev/rules.d/70-open-fatshield.rules",
}
LEGACY_PACKAGE = "shield-controller"
LEGACY_SERVICE = LEGACY_PACKAGE + ".service"


def command(*arguments):
    subprocess.run(arguments, check=True, timeout=600)


def copy(source, destination, executable=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755 if executable else 0o644)


def migrate_legacy_files(root=Path("/")):
    """Copy saved pairing/configuration once; leave the originals as backups."""
    for relative, mode in (("etc/{name}/config.json", 0o644),
                           ("var/lib/{name}/network.json", 0o600),
                           ("run/{name}/kernel-fault", 0o600)):
        source = root / relative.format(name=LEGACY_PACKAGE)
        target = root / relative.format(name=PACKAGE)
        if source.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True,
                                mode=0o700 if relative.startswith("var/lib/") else 0o755)
            if relative.startswith("var/lib/"):
                target.parent.chmod(0o700)
            copy(source, target)
            target.chmod(mode)


def registered_versions(package, root=Path("/var/lib/dkms")):
    base = root / package
    if not base.is_dir():
        return []
    return sorted(path.name for path in base.iterdir()
                  if re.fullmatch(r"[A-Za-z0-9_.+-]+", path.name)
                  and ((path / "source").is_symlink() or (path / "source").exists()))


def is_legacy_desktop(arguments):
    for index in (0, 1):
        if (len(arguments) > index + 1 and arguments[index] == "/usr/bin/shield-controller"
                and arguments[index + 1] in ("agent", "gui", "tray")):
            return True
    return False


def stop_legacy_desktop():
    processes = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            arguments = directory.joinpath("cmdline").read_bytes().decode(errors="replace").split("\0")
            if is_legacy_desktop(arguments):
                os.kill(int(directory.name), signal.SIGTERM)
                processes.append(directory)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    deadline = time.monotonic() + 5
    while processes and time.monotonic() < deadline:
        remaining = []
        for directory in processes:
            try:
                # A zombie has already released its input devices and locks.
                if directory.joinpath("stat").read_text().rsplit(")", 1)[1].split()[0] != "Z":
                    remaining.append(directory)
            except FileNotFoundError:
                pass
        processes = remaining
        if processes:
            time.sleep(0.1)
    if processes:
        raise RuntimeError("Close the old SHIELD Controller tray/volume helper and retry installation")


def remove_legacy_files(root=Path("/")):
    for path in FILES.values():
        (root / path.lstrip("/").replace(PACKAGE, LEGACY_PACKAGE)).unlink(missing_ok=True)
    for path in ("usr/lib/shield-controller", "usr/share/doc/shield-controller"):
        directory = root / path
        if directory.exists():
            shutil.rmtree(directory)


def service_state(action, service):
    return subprocess.run(["systemctl", action, "--quiet", service], timeout=15,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def stage(destination):
    def target(path):
        return destination / path.lstrip("/")
    for source, path in FILES.items():
        copy(SOURCE / source, target(path), path == "/usr/bin/open-fatshield")
    for source in (SOURCE / "open_fatshield").glob("*.py"):
        copy(source, target("/usr/lib/open-fatshield/open_fatshield") / source.name)
    config = target("/etc/open-fatshield/config.json")
    if not config.exists():
        copy(SOURCE / "packaging/config.json", config)
    dkms = target(f"/usr/src/{PACKAGE}-{VERSION}")
    for source in (SOURCE / "driver").iterdir():
        if source.suffix in (".c", ".h") and not source.name.endswith(".mod.c") or source.name in ("Makefile", "Kconfig"):
            copy(source, dkms / "driver" / source.name)
    copy(SOURCE / "dkms.conf", dkms / "dkms.conf")
    copy(SOURCE / "packaging/dkms-build.sh", dkms / "packaging/dkms-build.sh", executable=True)
    for name in ("LICENSE", "README.md", "CHANGELOG.md", "SUPPORT.md", "CONTRIBUTING.md", "SECURITY.md"):
        copy(SOURCE / name, target("/usr/share/doc/open-fatshield") / name)
    copy(SOURCE / "docs/design.md", target("/usr/share/doc/open-fatshield/docs/design.md"))
    copy(SOURCE / "docs/packages.md", target("/usr/share/doc/open-fatshield/docs/packages.md"))


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
    if Path("/usr/lib/open-fatshield/package-hooks.py").exists():
        parser.error("This installation is package-managed. Use your package manager to upgrade or remove it before switching to the source installer.")
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
        print("As your normal user, run: open-fatshield gui")
        return
    if args.uninstall:
        command("systemctl", "disable", "--now", "open-fatshield.service")
        command("dkms", "remove", f"{PACKAGE}/{VERSION}", "--all")
        for path in FILES.values():
            Path(path).unlink(missing_ok=True)
        for path in ("/usr/lib/open-fatshield", f"/usr/src/{PACKAGE}-{VERSION}", "/usr/share/doc/open-fatshield"):
            if Path(path).exists():
                shutil.rmtree(path)
        if args.purge:
            for path in ("/etc/open-fatshield", "/var/lib/open-fatshield",
                         "/etc/shield-controller", "/var/lib/shield-controller"):
                if Path(path).exists():
                    shutil.rmtree(path)
        command("systemctl", "daemon-reload")
        command("udevadm", "control", "--reload-rules")
        print("Uninstalled. Log out to stop any already-running tray or volume helper.")
        return
    for executable in ("dkms", "nmcli", "iw", "hostapd", "hostapd_cli", "modprobe", "systemctl", "udevadm", "make"):
        if not shutil.which(executable):
            parser.error(f"Missing prerequisite: {executable}; see README.md")
    kernel = os.uname().release
    if not Path(f"/lib/modules/{kernel}/build/Makefile").is_file():
        parser.error(f"Install matching headers for the running kernel {kernel}")
    service = PACKAGE + ".service"
    was_active = service_state("is-active", service)
    was_enabled = service_state("is-enabled", service)
    legacy_active = service_state("is-active", LEGACY_SERVICE)
    legacy_enabled = service_state("is-enabled", LEGACY_SERVICE)
    legacy_versions = registered_versions(LEGACY_PACKAGE, Path("/var/lib/dkms"))
    current_versions = registered_versions(PACKAGE, Path("/var/lib/dkms"))
    migrate_legacy_files(Path("/"))
    # Build the new package before stopping a working legacy installation.
    if VERSION in current_versions:
        if was_active:
            command("systemctl", "stop", service)
        command("dkms", "remove", f"{PACKAGE}/{VERSION}", "--all")
    stage(Path("/"))
    command("dkms", "add", f"{PACKAGE}/{VERSION}")
    command("dkms", "build", f"{PACKAGE}/{VERSION}", "-k", kernel)
    if was_active and VERSION not in current_versions:
        command("systemctl", "stop", service)
    if Path("/usr/lib/systemd/system", LEGACY_SERVICE).exists() or legacy_active or legacy_enabled:
        command("systemctl", "disable", "--now", LEGACY_SERVICE)
    stop_legacy_desktop()
    if (Path("/run/shield-controller/ownership.json").exists()
            or Path("/run/NetworkManager/conf.d/90-shield-controller.conf").exists()):
        raise RuntimeError("Legacy controller cleanup is incomplete. Inspect the old service logs and resolve it before retrying.")
    for package, versions in ((LEGACY_PACKAGE, legacy_versions), (PACKAGE, current_versions)):
        for version in versions:
            if package == PACKAGE and version == VERSION:
                continue
            command("dkms", "remove", f"{package}/{version}", "--all")
            source = Path(f"/usr/src/{package}-{version}")
            if source.exists():
                shutil.rmtree(source)
    command("dkms", "install", f"{PACKAGE}/{VERSION}", "-k", kernel)
    remove_legacy_files(Path("/"))
    command("systemctl", "daemon-reload")
    command("udevadm", "control", "--reload-rules")
    if args.enable or was_enabled or legacy_enabled:
        arguments = ["systemctl", "enable"]
        if args.enable or was_active or legacy_active:
            arguments.append("--now")
        command(*arguments, service)
    elif was_active or legacy_active:
        command("systemctl", "start", service)
    print("Installed. As your normal desktop user, run: open-fatshield pair")
    print("Optional automatic startup: open-fatshield enable")


if __name__ == "__main__":
    main()
