# Ball Detector Training Guide

This guide explains how to capture data, prepare a dataset, and train a ball detector for this repo.

## 1) Capture Guidelines
- Use the dual capture tool to record left/right video and timestamps.
- Collect diverse sessions: different backgrounds, lighting, speeds, and distances.
- Include idle footage (no ball) to reduce false positives.

Recommended capture settings (from `configs/default.yaml`):
- 1920x1080 @ 60 fps
- Pixel format: GRAY8 > YUY2 > MJPG
- Manual exposure and gain (disable auto WB).

## 2) Dataset Preparation
We start with single-camera training to simplify labeling. Use the left camera first.

Extract frames + metadata:
```bash
python -m record.dataset_prep \
  --video recordings/left.avi \
  --timestamps recordings/left_timestamps.csv \
  --out-dir datasets/ball_left \
  --fps 10 \
  --prefix left
```

This creates:
- `datasets/ball_left/images/` (frames)
- `datasets/ball_left/labels/` (empty labels folder)
- `datasets/ball_left/metadata.csv` (frame timestamps)
- `datasets/ball_left/dataset.yaml` (YOLO format)

## 3) Labeling
Label the ball with a single class `ball` (class id 0).

Recommended tools:
- LabelImg (fast start, local)
- CVAT (team workflows)

Label format: YOLO (txt files per image with `class x_center y_center width height` in normalized units).

## 4) Training (Starter Recipe)
Use a lightweight model for speed (YOLOv8-nano or similar).

Basic expectations:
- Train on the left dataset first.
- Validate on held-out sessions (new backgrounds, lighting).

## 5) Validation Checklist
- Idle false positives: <= 1 per second.
- Consistent detections for a real pitch across frames.
- No obvious dropouts in the lane ROI.

## 6) Configuration Guidance
These config fields impact detection and tracking:

`configs/default.yaml`:
- `camera.*`: resolution, fps, pixfmt, exposure, gain
- `stereo.*`: baseline and focal length (for triangulation)
- `tracking.*`: gate distance, min track length
- `metrics.*`: bounds for confidence checks

`configs/roi.json`:
- `lane`: rectangle for pitch lane
- `plate`: rectangle for strike zone + batter box area

Tip: Keep `baseline_ft` and `focal_length_px` up to date after calibration so 3D estimates are meaningful.

## 7) Team Workflow
- Keep a shared naming convention for recordings (date, location, lighting).
- Store raw recordings and labels in a shared location.
- Track dataset version and changes in a simple changelog.
