# Changes

## 0.2.0-alpha.1

* Add GitHub Actions builds for Debian, RPM and Arch installable DKMS/app packages,
  release uploads, source archives and checksums on matching version tags.
* Add native package lifecycle hooks and configuration-file preservation.

* Rename the installed command, service, desktop launchers, Python package, DKMS
  registration and configuration/state/runtime directories to Open FatShield names.
* Add a legacy upgrade path that preserves pairing, configuration and the service
  startup state, and retires the old command, helpers and DKMS registration.
* Update all current installation, GUI and troubleshooting instructions.
* Retain the `ozwpan` kernel module and existing controller network identity.

The underlying driver is unchanged. All 28 automated tests pass. Live migration
installed the renamed DKMS package, retired the legacy command, and started the
new service with the controller reported connected; the renamed GUI/helper ran.
Controller power-cycle reconnection and host reboot startup remain untested.

## Additional hardware validation

The maintainer confirmed controller audio input and output both work on the tested
setup. Update the compatibility documentation accordingly. This is a test result,
with no driver or application code changes.

The maintainer also confirmed rumble works on the tested setup. Update the
compatibility documentation and release notes; no code changes are needed.

## 0.1.0-alpha.1-r2 (source package refresh)

* Rename the project documentation to Open FatShield and update repository links.
* Add direct source download, release notes and SHA-256 checksum links.
* Separate archive and Git installation instructions and document GUI startup.
* Clarify source-package requirements and application-only update behavior.
* Bundle support, contribution, security and design documentation with installation.
* Add issue forms, a pull request template and project status/compatibility guidance.

Driver/application version remains `0.1.0-alpha.1`; no driver or application runtime changes.

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
