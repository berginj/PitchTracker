# PitchTracker Installation Guide

Complete step-by-step instructions for setting up PitchTracker from scratch.

---

## Prerequisites

### Required Hardware
- **2 USB cameras** (identical models recommended)
  - Minimum resolution: 640×480
  - Minimum framerate: 30 FPS
  - Compatible with UVC (USB Video Class) or OpenCV
- **Computer** running Windows 10/11, macOS, or Linux
  - Minimum: 4GB RAM, dual-core processor
  - Recommended: 8GB RAM, quad-core processor for real-time tracking

### Required Software
- **Python 3.10 or later**
  - Download from: https://www.python.org/downloads/
  - **Important for Windows:** Check "Add Python to PATH" during installation

---

## Step 1: Verify Python Installation

Open Command Prompt (Windows) or Terminal (macOS/Linux):

```bash
python --version
```

**Expected output:** `Python 3.10.x` or later

**If this fails on Windows:**
- Try `python3 --version`
- Or `py --version`
- If none work, reinstall Python and check "Add to PATH"

---

## Step 2: Get PitchTracker Code

### Option A: Clone from GitHub (Recommended)

```bash
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
```

### Option B: Download ZIP

1. Go to: https://github.com/berginj/PitchTracker
2. Click "Code" → "Download ZIP"
3. Extract to `C:\Users\<YourName>\App\PitchTracker` (or your preferred location)
4. Open Command Prompt/Terminal in that directory

---

## Step 3: Install Dependencies

### All Platforms

```bash
pip install -r requirements.txt
```

**This installs:**
- OpenCV (computer vision) - ~100 MB, takes 2-5 minutes
- NumPy (numerical computing)
- SciPy (scientific computing)
- PySide6 (GUI framework)
- PyYAML (configuration)
- scikit-learn (pattern detection)
- matplotlib (charts/reports)
- loguru (logging)
- psutil (resource monitoring)
- Other dependencies

### If You Get Permission Errors

**Windows/macOS/Linux:**
```bash
pip install --user -r requirements.txt
```

### If You Have Multiple Python Versions

```bash
python -m pip install -r requirements.txt
```

Or:
```bash
python3 -m pip install -r requirements.txt
```

---

## Step 4: Verify Installation

Run the dependency checker:

```bash
python scripts/check_dependencies.py
```

**Expected output:**
```
Checking PitchTracker dependencies...
----------------------------------------------------------------------
  ✓ opencv-contrib-python
  ✓ numpy
  ✓ scipy
  ✓ PyYAML
  ✓ PySide6
  ✓ scikit-learn
  ✓ matplotlib
  ✓ loguru
  ✓ jsonschema
  ✓ psutil
----------------------------------------------------------------------

✓ All 10 required dependencies are installed!
```

**If dependencies are missing:**
- The script will show exactly which packages need installation
- Follow the instructions to install them

---

## Step 5: Test Camera Access

Run the minimal camera test:

```bash
python test_camera_basic.py
```

**Expected output:**
```
======================================================================
MINIMAL CAMERA TEST
======================================================================

Step 1: Importing cv2...
  SUCCESS - OpenCV version: 4.10.0

Step 2: Importing numpy...
  SUCCESS - NumPy version: 1.26.4

Step 3: Listing available cameras...
  SUCCESS - Found cameras at indices: [0, 1]

Step 4: Testing camera 0...
  SUCCESS - Captured 640x480 frame from camera 0

======================================================================
TEST COMPLETE - All basic functions working!
======================================================================
```

**If no cameras found:**
- Cameras might be in use by another application (close Zoom, Skype, etc.)
- Try unplugging and replugging cameras
- Check Device Manager (Windows) or System Preferences (macOS)

---

## Step 6: Run Full Setup Validator

Run the complete setup validator:

```bash
python setup_validator.py
```

This checks:
- ✓ Python version
- ✓ All dependencies installed
- ✓ Configuration files exist
- ✓ Cameras are accessible
- ✓ Write permissions for recordings

**If all checks pass:** You're ready to use PitchTracker!

---

## Step 7: First-Time Setup

### Launch Setup Wizard

```bash
python launcher.py
```

The Setup Wizard will guide you through:

1. **Camera Selection** - Choose left and right cameras
2. **Camera Calibration** - Capture checkerboard images for stereo calibration
3. **Strike Zone Setup** - Define the strike zone dimensions

### What You'll Need for Calibration

- **Checkerboard pattern** (recommended: 9×6 corners, 30mm squares)
  - Download and print from: `docs/checkerboard_9x6_30mm.pdf`
  - Mount on stiff cardboard or foam board
- **Measure camera baseline** - Distance between lens centers (tape measure)
- **15-20 minutes** for capturing calibration images

---

## Alternative: Run Main Application Directly

If you've already completed setup:

```bash
python main_window.py
```

---

## Troubleshooting

### "No module named cv2"

OpenCV is not installed. Run:
```bash
pip install opencv-contrib-python
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

### "No module named PySide6"

Qt GUI framework is not installed. Run:
```bash
pip install PySide6
```

### Cameras Not Detected

1. **Close other applications** using cameras (Zoom, Skype, Teams)
2. **Check camera connections**:
   - Windows: Device Manager → Imaging Devices
   - macOS: System Preferences → Camera
   - Linux: `ls /dev/video*`
3. **Try different USB ports** (prefer USB 3.0)
4. **Restart computer** to reset camera drivers

### Script Window Flashes and Closes

If you double-click a `.py` file and it closes immediately:
- Open Command Prompt/Terminal first
- Navigate to PitchTracker directory: `cd C:\Users\...\PitchTracker`
- Run the script: `python <script_name>.py`
- This keeps the window open and shows error messages

### Permission Denied Errors

**Windows:**
- Run Command Prompt as Administrator
- Or use `pip install --user -r requirements.txt`

**macOS/Linux:**
- Use `pip install --user -r requirements.txt`
- Or use a virtual environment (see below)

---

## Advanced: Virtual Environment (Recommended)

Using a virtual environment keeps PitchTracker dependencies isolated:

### Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run PitchTracker

```bash
python launcher.py
```

### Deactivate When Done

```bash
deactivate
```

---

## Next Steps

After successful installation:

1. **Read the user guide:** `docs/USER_GUIDE.md` (if exists)
2. **Run the Setup Wizard:** `python launcher.py`
3. **Calibrate your cameras:** See `docs/STEREO_BASELINE_EXPLAINED.md`
4. **Check camera alignment:** See `docs/BASELINE_WORKFLOW.md`
5. **Start tracking pitches!**

---

## Getting Help

**If you encounter issues:**

1. **Check the logs:** `alignment_check_log.txt` (if alignment checker failed)
2. **Run diagnostics:**
   - `python scripts/check_dependencies.py`
   - `python test_camera_basic.py`
   - `python setup_validator.py`
3. **Report issues:** https://github.com/berginj/PitchTracker/issues

**Include in bug reports:**
- Python version: `python --version`
- Operating system: Windows 10, macOS 13, etc.
- Error messages (full text)
- Output from `python scripts/check_dependencies.py`

---

## Summary

```bash
# Quick start commands:
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker
pip install -r requirements.txt
python setup_validator.py
python launcher.py
```

That's it! You're ready to track pitches with stereo vision.
