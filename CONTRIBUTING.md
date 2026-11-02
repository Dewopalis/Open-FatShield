# Contributing to Open FatShield

Bug reports, hardware compatibility results, documentation fixes and code changes
are welcome. Start with [the support guide](SUPPORT.md) for live troubleshooting.

## Development

Clone the repo and create a branch:

```sh
git clone https://github.com/Dewopalis/Open-FatShield.git open-fatshield
cd open-fatshield
git switch -c your-change
make test
python3 packaging/install.py --destdir /tmp/open-fatshield-stage
```

Tests need Python and a C compiler with AddressSanitizer/UndefinedBehaviorSanitizer.
Building the module with `make` also needs headers for the running kernel and the
matching GCC or Clang/LLVM toolchain. To check the optional GUI with PySide6:

```sh
python3 tests/tray_smoke.py
```

This renders offscreen and does not change networking or the controller service.
The installer staging command also makes no system changes.

## Pull requests

Open a pull request against `main`. CI must pass, conversations must be resolved,
and the branch must be up to date before merging. Keep changes focused and explain
the behavior, why it is needed, checks performed and any untested assumptions.
Add meaningful regression coverage for driver fixes; avoid tests that only repeat
the implementation. Clearly separate compile checks from live hardware testing.

Preserve existing copyright notices and license contributions under GPL-2.0-only.
Do not commit packet captures, pairing keys, local state files or build artifacts.
Keep normal Wi-Fi under NetworkManager's control; changes that could interrupt it
need an explicit description and careful testing.

## Releases

Git tags identify downloadable source snapshots. Version `0.2.0-alpha.1` uses
`open-fatshield` for the installed command and service and includes a migration
from the original `shield-controller` installation. The earlier `0.1.0-alpha.1-r2`
snapshot was a documentation refresh of application version `0.1.0-alpha.1`.
Releases include Debian, RPM and Arch DKMS/app packages, plus source and SHA-256
checksums. See [the package workflow guide](docs/packages.md) for builds and tag
publication. Kernel-specific precompiled modules are not provided.
