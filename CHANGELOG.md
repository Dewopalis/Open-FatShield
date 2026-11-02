# Changes

## 0.1.0-alpha.1

* Package the modernized OZWPAN driver as DKMS sources.
* Add a system service that keeps normal NetworkManager Wi-Fi connected and runs
  the SHIELD AP on a separate interface on the same 2.4 GHz channel.
* Save a local controller network identity; open WPS enrollment explicitly.
* Initialize gamepad/mouse input and convert touchpad reports to relative motion.
* Add a per-user volume helper, desktop menu and start/stop/pair/boot commands.
* Include installer/uninstaller, 19 regression tests and CI.

Verified: successful live concurrent transport test with 1,286 input events;
module builds against CachyOS 7.3.1 and 6.18.55 LTS headers; automated tests pass.
Pending: installed-service live test, saved pairing reconnect, boot, roaming and
long-duration validation. This release is experimental.
