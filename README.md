# Open FatShield

[![Checks](https://github.com/Dewopalis/Open-FatShield/actions/workflows/check.yml/badge.svg)](https://github.com/Dewopalis/Open-FatShield/actions/workflows/check.yml)
[![License: GPL v2](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Status: experimental alpha](https://img.shields.io/badge/status-experimental%20alpha-orange.svg)](https://github.com/Dewopalis/Open-FatShield/releases)

Wireless Linux support for the original NVIDIA SHIELD Controller (2014/2015,
USB ID `0955:7210`). This controller uses Wi-Fi, rather than Bluetooth.

**Experimental alpha.** Gamepad buttons, sticks, touchpad mouse and desktop
volume/mute have been tested wirelessly while normal Wi-Fi remains connected.
Controller audio input and output have also been confirmed working by the project
maintainer on the tested setup.
The installed service has also been tested live. Saved-pairing reconnection and
boot behavior still need validation.
This is a community project, unaffiliated with NVIDIA.

| Feature | Status |
| --- | --- |
| Buttons, D-pad, sticks and shoulder controls | Tested wirelessly |
| Touchpad mouse | Tested wirelessly |
| Desktop volume and mute | Tested with WirePlumber |
| Controller and normal Wi-Fi together | Tested on Intel iwlwifi, 2.4 GHz |
| Qt status tray and pairing window | Implemented; offscreen UI check passed |
| Automatic reconnect and reboot startup | Implemented; live validation pending |
| Controller audio input and output | Tested and working on the maintainer's setup |
| Rumble | Tested and working on the maintainer's setup |

## Download

**[Download Open FatShield — source package (.tar.gz)](https://github.com/Dewopalis/Open-FatShield/releases/download/v0.1.0-alpha.1-r2/open-fatshield-0.1.0-alpha.1-r2.tar.gz)**

[Release notes](https://github.com/Dewopalis/Open-FatShield/releases/tag/v0.1.0-alpha.1-r2)
· [SHA-256 checksums](https://github.com/Dewopalis/Open-FatShield/releases/download/v0.1.0-alpha.1-r2/SHA256SUMS)
· [All releases](https://github.com/Dewopalis/Open-FatShield/releases)

This is an experimental **source release**, with an installer that builds the
driver for your running kernel through DKMS. It is not a prebuilt `.deb`, `.rpm`
or Arch package. The `r2` download refreshes documentation and project naming;
the driver and application remain version `0.1.0-alpha.1`.

## Requirements

* Linux with systemd, NetworkManager and a Wi-Fi adapter supporting simultaneous
  managed + AP interfaces on one channel.
* An existing **2.4 GHz** Wi-Fi connection. The controller AP follows its channel.
  The service waits when normal Wi-Fi is disconnected or using 5/6 GHz.
* Python 3.10+, hostapd with WPS support, iw, DKMS, make and matching kernel headers.
  Use Clang/LLVM for a kernel built with Clang; otherwise use GCC.
* WirePlumber (`wpctl`) for desktop volume controls. Polkit (`pkexec`) for graphical
  authorization. PySide6 and a system tray for the desktop app (KDE supported;
  GNOME requires a tray extension, or use the app window).

Live testing used CachyOS, an Intel iwlwifi adapter and kernel 7.3.1.
The driver also builds against 6.18.55 LTS headers; LTS runtime is untested.
Other adapters, distributions, controller models and multi-controller operation
are not yet validated. The 2017 Bluetooth controller is outside this project.
See [compatibility and troubleshooting](SUPPORT.md) before reporting a problem.

## Install

On Arch/CachyOS, install prerequisites and the header package matching your running
kernel (for example `linux-cachyos-headers`):

```sh
sudo pacman -S --needed python dkms hostapd iw networkmanager wireplumber polkit pyside6 base-devel clang llvm
```

Extract the downloaded package, then enter its directory:

```sh
tar -xzf open-fatshield-0.1.0-alpha.1-r2.tar.gz
cd open-fatshield-0.1.0-alpha.1-r2
```

Alternatively, get the source with Git:

```sh
git clone https://github.com/Dewopalis/Open-FatShield.git open-fatshield
cd open-fatshield
```

From either source directory, install and pair:

```sh
sudo python3 packaging/install.py
shield-controller doctor
shield-controller pair
shield-controller gui
```

Run `doctor`, `pair` and `gui` as your normal desktop user. Pair opens a two-minute
WPS window. Unplug the controller's USB cable and hold the NVIDIA button until
it flashes. The desktop volume helper starts automatically with this command.

For automatic startup:

```sh
shield-controller enable
```

The system service starts at boot and waits for suitable normal Wi-Fi. The
desktop volume helper starts when you log in. The controller network's identity
and password are saved locally, so the controller should reconnect when powered
on; **reconnection across service restarts/reboots still needs testing**.

The **SHIELD Controller** system tray app starts when you log in. Open it now with
`shield-controller tray`, or open **SHIELD Controller** from the application menu.
Its icon shows connected (green), ready (blue), waiting (amber), disconnected
(gray), or a driver fault (red). Click it to open the controller window, or
right-click for Pair, Connect, Disconnect and automatic startup controls.
Administrator authorization is requested when changing the system service.

Connect starts the service and allows a previously paired controller to reconnect;
choose Pair for first-time setup. Disconnect stops the controller service.
Quitting the tray leaves the controller service running. Tray startup at desktop
login and controller service startup at boot are independent.

## Use and troubleshoot

```sh
shield-controller status
shield-controller status --json
shield-controller logs
shield-controller stop
shield-controller disable
```

If normal Wi-Fi changes channel, the service recreates only its own controller
AP. Normal Wi-Fi stays under NetworkManager's control. Same-radio AP use shares
airtime, so throughput can change. Connection continuity beyond the original
60-second concurrent test remains to be tested.

The driver exposes normal Linux gamepad and mouse input devices. A separate
desktop helper handles volume keys because some desktops ignore media keys on a
gamepad. Controller audio input and output have also been tested and work on the
maintainer's setup. Rumble has also been confirmed working on that setup.

Configuration is `/etc/shield-controller/config.json`. The default automatically
selects a connected Wi-Fi interface and uses `shield0` for the controller. Set
`"interface": "wlan0"` to choose a specific adapter. Restart the service after edits.
The service will not reuse an existing `shield0` or a separately loaded `ozwpan`.
Stop the earlier experimental test before starting it.

Pairing secrets stay in root-only `/var/lib/shield-controller/network.json`.
WPS opens only when you choose Pair. No packet captures or raw input logs are
recorded by the service. Avoid sharing this state file or authentication captures.

To uninstall from the same release directory:

```sh
sudo python3 packaging/install.py --uninstall
```

Configuration and saved pairing remain unless you also pass `--purge`.
Secure Boot may require enrolling a DKMS signing key using your distribution's
procedure before the module can load.

Report problems on [GitHub Issues](https://github.com/Dewopalis/Open-FatShield/issues).
Include your controller model, distribution, kernel, Wi-Fi adapter,
`shield-controller doctor` output and relevant service logs. Remove personal
network identifiers first.

## Development

```sh
make test
make
python3 packaging/install.py --destdir /tmp/shield-package
```

The staging command copies package files without root privileges or system changes.
After a full installation, `sudo python3 packaging/install.py --app-only` refreshes
the application and launchers without rebuilding or restarting the driver. This
option requires the same driver version to be installed already. Restart the tray
app after updating it; an already-running instance keeps its previous code.

The project is named Open FatShield; the installed command and service retain the
name `shield-controller`, and the kernel module is `ozwpan`.

Contributions and hardware test reports are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
for development checks and the pull request process, or [open an issue](https://github.com/Dewopalis/Open-FatShield/issues/new/choose).
DKMS rebuilds the module for kernel updates; kernel API compatibility still needs
checking. See [design and provenance](docs/design.md) for the driver changes,
protocol findings and test boundaries.

## License

GPL-2.0-only; see [LICENSE](LICENSE). Based on the Linux staging OZWPAN driver and
[devmapal/nvidia-shield-controller-driver](https://github.com/devmapal/nvidia-shield-controller-driver).
Original file copyright notices are retained. New packaging and application code
are also GPL-2.0-only. NVIDIA and SHIELD are trademarks of their respective owners.
