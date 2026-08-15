# ML Detector Training Guide

**Last reviewed:** 2026-08-11
**Applies to:** v2.0.0 and current `main`

This is the canonical training reference for the current v2 architecture.
The earlier v1.2-era capture/labeling notes are preserved at
[`archive/docs/reference/TRAINING.md`](../../archive/docs/reference/TRAINING.md);
they record historical intent but predate the current recording service and
session-summary schema and should not be followed as current procedure.

---

## Training phase plan

| Phase | Ball type | Goal |
|---|---|---|
| 1 | Marked (dot pattern) | Bootstrap dot-centroid + index-pair detector |
| 2 | Mixed (marked + unmarked) | Validate detector generalization |
| 3 | Unmarked | Seam/texture identification; dots are a fallback |

The marked-ball marker spec is defined in
`contracts-shared/schema/marker_spec.schema.json` and an example instance lives
at `contracts-shared/examples/marker_spec.json`. Record the marker spec path in
session metadata for reproducibility (see REQ.md § 17).

---

## 1 — Capture

Use the dual-camera recording workflow (Coaching Sessions) to capture sessions
under diverse conditions: backgrounds, lighting, speeds, distances, and idle
footage (no ball) to reduce false positives.

**Recommended camera settings** (from `configs/default.yaml`):

- 1920 × 1080 @ 60 fps
- Pixel format: GRAY8 → YUY2 → MJPG (in preference order)
- Manual exposure and gain; fixed white balance or grayscale pipeline

Enable `recording.save_detections: true` in your config to capture per-frame
pixel-coordinate detections alongside the session videos.  The detection JSON is
written next to `manifest.json` in each pitch directory.

Per-session output layout (current v2 recording service):

```
<output_dir>/<session_id>/
├── session_left.avi
├── session_right.avi
├── session_left_timestamps.csv
├── session_right_timestamps.csv
├── session_summary.json          # schema_version "2.0.0"
└── <pitch_id>/
    ├── left.avi
    ├── right.avi
    ├── left_timestamps.csv
    ├── right_timestamps.csv
    ├── observations.json
    └── manifest.json             # schema_version "2.0.0"
```

> **v1.2 note:** REQ.md § 1.4 and § 16.1 contain recording manifest and
> session summary examples with `schema_version "1.0.0"` and `app_version
> "0.2.0"`. Those schemas are superseded. Current manifests use schema version
> `2.0.0`; see `contracts/versioning.py` (`SCHEMA_VERSION`) and
> `MANIFEST_SCHEMA.md`.

---

## 2 — Dataset preparation

Extract frames from a recorded session:

```powershell
python -m record.dataset_prep `
  --video recordings/<session_id>/left.avi `
  --timestamps recordings/<session_id>/session_left_timestamps.csv `
  --out-dir datasets/ball_left `
  --fps 10 `
  --prefix left
```

Output directories:

```
datasets/ball_left/
├── images/
├── labels/          # populated by your labeling tool
├── metadata.csv
└── dataset.yaml     # YOLO-compatible
```

---

## 3 — Labeling

Label the ball with class `ball` (class ID 0).

Recommended tools: **LabelImg** (fast local start) or **CVAT** (team workflows).

Format: YOLO TXT — one file per image, each line:
`<class> <x_center> <y_center> <width> <height>` in normalized units.

For marked-ball sessions also label:
- dot centroids `(u, v)` per frame
- index pair (double-dot) confidence

---

## 4 — Training

Use a lightweight model (YOLOv8-nano or similar) for the speed target
(≤ 4 ms per camera per frame on CPU, per REQ.md § 5.3).

Train on the left-camera dataset first; validate on held-out sessions with new
backgrounds and lighting.

---

## 5 — Validation checklist

- Idle false-positive rate ≤ 1 per second (REQ.md § 5.4)
- Consistent detections through the lane ROI across a real pitch
- No obvious dropouts in the lane or plate ROI
- Phase 1: index-pair detection confidence logged per frame

---

## 6 — Configuration fields that affect detection

| File | Key | Purpose |
|---|---|---|
| `configs/default.yaml` | `camera.*` | Resolution, fps, pixel format, exposure, gain |
| `configs/default.yaml` | `stereo.*` | Baseline and focal length for triangulation |
| `configs/default.yaml` | `tracking.*` | Gate distance, minimum track length |
| `configs/default.yaml` | `metrics.*` | Confidence-check bounds |
| `configs/roi.json` | `lane` | Pitch-lane detection rectangle |
| `configs/roi.json` | `plate` | Strike zone + batter box rectangle |

Keep `baseline_ft` and `focal_length_px` current after any recalibration so
that 3D estimates remain meaningful.

---

## 7 — Team workflow and data submission

Use a shared naming convention: `<date>_<location>_<lighting>_<pitcher-id>`.

Include in each submission zip:
- `session_left.avi`, `session_right.avi`
- timestamp CSVs
- `session_summary.json`
- `marker_spec.json` (Phase 1 and 2)

Maintain a manifest of uploads (session ID, location, lighting, ball type, schema version).

See also:
- [ML Training Data Strategy](../../ML_TRAINING_DATA_STRATEGY.md)
- [ML Training Implementation Guide](../../ML_TRAINING_IMPLEMENTATION_GUIDE.md)
- [ML Quick Reference](../../ML_QUICK_REFERENCE.md)
- [Cloud Submission Guide](../../CLOUD_SUBMISSION_GUIDE.md)
