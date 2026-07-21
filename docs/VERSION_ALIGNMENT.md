# Version and Release Alignment

**Last reviewed:** 2026-07-21
**Status:** code/build metadata aligned; refreshed release publication pending

## Current identity

| Purpose | Value | Source |
|---|---|---|
| Internal application version | `2.0.0` | `contracts/versioning.py` |
| Durable schema version | `1.2.0` | `contracts/versioning.py` |
| Installer application version | `2.0.0` | `installer.iss` |
| Installer filename | `PitchTracker-Setup-v2.0.0-stereo.exe` | `installer.iss` |
| Update comparison version | `2.0.0` | `updater.py` |
| Published GitHub tag/release | `v2.0.0` | GitHub Releases |

The `-stereo` suffix identifies the installer artifact and documentation theme;
semantic version comparisons use `2.0.0`.

## Current release gap

The published `v2.0.0` release has no attached installer asset, and `main` has
additional evidence/replay/setup-hardening commits beyond the release tag. A
clean installer was built locally from commit `40158c1`, but it is not a public
release artifact until it passes clean-machine smoke testing and is published
with its checksum.

## Release checklist

- [x] Runtime, installer, updater, and current docs use version 2.0.0.
- [x] Full automated suite recorded: 1,263 passed, 32 skipped, 0 failed.
- [x] Clean PyInstaller and Inno Setup build completed from `40158c1`.
- [ ] Installer smoke-tested on a clean Windows 10 machine.
- [ ] Installer smoke-tested on a clean Windows 11 machine.
- [ ] Built source commit and SHA-256 recorded in release notes.
- [ ] Installer attached to a refreshed GitHub release.
- [ ] Downloaded asset checksum independently reverified.
- [ ] Hardware/accuracy limitations copied into release notes.

## Change procedure

1. Update `contracts/versioning.py`, `installer.iss`, and `updater.py` together.
2. Update `CHANGELOG.md`, `README.md`, `CURRENT_STATUS.md`, and this file.
3. Run CI-equivalent gates and the full suite.
4. Build from a clean committed revision.
5. Smoke-test outside the development checkout.
6. Publish the tag, release notes, installer, and checksum.

Do not replace an existing public asset without retaining provenance and making
the changed checksum explicit.
