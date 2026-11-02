Open FatShield 0.2.0-alpha.1 — renamed command/service and installable packages.

Download a `.deb`, `.rpm`, or Arch `.pkg.tar.zst` package below, or the source
archive. SHA256SUMS covers every download. See [package installation instructions](https://github.com/Dewopalis/Open-FatShield/blob/main/docs/packages.md).

The packages install the app, service and DKMS sources. The kernel module builds
locally for your running kernel; matching headers/devel and the kernel compiler
are still required. Debian/RPM/Arch format builds do not imply runtime hardware
validation on every distribution. Packages are unsigned.

The command is now `open-fatshield`, the service is `open-fatshield.service`, and
the GUI is named Open FatShield. The source installer has a tested migration from
the original `shield-controller` installation, preserving pairing and the prior
service startup state. Existing source-install users must uninstall that version
without `--purge` before switching to native packages; see the linked guide.
No compatibility command alias is installed. The `ozwpan` kernel driver is unchanged.

Gamepad controls, touchpad mouse, volume/mute, controller audio input/output and
rumble are confirmed working on the maintainer's CachyOS/Intel iwlwifi setup with
normal 2.4 GHz Wi-Fi connected. The rename upgrade was tested live: the new service
reported the controller connected using saved pairing, and the renamed GUI/helper
ran. Controller power-cycle reconnect, host reboot, roaming, long-duration use
and other adapters/distributions remain unvalidated.

This is an experimental community alpha, unaffiliated with NVIDIA. The 2017
Bluetooth controller uses a different transport and is outside this project.
Private captures, pairing secrets and machine-specific module binaries are excluded.
