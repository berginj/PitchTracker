# Creating GitHub Release v1.0.0

This document provides instructions for creating the GitHub release manually if the automated script doesn't work.

## Option 1: Using the Script (Recommended)

```powershell
# Authenticate GitHub CLI (first time only)
gh auth login

# Run the release script
.\create_github_release.ps1
```

## Option 2: Manual Creation via GitHub Web Interface

1. **Go to GitHub Releases:**
   - Navigate to: https://github.com/berginj/PitchTracker/releases
   - Click "Create a new release" or "Draft a new release"

2. **Tag Settings:**
   - **Choose a tag:** Select `v1.0.0` from dropdown (already pushed)
   - **Target:** main branch

3. **Release Title:**
   ```
   PitchTracker v1.0.0 - Initial Release
   ```

4. **Release Description:**
   Copy the contents from `create_github_release.ps1` (the $releaseNotes variable)
   Or use this simplified version:

   ```markdown
   # PitchTracker v1.0.0 - Initial Release

   🎉 First official release of PitchTracker!

   ## Installation
   1. Download `PitchTracker-Setup-v1.0.0.exe` below
   2. Run installer (requires Windows 10+ 64-bit)
   3. Launch from Start Menu
   4. Connect dual USB cameras
   5. Complete 6-step Setup Wizard
   6. Start tracking!

   ## Features
   - Dual-camera stereo vision pitch tracking
   - Real-time 3D trajectory reconstruction
   - Strike zone analysis
   - Session recording with metrics
   - Stereo calibration wizard
   - ML detector support (ONNX)
   - Auto-update mechanism

   ## System Requirements
   - Windows 10/11 (64-bit)
   - 8 GB RAM (16 GB recommended)
   - Dual USB 3.0 cameras
   - 2 GB free disk space

   ## Documentation
   - `BUILD_INSTRUCTIONS.md` - Building from source
   - `README_INSTALL.md` - Installation guide
   - `DEPLOYMENT_IMPROVEMENTS.md` - Deployment details

   **Full Changelog**: https://github.com/berginj/PitchTracker/commits/v1.0.0
   ```

5. **Upload Installer:**
   - Drag and drop `installer_output\PitchTracker-Setup-v1.0.0.exe` (83 MB)
   - Or click "Attach binaries" and select the file

6. **Publish:**
   - Check "Set as the latest release"
   - Click "Publish release"

## Option 3: Using gh CLI Directly

```powershell
# Authenticate (if not already)
gh auth login

# Create release with installer
gh release create v1.0.0 `
  --title "PitchTracker v1.0.0 - Initial Release" `
  --notes-file release_notes.md `
  installer_output\PitchTracker-Setup-v1.0.0.exe
```

Where `release_notes.md` contains the release description.

## Verification

After creating the release:

1. **Check Release Page:**
   - Go to: https://github.com/berginj/PitchTracker/releases/tag/v1.0.0
   - Verify installer is attached
   - Verify description displays correctly

2. **Test Auto-Update:**
   - Install v1.0.0 using the installer
   - Modify `updater.py` to set `CURRENT_VERSION = "0.9.0"`
   - Launch PitchTracker
   - Should see update notification for v1.0.0

3. **Test Download:**
   - Click installer download link
   - Verify file downloads (83 MB)
   - Verify file is not corrupted

## Troubleshooting

### "gh: command not found"
Install GitHub CLI from: https://cli.github.com/

### "authentication required"
Run: `gh auth login` and follow prompts

### "tag v1.0.0 does not exist"
The tag was already pushed. Verify with:
```powershell
git tag -l
git ls-remote --tags origin
```

### "installer not found"
Build the installer first:
```powershell
.\build_installer.ps1
```

### "release already exists"
Delete the existing release:
```powershell
gh release delete v1.0.0
```
Or edit it:
```powershell
gh release edit v1.0.0
```

## Next Steps After Release

1. **Announce Release:**
   - Share link with coaches
   - Update README.md with download link
   - Post on social media (if applicable)

2. **Monitor Downloads:**
   ```powershell
   gh release view v1.0.0
   ```

3. **Prepare for v1.0.1:**
   - Update `CURRENT_VERSION` in `updater.py`
   - Update `AppVersion` in `installer.iss`
   - Make code changes
   - Rebuild installer
   - Create new release

---

**Questions?** Check BUILD_INSTRUCTIONS.md or DEPLOYMENT_IMPROVEMENTS.md
