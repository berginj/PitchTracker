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
- Use the “Refresh Devices” button to populate cameras.
- Configure ROIs and strike zone settings before recording.
- Camera mount files are in `3d models/`.

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
