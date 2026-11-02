#!/usr/bin/env python3
"""Build installable DKMS/app packages without modifying the build host."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "packaging/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
VERSION = installer.VERSION
NAME = "open-fatshield-dkms"
HOOK = "/usr/lib/open-fatshield/package-hooks.py"
GUARD = '''if { [ -e /usr/bin/open-fatshield ] || [ -e /usr/bin/shield-controller ]; } && [ ! -f /usr/lib/open-fatshield/package-hooks.py ]; then
  echo "Uninstall the standalone/source installation first (pairing is preserved). See docs/packages.md." >&2
  exit 1
fi
'''


def write(path, text, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755 if executable else 0o644)


def payload(root):
    installer.stage(root)
    installer.copy(ROOT / "packaging/native-hooks.py", root / HOOK.lstrip("/"), executable=True)


def deb(work, output):
    version = VERSION.replace("-", "~", 1) + "-1"
    tree = work / "payload"
    payload(tree)
    control = tree / "DEBIAN"
    write(control / "control", f'''Package: {NAME}
Version: {version}
Architecture: all
Section: kernel
Priority: optional
Maintainer: Open FatShield contributors <noreply@github.com>
Homepage: https://github.com/Dewopalis/Open-FatShield
Depends: python3 (>= 3.10), dkms, make, gcc, network-manager, iw, hostapd, kmod, systemd, udev
Recommends: pkexec, wireplumber, python3-pyside6.qtwidgets, python3-pyside6.qtnetwork
Description: Wireless driver and desktop app for the original NVIDIA SHIELD Controller
 Includes OZWPAN DKMS sources, a concurrent Wi-Fi service and Qt tray controls.
 The kernel module builds locally. Matching kernel headers are required.
''')
    write(control / "conffiles", "/etc/open-fatshield/config.json\n")
    write(control / "preinst", '#!/bin/sh\nset -e\n' + GUARD + f'if [ -f {HOOK} ]; then {HOOK} prepare; fi\n', True)
    write(control / "postinst", f'#!/bin/sh\nset -e\nif [ "$1" = configure ]; then {HOOK} configure; fi\n', True)
    write(control / "prerm", f'#!/bin/sh\nset -e\nif [ "$1" = remove ]; then {HOOK} remove; fi\n', True)
    write(control / "postrm", '#!/bin/sh\nset -e\nif [ -d /run/systemd/system ]; then systemctl daemon-reload; fi\n', True)
    target = output / f"{NAME}_{version}_all.deb"
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(tree), str(target)], check=True)
    subprocess.run(["dpkg-deb", "--info", str(target)], check=True)


def rpm(work, output):
    base, _, suffix = VERSION.partition("-")
    release = "0." + suffix + ".1" if suffix else "1"
    tree = work / "payload"
    payload(tree)
    top = work / "rpm"
    for name in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (top / name).mkdir(parents=True)
    file_list = []
    for path in sorted(tree.rglob("*")):
        if not path.is_file():
            continue
        relative = "/" + path.relative_to(tree).as_posix()
        prefix = "%config(noreplace) " if relative == "/etc/open-fatshield/config.json" else ""
        prefix = "%license " if relative.endswith("/LICENSE") else prefix
        file_list.append(prefix + relative)
    package_spec = top / "SPECS/open-fatshield.spec"
    write(package_spec, f'''Name: {NAME}
Version: {base}
Release: {release}
Summary: Wireless driver and tray app for the original NVIDIA SHIELD Controller
License: GPL-2.0-only
URL: https://github.com/Dewopalis/Open-FatShield
BuildArch: noarch
AutoReqProv: no
Requires: python3 >= 3.10, dkms, make, gcc, NetworkManager-wifi, iw, hostapd, kmod, systemd, systemd-udev
Recommends: python3-pyside6, wireplumber, polkit
%description
OZWPAN DKMS driver sources, concurrent Wi-Fi service and Qt tray controls.
Matching kernel headers/devel and the kernel compiler are required locally.
%install
mkdir -p "%{{buildroot}}"
cp -a "{tree}/." "%{{buildroot}}/"
%pre
{GUARD}
if [ -f {HOOK} ]; then {HOOK} prepare; fi
%post
{HOOK} configure
%preun
if [ "$1" -eq 0 ]; then {HOOK} remove; fi
%postun
if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
%files
''' + "\n".join(file_list) + "\n")
    subprocess.run(["rpmbuild", "--define", f"_topdir {top}", "--define", "__os_install_post %{nil}",
                    "-bb", str(package_spec)], check=True)
    for package in (top / "RPMS").rglob("*.rpm"):
        target = output / package.name
        shutil.copy2(package, target)
        subprocess.run(["rpm", "-qip", str(target)], check=True)


def arch(work, output):
    version = VERSION.replace("-", ".")
    tree = work / "payload"
    payload(tree)
    write(tree / "usr/share/libalpm/hooks/90-open-fatshield-resume.hook", f'''[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = {NAME}
[Action]
Description = Restoring Open FatShield after DKMS builds...
When = PostTransaction
Exec = {HOOK} resume
''')
    write(work / "open-fatshield.install", f'''pre_upgrade() {{ {HOOK} prepare; }}
post_install() {{ {HOOK} configure --external-dkms; }}
post_upgrade() {{ post_install; }}
pre_remove() {{ {HOOK} remove --external-dkms; }}
post_remove() {{ if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi; }}
''')
    write(work / "PKGBUILD", f'''pkgname={NAME}
pkgver={version}
pkgrel=1
pkgdesc='Wireless driver and tray app for the original NVIDIA SHIELD Controller'
arch=('any')
url='https://github.com/Dewopalis/Open-FatShield'
license=('GPL-2.0-only')
depends=('python' 'dkms' 'networkmanager' 'iw' 'hostapd' 'kmod' 'systemd')
optdepends=('pyside6: desktop tray' 'wireplumber: volume keys' 'polkit: graphical authorization' 'linux-headers: module build for stock Arch kernel' 'clang: Clang-built kernels' 'llvm: Clang-built kernels')
backup=('etc/open-fatshield/config.json')
install=open-fatshield.install
options=('!strip' '!debug')
package() {{
  cp -a "$startdir/payload/." "$pkgdir/"
}}
''')
    subprocess.run(["makepkg", "--nodeps", "--noconfirm"], cwd=work, check=True)
    for package in work.glob("*.pkg.tar.*"):
        target = output / package.name
        shutil.copy2(package, target)
        subprocess.run(["pacman", "-Qip", str(target)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format", choices=("deb", "rpm", "arch"))
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="open-fatshield-package-") as temporary:
        {"deb": deb, "rpm": rpm, "arch": arch}[args.format](Path(temporary), output)


if __name__ == "__main__":
    main()
