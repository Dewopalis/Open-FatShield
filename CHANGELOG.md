# Changes

## 0.1.0-alpha.1

* Package the modernized OZWPAN driver as DKMS sources.
* Add a system service that keeps normal NetworkManager Wi-Fi connected and runs
  the SHIELD AP on a separate interface on the same 2.4 GHz channel.
* Save a local controller network identity; open WPS enrollment explicitly.
* Initialize gamepad/mouse input and convert touchpad reports to relative motion.
* Add a per-user volume helper, Qt status tray/window and start/stop/pair/boot commands.
* Fix pairing replies across the service's private temporary directory with shared
  runtime sockets. The earlier command could time out after successfully starting WPS.
* Include installer/uninstaller, 21 regression tests, an optional offscreen Qt smoke
  test and CI.

Verified: successful live concurrent transport test with 1,286 input events;
module builds against CachyOS 7.3.1 and 6.18.55 LTS headers; automated tests pass.
Verified: installed DKMS module and service pairing/input; offscreen Qt window.
Pending: desktop tray interaction, saved pairing reconnect, boot, roaming and
long-duration validation. This release is experimental.
