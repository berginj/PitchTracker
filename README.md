# PitchTracker Quick Start (Windows)

## For End Users (Coaches)

If you received the installer, see [README_INSTALL.md](README_INSTALL.md) for installation instructions.

**Quick Install:**
1. Download `PitchTracker-Setup-v1.0.0.exe`
2. Run installer (requires Windows 10+)
3. Launch from Start Menu
4. Complete 6-step Setup Wizard

The application includes automatic updates - you'll be notified when new versions are available.

---

## For Developers

### Setup
```powershell
cd C:\Users\bergi\App\PitchTracker
.\setup.ps1
```

## Run
```powershell
.\run.ps1 -Backend uvc
```

If you only have an internal camera, use:
```powershell
.\run.ps1 -Backend opencv
```

## Notes
- Use the `Refresh Devices` button to populate cameras.
- The calibration wizard runs after startup; follow the steps or use Skip to reach the UI.
- Configure ROIs and strike zone settings before recording.
- Camera mount files are in `3dModels/`.
- Recording creates a session folder with per-pitch subfolders (left/right videos, timestamps, manifest).
- Recording also writes continuous session videos: `session_left.avi`, `session_right.avi`, and timestamp CSVs in the session folder.

## ARM Auto Config
On Windows ARM (e.g., Snapdragon), the UI auto-selects `configs/snapdragon.yaml` when no `--config` is provided. Use `--config configs/default.yaml` (or another file) to override.

## Tests
```powershell
python -m pytest
```

To run optional clip-based detection tests:
```powershell
$env:PITCHTRACKER_TEST_VIDEO="C:\path\to\left.avi"
python -m pytest tests/test_video_clip.py
```

## Completed Features
- PySide6 UI with in-process pipeline service and recording/replay
- Lane + plate ROI calibration with strike-zone 3x3 overlay
- Classical detector with ROI cropping and optional ONNX ML detector
- Recording bundles with manifest, timestamps, and config snapshot
- Plate plane calibration tool with logging

## ML Detector
Set these in `configs/default.yaml` to use an ONNX model:
- `detector.type: ml`
- `detector.model_path: path\to\model.onnx`
- `detector.model_input_size: [640, 640]`
- `detector.model_conf_threshold: 0.25`
- `detector.model_class_id: 0`
- `detector.model_format: yolo_v5`

Quick validation:
```powershell
python -m detect.validate_ml --model models\ball.onnx --image samples\frame.png
```

## Building the Installer

To create a distributable installer for end users:

```powershell
# Install build tools (one-time setup)
pip install pyinstaller

# Download and install Inno Setup 6 from:
# https://jrsoftware.org/isdl.php

# Build installer (creates PitchTracker-Setup-v1.0.0.exe)
.\build_installer.ps1 -Clean
```

**Output:** `installer_output\PitchTracker-Setup-v1.0.0.exe` (~100-150 MB)

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for detailed build documentation including:
- Prerequisites and dependencies
- Bundle size optimization
- Version management
- Testing checklist
- Distribution via GitHub Releases

**Auto-Update Mechanism:** The installer includes automatic update checking via GitHub Releases API. When you publish a new release with a tagged version (e.g., `v1.0.1`) and attach the installer as an asset, users will be notified and can install updates with one click.

---

## Documentation

### Core Documentation
- [README.md](README.md) - This quick start guide
- [README_INSTALL.md](README_INSTALL.md) - End-user installation guide
- [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) - Building the installer
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [REQ.md](REQ.md) - Requirements and specifications
- [MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md) - Session and pitch manifest schemas (v1.2.0)

### Architecture & Design
- [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) - System design principles
- [REFACTORING_PROGRESS.md](REFACTORING_PROGRESS.md) - Pipeline service refactoring

### Pitch Tracking V2
- **[PITCH_TRACKING_V2_GUIDE.md](PITCH_TRACKING_V2_GUIDE.md)** - Complete integration guide
- **[PITCH_TRACKING_V2_SUMMARY.md](PITCH_TRACKING_V2_SUMMARY.md)** - Quick V1 vs V2 comparison
- **[PITCH_TRACKING_V2_INTEGRATION.md](PITCH_TRACKING_V2_INTEGRATION.md)** - Integration changes
- **[PITCH_TRACKING_ANALYSIS.md](PITCH_TRACKING_ANALYSIS.md)** - V1 issues analysis (12 critical bugs)
- **[V2_TEST_RESULTS.md](V2_TEST_RESULTS.md)** - Test results (8/8 passing)
- **[V2_CLEANUP_TASKS.md](V2_CLEANUP_TASKS.md)** - Optional enhancements

**Key V2 Improvements:**
- Zero data loss (was ~16 frames/pitch in V1)
- Thread-safe operations
- Accurate timing (<33ms error vs ±330ms in V1)
- Pre-roll buffering that actually works
- Data validation and false trigger filtering

### ML Training & Automation (NEW)
- **[ML_QUICK_REFERENCE.md](ML_QUICK_REFERENCE.md)** - Quick start guide for ML features ⭐ START HERE
- **[CLOUD_SUBMISSION_GUIDE.md](CLOUD_SUBMISSION_GUIDE.md)** - Package data for cloud upload ⭐ EXPORT GUIDE
- **[ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md)** - 18-month automation roadmap
- **[ML_TRAINING_IMPLEMENTATION_GUIDE.md](ML_TRAINING_IMPLEMENTATION_GUIDE.md)** - Week 1 implementation details
- **[CLOUD_SUBMISSION_SCHEMA.md](CLOUD_SUBMISSION_SCHEMA.md)** - Technical specification (full vs telemetry-only)

**Current Status (v1.2.0):**
- ✅ Detection export (pixel coordinates, confidence scores)
- ✅ Observation export (3D trajectory points)
- ✅ Frame extraction (key frames as PNG)
- ✅ Calibration export (geometry, intrinsics, ROIs)
- ✅ Performance metrics in manifest

**Automation Roadmap:**
- 6 months: Ball detector model (eliminate HSV tuning)
- 9 months: Field segmentation (auto-detect ROIs)
- 12 months: Batter pose estimation (auto-calculate strike zone)
- 18 months: Self-calibration (reduce setup to <2 min)

**Enable ML Data Collection:**
```yaml
# configs/default.yaml
recording:
  save_detections: true       # Export detection JSON
  save_observations: true     # Export 3D observations
  save_training_frames: true  # Save key frames
  frame_save_interval: 5      # Frame sampling rate
```

**Validate Export:**
```powershell
python test_ml_data_export.py "recordings\session-2026-01-16_001"
```

**Export for Cloud Submission:**
```powershell
# Full package (videos + telemetry) - 4-5 GB, enables all 5 models
python export_ml_submission.py --session-dir "recordings\session-2026-01-16_001" --output "ml-submission-full.zip" --type full --pitcher-id "anonymous-123"

# Telemetry-only (no videos) - 50-100 MB, enables 2 of 5 models, privacy-preserving
python export_ml_submission.py --session-dir "recordings\session-2026-01-16_001" --output "ml-submission-telemetry.zip" --type telemetry_only --pitcher-id "anonymous-123" --reason privacy_preserving
```
