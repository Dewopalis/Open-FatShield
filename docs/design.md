# Design and provenance

The kernel module restores the staging OZWPAN USB-over-Wi-Fi host controller.
It binds to a dedicated virtual AP and carries USB traffic directly over Ethernet
type `0x892e`; the controller network does not require DHCP, NAT or a bridge.
Normal Wi-Fi remains a managed station on the same radio and channel.

The root system service creates `shield0`, temporarily marks only that interface
unmanaged in NetworkManager, starts hostapd with the SHIELD-compatible P2P vendor
advertisement, and loads `ozwpan`. It saves a random SSID/password and the AP MAC
locally. Pair explicitly opens WPS push-button enrollment. Credential persistence
is implemented; reconnect and boot behavior require live validation.

An ownership record and bounded subprocess waits allow cleanup after failures.
The service checks normal Wi-Fi's connection UUID, BSSID and channel and removes
its AP when these change. It does not activate/deactivate normal Wi-Fi connections.
The service waits for a suitable 2.4 GHz connection at boot. Interface ownership
checks refuse to overwrite another session's interface, module or NM rule.

The unprivileged desktop agent uses uaccess permissions limited to the virtual
SHIELD input devices. It handles volume/mute through the logged-in user's wpctl.
Gamepad and mouse events are exposed by the kernel and work without that helper.
The service performs the read-only HID input-report initialization that was
required to start live report streaming in the experiments.

## Source origins

* Linux staging OZWPAN, restored and patched by
  [devmapal/nvidia-shield-controller-driver](https://github.com/devmapal/nvidia-shield-controller-driver),
  inspected at commit `168539f4534b91c3f545f1249fad45cbf5d864d4`.
  Original Ozmo copyright and GPL notices are retained in the driver sources.
* [NVIDIA's Android hid-nvidia-blake.c](https://github.com/LineageOS/android_kernel_nvidia_shieldtablet/blob/cm-12.0/drivers/hid/hid-nvidia-blake.c)
  and local wireless captures informed the SHIELD touchpad interpretation.
* [Syniurge/ShieldControllerWinDriver](https://github.com/Syniurge/ShieldControllerWinDriver)
  was inspected as an open-source Windows USB reference. This project does not
  distribute NVIDIA Windows binaries or claim to have decompiled their driver.

REA packet tooling and TShark supported the investigation. Private packet captures,
authentication exchanges, personal network identifiers and machine diagnostics
are deliberately excluded from this release.

## Driver changes

* Modern timekeeping, unaligned access, platform/class, hrtimer and access_ok APIs.
* Linearize receive skbs rather than sleeping allocations in packet receive context.
* Fix descriptor completion length, fragmented replies, bounds, no-progress replies
  and error propagation. The original completion overrun caused a real kernel fault
  during early testing; this fix enabled stable enumeration in subsequent tests.
* Replace a trailing one-byte request payload with a flexible array and enforce
  protocol payload limits before allocation.
* Convert SHIELD report 2 touch coordinates into relative mouse deltas, suppress
  contact/release jumps and preserve the physical mouse button bits.
* Initialize input through HIDIOCGINPUT reads for reports 1 and 2. Opening hidraw
  and reading these reports together enabled streaming; their individual causal
  contributions have not been isolated. No undocumented HID writes are used.

## Validation boundaries

Repeated isolated tests verified wireless enumeration and input. The final
concurrent test recorded 1,286 button/axis/mouse events, working desktop volume,
and normal Wi-Fi remaining on its original connection. These tests used a
temporary transport script, before packaging the service.

The installed DKMS module and system service subsequently paired the controller
and received live input while normal Wi-Fi stayed connected. An initial external
pair command timed out despite starting WPS: hostapd's PrivateTmp namespace hid
the client's reply socket. Both sides now use the shared root-only runtime
directory via hostapd_cli's `-s` option. A read-only status query verified this fix.

The maintainer subsequently tested controller audio input and output and confirmed
both work on the tested setup. This is a live user test result; the automated tests
do not exercise audio, and other audio setups remain unvalidated.

The maintainer also confirmed rumble works on the tested setup. This is a live
user test result; the automated tests do not exercise rumble.

The PySide6 tray app polls status asynchronously, offers Pair/Connect/Disconnect
and boot controls, and uses the CLI/Polkit boundary for privileged actions.
Only one tray instance runs per desktop user. Its local activation socket is
restricted to that user. The controller service remains independent of the tray.

Automated tests exercise the real descriptor callback, request serializer and
touchpad transform with AddressSanitizer/UndefinedBehaviorSanitizer harnesses,
plus report reads, media mapping, network/config validation, process timeouts,
owned-resource recovery and staged installation. The optional Qt smoke test checks
the connected-state window offscreen. These do not substitute for live desktop
interaction, reboot, reconnect, roaming or long-duration tests. The restored kernel
driver has not received a complete security audit. Use this as experimental code.
