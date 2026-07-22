# PitchTracker Release Publication Checklist

**Last reviewed:** 2026-07-22

## Current state

- Latest public tag/release: `v2.0.0`.
- The `v2.0.0` release has no installer asset.
- `main` contains evidence, replay, setup, CI, and documentation hardening beyond
  that tag.
- A local installer build exists in project history, but clean-machine smoke
  testing and public checksum verification remain incomplete.

Do not recreate, overwrite, or attach an unverified asset to `v2.0.0`. Publish a
new semantic version after the checklist below is complete.

## Preconditions

- [ ] Application, installer, updater, changelog, and documentation versions agree.
- [ ] Required CI jobs pass on the exact release commit.
- [ ] The installer is built from a clean tagged revision.
- [ ] Windows 10 and Windows 11 clean-machine smoke tests pass.
- [ ] Installer filename, size, and SHA-256 are recorded and independently checked.
- [ ] Release notes state the physical-validation and supported-hardware boundary.
- [ ] No private recordings, calibration artifacts, secrets, or development caches
      are present in the package.

## Create a new release

1. Choose the next semantic version; do not reuse an existing tag.
2. Update all version sources and documentation in one reviewed change.
3. Merge the release change through protected CI.
4. Tag the exact merge commit and push the annotated tag.
5. Build and smoke-test the installer from that tag.
6. Prepare release notes and a checksum file.
7. Publish with GitHub CLI or the GitHub release UI.

The repository helper enforces an existing semantic-version tag, refuses an
existing release, and verifies the installer against the supplied checksum:

```powershell
.\create_github_release.ps1 `
  -Tag vX.Y.Z `
  -InstallerPath installer_output\PitchTracker-Setup-vX.Y.Z-stereo.exe `
  -ChecksumPath installer_output\PitchTracker-Setup-vX.Y.Z-stereo.exe.sha256 `
  -NotesFile release_notes.md
```

Example only, using placeholders intentionally:

```powershell
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z `
  --verify-tag `
  --title "PitchTracker vX.Y.Z" `
  --notes-file release_notes.md `
  installer_output\PitchTracker-Setup-vX.Y.Z-stereo.exe `
  installer_output\PitchTracker-Setup-vX.Y.Z-stereo.exe.sha256
```

## Required release-note content

- Exact source commit and tag.
- Installer filename and SHA-256.
- Supported Windows versions and clean-machine test matrix.
- Hardware qualification state and operating envelope.
- Explicit statement that automated tests do not validate physical accuracy.
- Known issues, migration notes, and data-location/uninstall behavior.
- Links to `CURRENT_STATUS.md`, `ROADMAP.md`, and the changelog.

## Post-publication verification

1. Download both assets from the public release.
2. Recompute the installer SHA-256 and compare it to the published checksum.
3. Run one final clean-machine install/launch/uninstall smoke test.
4. Confirm the updater sees the intended version and installer asset.
5. Update `docs/CURRENT_STATUS.md` and `docs/VERSION_ALIGNMENT.md` with the exact
   public evidence.

Never silently replace an asset. If an artifact is wrong, preserve provenance,
publish a corrected version, and explain the superseded artifact explicitly.
