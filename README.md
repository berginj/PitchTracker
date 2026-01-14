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
