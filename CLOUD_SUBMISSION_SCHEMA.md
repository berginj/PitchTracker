# Cloud Submission Schema for ML Training

## Overview

This document defines the contract for packaging and submitting PitchTracker data to cloud services for ML model training. Two submission variants are supported:

1. **Full Package** - Videos + all ML training data (maximum ML capability)
2. **Telemetry-Only** - JSON metadata without videos (lightweight, privacy-preserving)

**Purpose:** Enable submission to cloud-based ML training pipelines while maintaining flexibility around video sharing.

---

## Submission Variants

### Variant 1: Full Package (with Videos)

**Use Cases:**
- Training ball detector models (REQUIRED)
- Training field segmentation models (REQUIRED)
- Training batter pose estimation models (REQUIRED)
- Visual verification of trajectories
- Annotation tool ground truth generation
- Quality assurance and debugging

**Size:** ~4-5 GB per session (20 pitches)

**Why Video is Required:**
- **Ball detector:** Needs raw frames showing ball in varied positions, lighting, backgrounds
- **Field segmentation:** Needs frames showing field boundaries, pitcher mound, plate, backstop
- **Batter pose:** Needs frames with batter in stance for keypoint detection
- **Annotation:** Human annotators need visual frames to label ground truth
- **Verification:** Validates trajectory calculations against visual evidence

**What's Included:**
- ✅ Session videos (full continuous recording)
- ✅ Pitch videos (individual pitch clips with pre/post-roll)
- ✅ Key frames (PNG at critical moments)
- ✅ All detections (pixel coordinates, confidence)
- ✅ All observations (3D trajectory points)
- ✅ Calibration metadata (geometry, intrinsics, ROIs)
- ✅ Performance metrics
- ✅ Manifests and summaries

### Variant 2: Telemetry-Only (without Videos)

**Use Cases:**
- Self-calibration model training (video NOT required)
- Trajectory model training (video NOT required)
- Physics model validation (video NOT required)
- Performance analysis and statistics
- Privacy-preserving submissions (no visual player data)
- Lightweight data collection (reduced bandwidth/storage)

**Size:** ~50-100 MB per session (20 pitches)

**Why Video is NOT Required:**
- **Self-calibration:** Uses stereo correspondences (2D pixel pairs) + 3D points
- **Trajectory models:** Uses 3D observations with timestamps
- **Physics validation:** Uses 3D positions and velocities
- **Privacy:** No visual recording of players or facility

**What's Included:**
- ✅ All detections (pixel coordinates, confidence) - NO frames
- ✅ All observations (3D trajectory points)
- ✅ Calibration metadata (geometry, intrinsics, ROIs)
- ✅ Performance metrics
- ✅ Manifests and summaries
- ❌ Session videos
- ❌ Pitch videos
- ❌ Key frame images

**Trade-offs:**
- ✅ 50x smaller file size
- ✅ Faster upload
- ✅ Privacy-preserving (no player visuals)
- ❌ Cannot train visual models (ball detector, segmentation, pose)
- ❌ Cannot generate annotations
- ❌ Cannot verify trajectories visually

---

## Full Package Schema

### Directory Structure

```
ml-submission-{session-id}-full.zip
├── submission_manifest.json          # Submission metadata
├── session/
│   ├── manifest.json                 # Session manifest
│   ├── session_summary.json          # Session summary
│   ├── session_left.avi              # Full left camera video
│   ├── session_right.avi             # Full right camera video
│   ├── session_left_timestamps.csv
│   ├── session_right_timestamps.csv
│   └── calibration/                  # Calibration metadata
│       ├── stereo_geometry.json
│       ├── intrinsics_left.json
│       ├── intrinsics_right.json
│       └── roi_annotations.json
└── pitches/
    ├── pitch-001/
    │   ├── manifest.json             # Pitch manifest (with performance_metrics)
    │   ├── left.avi                  # Pitch video clip
    │   ├── right.avi
    │   ├── left_timestamps.csv
    │   ├── right_timestamps.csv
    │   ├── detections/               # Ball detections
    │   │   ├── left_detections.json
    │   │   └── right_detections.json
    │   ├── observations/             # 3D trajectory
    │   │   └── stereo_observations.json
    │   └── frames/                   # Key frames (PNG)
    │       ├── left/
    │       │   ├── pre_roll_00001.png
    │       │   ├── uniform_00005.png
    │       │   ├── pitch_00015_first.png
    │       │   └── ...
    │       └── right/
    │           └── (same)
    ├── pitch-002/
    │   └── (same structure)
    └── ...
```

### Submission Manifest (submission_manifest.json)

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.2.0",
  "submission_id": "ml-submission-20260116-123456",
  "submission_type": "full",
  "created_utc": "2026-01-16T12:34:56Z",
  "session": {
    "session_id": "session-2026-01-16_001",
    "started_utc": "2026-01-16T12:00:00Z",
    "ended_utc": "2026-01-16T12:30:00Z",
    "pitch_count": 20
  },
  "source": {
    "app": "PitchTracker",
    "rig_id": "rig-001",
    "location": "Indoor Facility A",
    "pitcher_id": "player-anonymous-123",
    "operator": "coach-456"
  },
  "data_manifest": {
    "videos": {
      "session_videos": true,
      "pitch_videos": true,
      "key_frames": true
    },
    "telemetry": {
      "detections": true,
      "observations": true,
      "calibration": true,
      "performance_metrics": true
    }
  },
  "size_bytes": 4294967296,
  "checksum_sha256": "abc123...",
  "intended_use": [
    "ball_detector_training",
    "field_segmentation_training",
    "pose_estimation_training",
    "trajectory_model_training",
    "self_calibration_training"
  ],
  "privacy": {
    "player_consent": true,
    "anonymized": true,
    "retention_days": 730
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Submission schema version |
| `app_version` | string | Yes | PitchTracker version used |
| `submission_id` | string | Yes | Unique submission identifier |
| `submission_type` | string | Yes | "full" or "telemetry_only" |
| `created_utc` | string | Yes | ISO 8601 submission timestamp |
| `session.session_id` | string | Yes | Source session identifier |
| `session.started_utc` | string | Yes | Session start time |
| `session.ended_utc` | string | Yes | Session end time |
| `session.pitch_count` | int | Yes | Number of pitches included |
| `source.app` | string | Yes | Source application name |
| `source.rig_id` | string | No | Unique rig identifier |
| `source.location` | string | No | Recording location |
| `source.pitcher_id` | string | No | Anonymous pitcher ID |
| `source.operator` | string | No | Operator/coach ID |
| `data_manifest.videos.*` | boolean | Yes | Which video types included |
| `data_manifest.telemetry.*` | boolean | Yes | Which telemetry types included |
| `size_bytes` | int | Yes | Total package size |
| `checksum_sha256` | string | Yes | Package integrity checksum |
| `intended_use` | array[string] | Yes | ML use cases this data supports |
| `privacy.player_consent` | boolean | Yes | Player consent obtained |
| `privacy.anonymized` | boolean | Yes | Player data anonymized |
| `privacy.retention_days` | int | Yes | Data retention period |

---

## Telemetry-Only Package Schema

### Directory Structure

```
ml-submission-{session-id}-telemetry.zip
├── submission_manifest.json          # Submission metadata
├── session/
│   ├── manifest.json                 # Session manifest
│   ├── session_summary.json          # Session summary
│   └── calibration/                  # Calibration metadata
│       ├── stereo_geometry.json
│       ├── intrinsics_left.json
│       ├── intrinsics_right.json
│       └── roi_annotations.json
└── pitches/
    ├── pitch-001/
    │   ├── manifest.json             # Pitch manifest (with performance_metrics)
    │   ├── detections/               # Ball detections (NO frames)
    │   │   ├── left_detections.json
    │   │   └── right_detections.json
    │   └── observations/             # 3D trajectory
    │       └── stereo_observations.json
    ├── pitch-002/
    └── ...
```

### Submission Manifest (submission_manifest.json)

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.2.0",
  "submission_id": "ml-submission-20260116-123456",
  "submission_type": "telemetry_only",
  "created_utc": "2026-01-16T12:34:56Z",
  "session": {
    "session_id": "session-2026-01-16_001",
    "started_utc": "2026-01-16T12:00:00Z",
    "ended_utc": "2026-01-16T12:30:00Z",
    "pitch_count": 20
  },
  "source": {
    "app": "PitchTracker",
    "rig_id": "rig-001",
    "location": "Indoor Facility A",
    "pitcher_id": "player-anonymous-123",
    "operator": "coach-456"
  },
  "data_manifest": {
    "videos": {
      "session_videos": false,
      "pitch_videos": false,
      "key_frames": false
    },
    "telemetry": {
      "detections": true,
      "observations": true,
      "calibration": true,
      "performance_metrics": true
    }
  },
  "size_bytes": 52428800,
  "checksum_sha256": "def456...",
  "intended_use": [
    "trajectory_model_training",
    "self_calibration_training"
  ],
  "privacy": {
    "player_consent": true,
    "anonymized": true,
    "retention_days": 730
  },
  "telemetry_only_reason": "privacy_preserving"
}
```

**Additional Field:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `telemetry_only_reason` | string | No | Reason for omitting videos ("privacy_preserving", "bandwidth", "storage") |

---

## ML Training Capabilities by Variant

### Full Package Enables

| ML Model | Training | Annotation | Verification | Notes |
|----------|----------|------------|--------------|-------|
| Ball Detector | ✅ Required | ✅ Required | ✅ Visual | Needs frames with ball visible |
| Field Segmentation | ✅ Required | ✅ Required | ✅ Visual | Needs frames showing field |
| Batter Pose | ✅ Required | ✅ Required | ✅ Visual | Needs frames with batter |
| Trajectory Models | ✅ Optional | ❌ N/A | ✅ Visual | Can use telemetry-only |
| Self-Calibration | ✅ Optional | ❌ N/A | ✅ Visual | Can use telemetry-only |

### Telemetry-Only Enables

| ML Model | Training | Annotation | Verification | Notes |
|----------|----------|------------|--------------|-------|
| Ball Detector | ❌ Not possible | ❌ Not possible | ❌ No visual | Requires frames |
| Field Segmentation | ❌ Not possible | ❌ Not possible | ❌ No visual | Requires frames |
| Batter Pose | ❌ Not possible | ❌ Not possible | ❌ No visual | Requires frames |
| Trajectory Models | ✅ Sufficient | ❌ N/A | ⚠️ Numeric only | Uses 3D observations |
| Self-Calibration | ✅ Sufficient | ❌ N/A | ⚠️ Numeric only | Uses stereo correspondences |

**Key Insight:** Telemetry-only enables 2 of 5 automation models (40% of roadmap). Full package enables all 5 models (100% of roadmap).

---

## Video Requirement Analysis

### When Video is REQUIRED

**1. Ball Detector Training**
- **Why:** Model must learn to detect ball from raw pixels across varied conditions
- **Alternative:** None - this is a visual recognition task
- **Impact:** Without this model, HSV tuning remains manual forever

**2. Field Segmentation Training**
- **Why:** Model must segment field boundaries from visual scenes
- **Alternative:** Manual ROI drawing remains required
- **Impact:** Without this model, 10-minute ROI setup remains manual

**3. Batter Pose Estimation**
- **Why:** Model must detect batter keypoints from visual frames
- **Alternative:** Manual strike zone measurement remains required
- **Impact:** Without this model, 10-minute per-batter setup remains manual

**Total Impact of Omitting Video:** 3 of 5 automation models cannot be trained. Setup time reduction limited to 25% instead of 95%.

### When Video is NOT Required

**4. Trajectory Model Training**
- **Why:** Uses 3D observations (X, Y, Z, t) not visual data
- **Data Needed:** stereo_observations.json (3D points + timestamps)
- **Video Benefit:** Visual verification only, not training requirement

**5. Self-Calibration Training**
- **Why:** Uses stereo correspondences (2D left/right pixel pairs) + 3D triangulation
- **Data Needed:** detections JSON (pixel coordinates) + observations JSON (3D points)
- **Video Benefit:** Visual verification only, not training requirement

---

## Privacy Considerations

### Full Package Privacy Concerns

**Sensitive Data in Videos:**
- Player faces (identifiable in some camera angles)
- Facility branding and layout
- Other individuals in background
- Proprietary training methods

**Mitigation Strategies:**
1. **Player Consent:** Explicit consent for video sharing
2. **Anonymization:** Remove or blur faces in key frames
3. **Field-Only Cropping:** Extract only field region, exclude backgrounds
4. **Retention Limits:** Auto-delete after training complete

### Telemetry-Only Privacy Benefits

**No Visual Data:**
- ✅ No player faces or identifying features
- ✅ No facility visuals
- ✅ No background individuals
- ✅ Only numeric coordinates and timestamps

**Remaining Identifying Info:**
- ⚠️ Pitcher biomechanics (potentially identifying from trajectory patterns)
- ⚠️ Facility geometry (calibration metadata)

**Recommendation:** For maximum privacy, use telemetry-only unless visual models are critical priority.

---

## File Format Specifications

### Videos

**Format:** AVI (MJPG codec)
**Resolution:** 1920x1080 @ 60fps (typical)
**Color:** Grayscale (GRAY8) or RGB
**Size:** ~100 MB per pitch clip, ~2 GB per session

### Key Frames

**Format:** PNG (lossless)
**Resolution:** Original camera resolution
**Color:** Grayscale or RGB
**Naming:** `{type}_{index:05d}.png`
**Size:** ~500 KB per frame

### Detection JSON

**Format:** JSON with array of detection objects
**Size:** ~10 KB per pitch
**Schema:** See MANIFEST_SCHEMA.md

### Observation JSON

**Format:** JSON with array of observation objects
**Size:** ~50 KB per pitch
**Schema:** See MANIFEST_SCHEMA.md

### Calibration JSON

**Format:** JSON with calibration parameters
**Size:** ~5 KB per session
**Schema:** See MANIFEST_SCHEMA.md

---

## Export Utilities

### Command-Line Export

```bash
# Full package export
python export_ml_submission.py \
  --session-dir "recordings/session-2026-01-16_001" \
  --output "ml-submission-full.zip" \
  --type full \
  --pitcher-id "anonymous-123" \
  --location "Indoor Facility A"

# Telemetry-only export
python export_ml_submission.py \
  --session-dir "recordings/session-2026-01-16_001" \
  --output "ml-submission-telemetry.zip" \
  --type telemetry_only \
  --pitcher-id "anonymous-123" \
  --location "Indoor Facility A" \
  --reason privacy_preserving
```

### Programmatic Export

```python
from export_ml_submission import create_ml_submission

# Full package
create_ml_submission(
    session_dir=Path("recordings/session-2026-01-16_001"),
    output_path=Path("ml-submission-full.zip"),
    submission_type="full",
    source={
        "rig_id": "rig-001",
        "location": "Indoor Facility A",
        "pitcher_id": "anonymous-123",
    },
    privacy={
        "player_consent": True,
        "anonymized": True,
        "retention_days": 730,
    },
)

# Telemetry-only
create_ml_submission(
    session_dir=Path("recordings/session-2026-01-16_001"),
    output_path=Path("ml-submission-telemetry.zip"),
    submission_type="telemetry_only",
    source={
        "rig_id": "rig-001",
        "location": "Indoor Facility A",
        "pitcher_id": "anonymous-123",
    },
    privacy={
        "player_consent": True,
        "anonymized": True,
        "retention_days": 730,
    },
    telemetry_only_reason="privacy_preserving",
)
```

---

## Cloud API Contract

### Upload Endpoint

**URL:** `POST /api/ml-submissions`

**Headers:**
```
Content-Type: multipart/form-data
x-api-key: {api_key}
```

**Body:**
```
submission_manifest: (JSON file)
data_package: (ZIP file)
```

**Response (Success):**
```json
{
  "status": "accepted",
  "submission_id": "ml-submission-20260116-123456",
  "received_utc": "2026-01-16T12:35:00Z",
  "size_bytes": 4294967296,
  "estimated_processing_hours": 24
}
```

**Response (Error):**
```json
{
  "status": "rejected",
  "error": "invalid_schema",
  "message": "submission_manifest.json missing required field: session.pitch_count",
  "details": {...}
}
```

### Status Check Endpoint

**URL:** `GET /api/ml-submissions/{submission_id}/status`

**Response:**
```json
{
  "submission_id": "ml-submission-20260116-123456",
  "status": "processing",
  "progress_pct": 45,
  "started_utc": "2026-01-16T12:35:00Z",
  "estimated_completion_utc": "2026-01-17T12:35:00Z",
  "training_jobs": [
    {
      "model_type": "ball_detector",
      "status": "queued",
      "priority": 1
    },
    {
      "model_type": "trajectory_model",
      "status": "training",
      "progress_pct": 67
    }
  ]
}
```

---

## Recommendations

### For Maximum ML Capability

**Use Full Package when:**
- Training all 5 automation models is priority
- Player consent obtained for video sharing
- Bandwidth and storage available (4-5 GB per session)
- Privacy concerns can be addressed with anonymization

**Result:** Enables 100% of 18-month automation roadmap

### For Privacy-Preserving Collection

**Use Telemetry-Only when:**
- Player prefers no video sharing
- Privacy is highest priority
- Bandwidth or storage limited
- Only trajectory/calibration models needed

**Result:** Enables 40% of automation roadmap (2 of 5 models)

### Hybrid Approach

**Recommended Strategy:**
1. **Weeks 1-3:** Collect full packages to enable all ML models (priority: ball detector)
2. **After ball detector trained:** Switch to telemetry-only for privacy
3. **Periodic full packages:** Collect occasionally to improve visual models

**Result:** Balance privacy with ML capability

---

## Related Documentation

- [MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md) - Complete manifest reference
- [ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md) - 18-month ML roadmap
- [ML_QUICK_REFERENCE.md](ML_QUICK_REFERENCE.md) - Quick start guide
- [CHANGELOG.md](CHANGELOG.md) - Version history (v1.2.0 ML features)
