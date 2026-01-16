# PitchTracker - Quick Start Guide

## Installation

### Prerequisites
```powershell
# Install Python dependencies
pip install PySide6 numpy opencv-python pyyaml
```

## Running PitchTracker

### Option 1: Unified Launcher (Recommended)
Launch the main application with role selector:
```powershell
python launcher.py
```

This shows a clean interface with two options:
- **🔧 Setup & Calibration** - For system configuration
- **⚾ Coaching Sessions** - For daily coaching use

### Option 2: Direct Launch
Launch specific applications directly:

**Setup Wizard:**
```powershell
python test_setup_wizard.py
```

**Coaching App:**
```powershell
python test_coaching_app.py
```

## First Time Setup

1. **Launch Setup Wizard** (via launcher or `python test_setup_wizard.py`)

2. **Complete all 6 steps:**
   - **Step 1:** Camera Setup - Select left and right cameras
   - **Step 2:** Stereo Calibration - Capture checkerboard images
   - **Step 3:** ROI Configuration - Draw lane and plate regions
   - **Step 4:** Detector Tuning - Configure detection mode
   - **Step 5:** System Validation - Verify configuration
   - **Step 6:** Export Package - Generate setup report

3. **Launch Coaching App** (via launcher or `python test_coaching_app.py`)

## Using the Coaching App

1. Click "Start Session"
2. Select pitcher and adjust settings (batter height, ball type)
3. Click OK to start capture and recording
4. Throw pitches - metrics appear in real-time
5. Click "End Session" when done
6. Review session summary

## Workflow

```
┌─────────────────────┐
│   Launch PitchTracker   │
│     (launcher.py)    │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌──────────┐
│ Setup   │   │ Coaching │
│ Wizard  │   │   App    │
└─────────┘   └──────────┘
    │             │
    │ (one-time)  │ (daily)
    │             │
    ▼             ▼
[Configure]   [Track Pitches]
```

## File Locations

**Configuration:**
- `configs/default.yaml` - Main configuration
- `calibration/stereo_calibration.npz` - Calibration data
- `rois/shared_rois.json` - Lane and plate ROIs

**Generated Data:**
- `data/sessions/<session_name>/` - Session recordings
- `setup_report.txt` - Setup summary report

## Troubleshooting

### No cameras found
- Check USB connections
- Ensure cameras have unique serial numbers
- Try OpenCV backend: `python launcher.py` and select cameras by index

### Calibration fails
- Ensure checkerboard is visible in both cameras
- Capture at least 10 image pairs
- Try different angles and distances
- Check lighting conditions

### No pitch detection
- Verify ROIs are configured correctly
- Check detector settings in Step 4
- Ensure proper lighting
- Verify ball type matches configuration

### Import errors
```powershell
# Install missing dependencies
pip install PySide6 numpy opencv-python pyyaml
```

## Support

For issues or questions:
1. Check configuration in `configs/default.yaml`
2. Review ROIs in `rois/shared_rois.json`
3. Re-run Setup Wizard validation (Step 5)
4. Check console output for error messages

## Version

**Current Version:** 1.0.0

**Components:**
- Setup Wizard - Complete (6 steps)
- Coaching App - Complete (integrated with pipeline)
- Unified Launcher - Complete
