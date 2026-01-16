# PitchTracker Build Instructions

Guide for building the PitchTracker installer from source.

## Prerequisites

### Required Software

1. **Python 3.9+** with pip
   ```powershell
   python --version  # Should be 3.9 or later
   ```

2. **PyInstaller** (for creating executable)
   ```powershell
   pip install pyinstaller
   ```

3. **Inno Setup 6** (for creating installer)
   - Download from: https://jrsoftware.org/isdl.php
   - Install to default location: `C:\Program Files (x86)\Inno Setup 6\`

4. **UPX** (optional, for compression)
   - Download from: https://upx.github.io/
   - Extract upx.exe to a directory in PATH
   - Or place in project root directory

### Python Dependencies

Install all project dependencies:

```powershell
pip install -r requirements.txt
```

### Assets

Create an application icon (optional but recommended):

```powershell
# Create assets directory
mkdir assets

# Add icon file
# Place a 256x256 PNG as assets/icon.ico
# Or use an .ico converter
```

---

## Build Process

### Quick Build (All Steps)

```powershell
# Clean build (recommended for release)
.\build_installer.ps1 -Clean

# Or without cleaning
.\build_installer.ps1
```

**Output:** `installer_output\PitchTracker-Setup-v1.0.0.exe`

---

### Step-by-Step Build

#### 1. Build PyInstaller Bundle

```powershell
# Use the optimized spec file
python -m PyInstaller --clean launcher.spec
```

**Output:** `dist\PitchTracker\` directory with executable and dependencies

**Expected size:** ~150-200 MB (before Inno Setup compression)

**Verify:**
```powershell
# Test the executable
.\dist\PitchTracker\PitchTracker.exe
```

#### 2. Build Inno Setup Installer

```powershell
# Compile installer script
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**Output:** `installer_output\PitchTracker-Setup-v1.0.0.exe`

**Expected size:** ~100-150 MB (compressed)

---

## Build Configurations

### Full Build (Default)

```powershell
.\build_installer.ps1
```

Includes:
- PyInstaller bundling
- Inno Setup installer
- All files and dependencies

### Skip PyInstaller (Use Existing Bundle)

```powershell
.\build_installer.ps1 -SkipPyInstaller
```

Useful when:
- dist\ folder already exists
- Only updating installer settings
- Testing installer without rebuilding

### Skip Inno Setup (Just Bundle)

```powershell
.\build_installer.ps1 -SkipInnoSetup
```

Useful for:
- Testing the PyInstaller build
- Debugging bundle issues
- Creating portable version

### Clean Build

```powershell
.\build_installer.ps1 -Clean
```

Removes:
- `build/` directory
- `dist/` directory
- `installer_output/` directory

Recommended for:
- Release builds
- After significant code changes
- When troubleshooting build issues

---

## Optimizing Bundle Size

### Current Optimizations (launcher.spec)

1. **Exclude unused modules:**
   - matplotlib, pandas, jupyter, tkinter
   - Testing frameworks (pytest, unittest)
   - Documentation tools (sphinx)

2. **Enable UPX compression:**
   - Compresses executables
   - Reduces final size by ~30%

3. **Strip debug symbols:**
   - Removes debugging information
   - Reduces size without affecting functionality

### Further Optimization

If bundle is still too large:

1. **Remove unused OpenCV modules:**
   ```python
   # In launcher.spec, add to excludes:
   excludes = [
       'cv2.aruco',  # If not using ArUco markers
       'cv2.dnn',    # If not using deep learning
   ]
   ```

2. **Use --onefile mode** (not recommended):
   ```powershell
   # Creates single .exe (slower startup, no size benefit for installer)
   pyinstaller --onefile launcher.py
   ```

3. **Profile imports:**
   ```powershell
   # Find large dependencies
   python -m PyInstaller --log-level=DEBUG launcher.spec 2>&1 | findstr "MB"
   ```

---

## Version Management

### Updating Version Number

Update in multiple locations:

1. **installer.iss** (line 6):
   ```inno
   #define AppVersion "1.0.1"
   ```

2. **launcher.py** (if version is shown in UI):
   ```python
   APP_VERSION = "1.0.1"
   ```

3. **README files** (document the version)

### Git Tagging for Releases

```powershell
# Create version tag
git tag -a v1.0.1 -m "Release version 1.0.1"

# Push tag to origin
git push origin v1.0.1
```

---

## Testing the Installer

### Test Checklist

Before distributing, test on a **clean Windows machine**:

- [ ] Installer runs without errors
- [ ] Progress bar shows correctly
- [ ] Files installed to correct location
- [ ] Start Menu shortcut works
- [ ] Desktop shortcut works (if selected)
- [ ] Application launches successfully
- [ ] Cameras detected (if connected)
- [ ] Setup Wizard completes
- [ ] Coaching App functions
- [ ] Uninstaller removes all files

### Testing in Virtual Machine

Recommended: Test in VMware/VirtualBox with clean Windows 10/11

```powershell
# Snapshot VM before testing
# Install PitchTracker
# Test all functionality
# Uninstall and verify cleanup
# Revert VM snapshot for next test
```

---

## Distribution

### GitHub Releases

1. **Create release on GitHub:**
   ```powershell
   # Tag version (if not done)
   git tag -a v1.0.0 -m "Release 1.0.0"
   git push origin v1.0.0
   ```

2. **Upload installer:**
   - Go to GitHub → Releases → Create New Release
   - Select tag (v1.0.0)
   - Upload: `PitchTracker-Setup-v1.0.0.exe`
   - Add release notes

3. **Update auto-updater URL:**
   - Ensure `updater.py` points to correct repository
   - Users will get update notifications

### Direct Distribution

If distributing directly (not via GitHub):

1. **Upload to cloud storage:**
   - Google Drive, Dropbox, OneDrive
   - Share link with coaches

2. **Provide checksums:**
   ```powershell
   # Generate SHA256 checksum
   Get-FileHash .\installer_output\PitchTracker-Setup-v1.0.0.exe -Algorithm SHA256
   ```

3. **Include installation guide:**
   - Share README_INSTALL.md
   - Provide support contact

---

## Troubleshooting Build Issues

### PyInstaller Fails

**Error:** `ImportError: No module named ...`

**Solution:**
```powershell
# Add to hiddenimports in launcher.spec
hiddenimports = ['missing_module']
```

---

**Error:** `RecursionError: maximum recursion depth exceeded`

**Solution:**
```powershell
# Increase recursion limit
python -m PyInstaller --recursion-limit=5000 launcher.spec
```

---

**Error:** `UnicodeDecodeError` during build

**Solution:**
```powershell
# Set environment variable
$env:PYTHONIOENCODING = "utf-8"
python -m PyInstaller launcher.spec
```

---

### Inno Setup Fails

**Error:** `ISCC.exe not found`

**Solution:**
```powershell
# Install Inno Setup from https://jrsoftware.org/isdl.php
# Or specify path in build script
```

---

**Error:** `Source file not found: dist\PitchTracker\...`

**Solution:**
```powershell
# Run PyInstaller first
python -m PyInstaller launcher.spec

# Then compile installer
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

---

### Bundle Size Too Large

**Current size:** ~300 MB

**Target size:** ~150 MB

**Steps:**
1. Check what's included:
   ```powershell
   # List all files and sizes
   Get-ChildItem -Path dist\PitchTracker -Recurse | Sort-Object Length -Descending | Select-Object -First 20
   ```

2. Exclude large unused modules (see "Optimizing Bundle Size")

3. Enable UPX compression (if not already):
   ```python
   # In launcher.spec
   exe = EXE(..., upx=True, ...)
   coll = COLLECT(..., upx=True, ...)
   ```

4. Remove test data and examples:
   ```powershell
   # Before building installer, remove from dist/
   Remove-Item -Path dist\PitchTracker\tests -Recurse -Force
   ```

---

## CI/CD Integration (Future)

### GitHub Actions Workflow

Create `.github/workflows/build-installer.yml`:

```yaml
name: Build Installer

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: pip install -r requirements.txt

    - name: Install PyInstaller
      run: pip install pyinstaller

    - name: Build with PyInstaller
      run: python -m PyInstaller launcher.spec

    - name: Install Inno Setup
      run: choco install innosetup

    - name: Build Installer
      run: & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

    - name: Upload Release Asset
      uses: actions/upload-release-asset@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        upload_url: ${{ github.event.release.upload_url }}
        asset_path: ./installer_output/PitchTracker-Setup-v${{ github.ref_name }}.exe
        asset_name: PitchTracker-Setup-${{ github.ref_name }}.exe
        asset_content_type: application/x-msdownload
```

---

## Support

If you encounter build issues:

1. Check this guide for troubleshooting steps
2. Review PyInstaller documentation: https://pyinstaller.org/
3. Review Inno Setup documentation: https://jrsoftware.org/ishelp/
4. Submit issue with build logs to GitHub repository

---

**Last Updated:** 2026-01-16
**Build System Version:** 1.0.0
