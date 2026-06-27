# Creating GitHub Release v2.0.0

This document provides manual release instructions if `create_github_release.ps1`
does not work.

## Option 1: Using The Script

```powershell
gh auth login
.\create_github_release.ps1
```

## Option 2: Manual Creation Via GitHub

1. Go to https://github.com/berginj/PitchTracker/releases.
2. Click "Draft a new release".
3. Choose or create tag `v2.0.0`.
4. Set the title to `PitchTracker v2.0.0`.
5. Attach `installer_output\PitchTracker-Setup-v2.0.0-stereo.exe`.
6. Include release notes that state this is a controlled facility pilot build
   and that accuracy validation is still in progress.

Suggested notes:

```markdown
# PitchTracker v2.0.0

Canonical pilot build for controlled facility deployments.

## Install
1. Download `PitchTracker-Setup-v2.0.0-stereo.exe`.
2. Run the installer on Windows 10/11.
3. Complete Setup Doctor before coaching use.
4. Use a fixed dual-camera rig and the pilot hardware checklist.

## Included
- Service-oriented pipeline runtime with `PipelineOrchestrator`
- Setup Doctor and rig profile workflow
- Stereo capture, detection, recording, review, and analysis
- Pattern detection and pitcher profile workflows
- Local recording artifacts with manifests and summaries

## Known Limitations
- Accuracy validation against reference equipment is pending.
- Setup requires a trained operator and controlled camera placement.
- Best suited to fixed facility/academy deployments.
- Cloud/mobile/TAG production integrations are deferred.

## Documentation
- `README.md`
- `docs/CURRENT_STATUS.md`
- `docs/VERSION_ALIGNMENT.md`
- `docs/HARDWARE_PROFILE.md`
- `docs/VELOCITY_VALIDATION_PROTOCOL.md`

Full changelog: https://github.com/berginj/PitchTracker/blob/main/CHANGELOG.md
```

## Option 3: Using `gh` Directly

```powershell
gh release create v2.0.0 `
  --title "PitchTracker v2.0.0" `
  --notes-file release_notes.md `
  installer_output\PitchTracker-Setup-v2.0.0-stereo.exe
```

## Verification

After creating the release:

1. Verify the release page exists at
   `https://github.com/berginj/PitchTracker/releases/tag/v2.0.0`.
2. Download the installer and confirm the filename is
   `PitchTracker-Setup-v2.0.0-stereo.exe`.
3. Smoke-test the installer on a clean Windows 10/11 machine.
4. Record the test result in `docs/CURRENT_STATUS.md` or release notes.

## Troubleshooting

### `gh: command not found`

Install GitHub CLI from https://cli.github.com/.

### `authentication required`

Run:

```powershell
gh auth login
```

### `tag v2.0.0 does not exist`

Create and push it:

```powershell
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

### `installer not found`

Build the installer first:

```powershell
.\build_installer.ps1 -Clean
```

### `release already exists`

Edit or delete through GitHub UI, or use:

```powershell
gh release edit v2.0.0
```

---

**Questions?** Check `BUILD_INSTRUCTIONS.md` and `docs/VERSION_ALIGNMENT.md`.
