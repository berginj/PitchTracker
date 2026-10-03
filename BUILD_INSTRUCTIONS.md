# PitchTracker Windows Build Instructions

**Last reviewed:** 2026-10-03

These instructions create a local test artifact. They do not authorize release
publication and do not prove clean-machine installation or physical accuracy.

## Prerequisites

- 64-bit Windows 10 or Windows 11.
- Python 3.13 or newer.
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
python scripts\check_public_docs.py
python scripts\check_typing_policy.py
python -m mypy . --no-incremental --show-error-codes
python -m pytest
```

Mypy is required on the canonical Python 3.13 job. The dependency vulnerability
scan remains advisory; record its findings separately.

## Build from a clean committed revision

```powershell
.\build_installer.ps1 -Clean
```

Expected outputs for application version 2.0.0:

- `dist\PitchTracker\PitchTracker.exe`
- `dist\PitchTracker\PitchTrackerWorker.exe`
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe`
- `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe.sha256`

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

## Preserve earlier artifacts with an isolated build

`-Clean` removes the generated `build`, `dist`, and `installer_output` trees.
To retain earlier artifacts, use a fresh ID and output directories instead:

```powershell
$projectRoot = (Get-Location).Path
$sourceRevision = git rev-parse HEAD
$artifactId = "review-$((Get-Date).ToString('yyyyMMdd-HHmmss'))-$($sourceRevision.Substring(0, 7))"
$bundleOutput = Join-Path $projectRoot "dist\$artifactId"
$buildWork = Join-Path $projectRoot "build\$artifactId"
$installerOutput = Join-Path $projectRoot "installer_output\$artifactId"
foreach ($target in @($bundleOutput, $buildWork, $installerOutput)) {
    if (Test-Path -LiteralPath $target) { throw "Choose a new artifact ID: $target" }
}
python -m PyInstaller --clean --distpath $bundleOutput --workpath $buildWork launcher.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
$bundlePath = Join-Path $bundleOutput "PitchTracker"
```

Compile from a newly staged copy of the current `installer.iss`, never from an
old validation copy. Redirect its application sources to the tested bundle and
set `SourceDir` so configuration/assets/docs resolve from the checkout:

```powershell
$stagedScript = Join-Path $buildWork "installer.iss"
$definition = Get-Content -LiteralPath "installer.iss" -Raw
$definition = $definition.Replace('[Setup]', "[Setup]`r`nSourceDir=$projectRoot")
$definition = $definition.Replace('Source: "dist\PitchTracker\', ('Source: "' + $bundlePath + '\'))
$definition | Set-Content -LiteralPath $stagedScript -Encoding utf8
$compileStarted = Get-Date
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/O$installerOutput" $stagedScript
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
. .\scripts\installer_artifact.ps1
$installerFile = Get-FreshInstallerArtifact -DefinitionPath $stagedScript `
    -OutputDirectory $installerOutput -BuiltAfter $compileStarted
$installerHash = (Get-FileHash -LiteralPath $installerFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
"$installerHash  $($installerFile.Name)" | Set-Content -LiteralPath "$($installerFile.FullName).sha256" -Encoding ascii
```

The normal build script's `-SkipPyInstaller` option targets `dist\PitchTracker`;
it does not select an isolated bundle. Retain the staged definition, build logs,
source revision, GUI/worker hashes, dependency versions and smoke-test results
with the isolated artifact. Local compilation and checksum generation do not
sign an installer. Recompute the final checksum after signing before publication.

Use the explicit GUI smoke test with isolated state, without camera discovery or
updater requests:

```powershell
$env:PITCHTRACKER_PACKAGED_DIR = $bundlePath
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest tests\test_gui_smoke.py::test_frozen_gui_workflows_render_and_close
```

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
