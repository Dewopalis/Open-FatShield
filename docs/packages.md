# Installable packages

The **Packages** GitHub Actions workflow builds `.deb`, `.rpm` and Arch
`.pkg.tar.zst` files for pull requests, pushes to main and manual runs. Version
tags also publish the packages, a source archive and SHA-256 checksums to GitHub
Releases. CI builds each format with its native package tools and inspects its
metadata. Builds do not require access to controller hardware or root on your PC.

These are ready-to-install **DKMS/app packages**, not kernel-specific `.ko`
binaries. DKMS builds the module for your kernel on the target machine. Install
matching kernel headers/devel first, plus Clang/LLVM if your kernel uses Clang.
Runtime support remains tested on CachyOS/Intel iwlwifi; building other package
formats does not establish hardware compatibility on those distributions.

## Fresh installation

Download the format for your distribution from
[Releases](https://github.com/Dewopalis/Open-FatShield/releases).

Debian/Ubuntu:

```sh
sudo apt install ./open-fatshield-dkms_*_all.deb
```

Fedora/RPM systems (the configured repositories must provide DKMS):

```sh
sudo dnf install ./open-fatshield-dkms-*.noarch.rpm
```

Arch/CachyOS:

```sh
sudo pacman -U ./open-fatshield-dkms-*-any.pkg.tar.zst
sudo pacman -S --needed pyside6 wireplumber polkit
```

The Debian/RPM packages recommend the optional GUI/audio dependencies. PySide6
availability varies by distribution release; if unavailable, the CLI still works.
For example, the Debian split QtWidgets/QtNetwork packages must be available for
the tray. Do not install dependencies from a different distribution release.

Then, as your normal user:

```sh
open-fatshield doctor
open-fatshield pair
open-fatshield gui
```

Installation does not automatically enable the service on a fresh machine. Use
`open-fatshield enable` to enable it at boot. The tray starts at desktop login.
The same 2.4 GHz Wi-Fi and concurrent managed/AP requirements apply.

If running-kernel headers were missing during installation, install them and run
`sudo dkms autoinstall` before pairing. Check build failures with your package
manager/DKMS logs and `open-fatshield doctor`.

## Switching from the source installer

Do not install a native package over files managed by `packaging/install.py`.
First uninstall from the same source release you installed:

```sh
sudo python3 packaging/install.py --uninstall
```

Leave out `--purge`: configuration and saved pairing remain. Close the old tray
and volume helper or log out, then install the native package and reopen the app.
Users still on the original `shield-controller` release should first perform the
documented source upgrade to 0.2.0-alpha.1, which migrates pairing to the new path.
Native packages deliberately reject an existing standalone installation rather
than silently take ownership of it. On Arch, pacman itself rejects file conflicts.

Use the package manager for subsequent upgrades and removal. Do not use the
source uninstaller or `--app-only` on a package-managed installation. Packages
preserve `/etc/open-fatshield/config.json` using native configuration-file rules;
saved pairing in `/var/lib/open-fatshield` is retained on removal.

## Build and release

```sh
python3 packaging/build_packages.py deb   # dpkg-deb
python3 packaging/build_packages.py rpm   # rpmbuild/rpm
python3 packaging/build_packages.py arch  # makepkg/pacman; run without root
```

Outputs go to `dist/`. Run the **Packages** workflow manually to get CI artifacts
without creating a release. For a release, the version tag must exactly match
`bin/open-fatshield --version`; all three package jobs must succeed before the
publish job runs. Publication uses repository-token write permission only in
that job. Do not separately create a release with that tag before the workflow.
Generated packages are unsigned; checksums verify the downloaded assets against
the release manifest, rather than providing a distribution signing key.
