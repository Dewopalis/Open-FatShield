# Help and compatibility

## Tested setup

| Component | Tested |
| --- | --- |
| Controller | Original Wi-Fi SHIELD Controller, USB ID `0955:7210` |
| Distribution | CachyOS (Arch based), systemd and NetworkManager |
| Wireless driver | Intel iwlwifi, managed station + AP on the same 2.4 GHz channel |
| Kernel | 7.3.1 runtime; 6.18.55 LTS compile check only |
| Controller audio | Input and output tested and working by the maintainer |
| Rumble | Tested and working by the maintainer |
| Desktop volume/mute | Tested with WirePlumber `wpctl` |
| Desktop app | PySide6 Qt tray/window; offscreen smoke test |

This is a small experimental compatibility list, not a guarantee that other
hardware cannot work. Please submit successful hardware reports as well as bugs.
The Bluetooth SHIELD Controller (2017) uses a different transport and is outside
this driver. Controller audio input and output are confirmed working on the tested
setup; rumble has also been confirmed working on that setup.

## First checks

1. Install matching headers for the **running** kernel, then follow the README.
2. Connect normal Wi-Fi to a 2.4 GHz network. The service does not change its band.
3. Run `open-fatshield doctor` and `open-fatshield status`.
4. Open `open-fatshield gui`, choose Pair, unplug USB and hold the NVIDIA button
   until it flashes. The WPS window lasts two minutes.
5. If it fails, inspect `open-fatshield logs`. Reading system logs may require
   `sudo journalctl -u open-fatshield.service -n 100 --no-pager` on your distribution.

## Common questions

**Why is it waiting for Wi-Fi?** The controller needs a 2.4 GHz AP. This release
shares the connected station's channel and waits on 5/6 GHz or without a normal
Wi-Fi connection. Your adapter must support managed + AP concurrently.

**Why does it refuse `shield0` or an already-loaded module?** Another controller
session may still own those resources. Stop an earlier test or service before
starting this one. The app avoids taking over somebody else's interface/module.

**Why is there no tray icon?** Install PySide6 and run `open-fatshield gui`.
On GNOME, a tray extension may be needed; the app also provides a regular window.
The launcher appears as **Open FatShield** in the application menu.

**Why do the buttons work but not volume?** The desktop helper needs a logged-in
user and a working `wpctl get-volume @DEFAULT_AUDIO_SINK@`. Run the app as your
normal user. Only service-changing actions request administrator authorization.

**Do I need to pair every time?** Credentials are saved locally. Connect starts
the service with the same network identity. Reconnect and boot
behavior need further testing. Reconnection with saved pairing was observed during
the rename upgrade; controller power-cycle and host reboot behavior remain
untested. Report what happens on your hardware.

**Does quitting the tray disconnect the controller?** No. Use Disconnect to stop
the controller service. Quit only closes the tray app. Tray startup at login and
service startup at boot are separate settings.

## Get help or report compatibility

Use the [issue forms](https://github.com/Dewopalis/Open-FatShield/issues/new/choose).
Include the controller model, distro/kernel, Wi-Fi adapter/driver and the result
of `open-fatshield doctor`. Describe what you tried and the observed result.
Remove personal network identifiers from logs. Do not upload pairing credentials,
the saved `network.json` file or authentication captures.

For exploitable security flaws, use [private vulnerability reporting](https://github.com/Dewopalis/Open-FatShield/security/advisories/new).
