# PitchTracker Quick Start (Windows)

## Setup
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

## Documentation

### Core Documentation
- [README.md](README.md) - This quick start guide
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [REQ.md](REQ.md) - Requirements and specifications

### Architecture & Design
- [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) - System design principles
- [REFACTORING_PROGRESS.md](REFACTORING_PROGRESS.md) - Pipeline service refactoring

### Pitch Tracking V2 (NEW)
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
