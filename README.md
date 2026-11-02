# SHIELD Controller Linux

Wireless Linux support for the original NVIDIA SHIELD Controller (2014/2015,
USB ID `0955:7210`). This controller uses Wi-Fi, rather than Bluetooth.

**Experimental alpha.** Gamepad buttons, sticks, touchpad mouse and desktop
volume/mute have been tested wirelessly while normal Wi-Fi remains connected.
The installed service has also been tested live. Saved-pairing reconnection and
boot behavior still need validation.
This is a community project, unaffiliated with NVIDIA.

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

## Install

On Arch/CachyOS, install prerequisites and the header package matching your running
kernel (for example `linux-cachyos-headers`):

```sh
sudo pacman -S --needed python dkms hostapd iw networkmanager wireplumber polkit pyside6 base-devel clang llvm
```

From a downloaded release or this repository:

```sh
git clone https://github.com/Dewopalis/shield-controller-linux.git
cd shield-controller-linux
sudo python3 packaging/install.py
shield-controller doctor
shield-controller pair
```

Run the last two commands as your normal desktop user. Pair opens a two-minute
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
gamepad. There is no audio streaming/headset or rumble support claim.

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

Report problems on [GitHub Issues](https://github.com/Dewopalis/shield-controller-linux/issues).
Include your controller model, distribution, kernel, Wi-Fi adapter, `shield-controller
doctor` output and relevant service logs. Remove personal network identifiers first.

## Development

```sh
make test
make
python3 packaging/install.py --destdir /tmp/shield-package
```

The staging command copies package files without root privileges or system changes.
After a full installation, `sudo python3 packaging/install.py --app-only` refreshes
the application and launchers without rebuilding or restarting the driver.
DKMS rebuilds the module for kernel updates; kernel API compatibility still needs
checking. See [design and provenance](docs/design.md) for the driver changes,
protocol findings and test boundaries.

## License

GPL-2.0-only; see [LICENSE](LICENSE). Based on the Linux staging OZWPAN driver and
[devmapal/nvidia-shield-controller-driver](https://github.com/devmapal/nvidia-shield-controller-driver).
Original file copyright notices are retained. New packaging and application code
are also GPL-2.0-only. NVIDIA and SHIELD are trademarks of their respective owners.
