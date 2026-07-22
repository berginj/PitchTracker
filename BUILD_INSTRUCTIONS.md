# PitchTracker Windows Build Instructions

**Last reviewed:** 2026-07-22

These instructions create a local test artifact. They do not authorize release
publication and do not prove clean-machine installation or physical accuracy.

## Prerequisites

- 64-bit Windows 10 or Windows 11.
- Python 3.11 or 3.12.
- Repository dependencies from `requirements-dev.txt`.
- Inno Setup 6 at its standard installation path.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Install Inno Setup from its official site and verify `ISCC.exe` is available at
`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.

## Run the protected software gates

```powershell
flake8 . --count --statistics
python scripts\check_file_length.py
python scripts\sync_schema.py --check
python -m pytest
```

Mypy and the dependency vulnerability scan are currently advisory in CI. Record
their findings instead of describing them as blocking gates.

## Build from a clean committed revision

```powershell
.\build_installer.ps1 -Clean
```

Expected outputs for application version 2.0.0:

- `dist\PitchTracker\PitchTracker.exe`
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe`

The filename comes from `installer.iss`. Version changes must update
`contracts/versioning.py`, `installer.iss`, `updater.py`, the changelog, and
release documentation together.

## Local artifact checks

1. Record `git rev-parse HEAD` and confirm the worktree is clean.
2. Launch `dist\PitchTracker\PitchTracker.exe` on the build machine.
3. Compute the installer checksum:

   ```powershell
   Get-FileHash installer_output\PitchTracker-Setup-v2.0.0-stereo.exe -Algorithm SHA256
   ```

4. Retain build logs, the exact dependency environment, filename, size, and
   checksum.

## Clean-machine smoke testing

Before publication, test the installer outside the development checkout on the
supported Windows matrix. Verify:

- install and first launch;
- Setup & Calibration entry;
- simulator/no-camera behavior;
- writable configuration, logs, calibration, and recording paths;
- update-check behavior;
- uninstall and reinstall behavior;
- data retention/removal expectations; and
- Windows security prompts and exact failures.

Do not attach an installer to a release until these results and the SHA-256 are
reviewed. Track smoke tests in
[issue #11](https://github.com/berginj/PitchTracker/issues/11).

## Publication

Follow [GITHUB_RELEASE_INSTRUCTIONS.md](GITHUB_RELEASE_INSTRUCTIONS.md). Never
replace an existing release asset silently; publish a new version with explicit
provenance and limitations.
