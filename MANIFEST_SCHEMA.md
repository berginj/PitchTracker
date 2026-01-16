# Manifest Schema Documentation

## Overview

PitchTracker generates JSON manifest files for both sessions and individual pitches. These manifests contain metadata about recordings, trajectories, strike zone analysis, and (optionally) ML training metrics.

**Schema Version:** 1.2.0
**Last Updated:** 2026-01-16

---

## Session Manifest

**Location:** `{session_dir}/manifest.json`

**Purpose:** Describes a recording session with references to session-level videos and summaries.

### Schema

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.2.0",
  "rig_id": null,
  "created_utc": "2026-01-16T12:34:56Z",
  "pitch_id": "session-2026-01-16_001-pitch-020",
  "session": "session-2026-01-16_001",
  "mode": "bullpen",
  "measured_speed_mph": 85.5,
  "config_path": "configs/default.yaml",
  "calibration_profile_id": null,
  "session_summary": "session_summary.json",
  "session_summary_csv": "session_summary.csv",
  "session_left_video": "session_left.avi",
  "session_right_video": "session_right.avi",
  "session_left_timestamps": "session_left_timestamps.csv",
  "session_right_timestamps": "session_right_timestamps.csv"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Manifest schema version |
| `app_version` | string | PitchTracker application version |
| `rig_id` | string\|null | Unique rig identifier (future use) |
| `created_utc` | string | ISO 8601 timestamp (UTC) |
| `pitch_id` | string | Last pitch ID in session |
| `session` | string | Session name/ID |
| `mode` | string | Recording mode ("bullpen", "game", etc.) |
| `measured_speed_mph` | float | Manual speed measurement (if provided) |
| `config_path` | string | Path to config file used |
| `calibration_profile_id` | string\|null | Calibration profile ID (future use) |
| `session_summary` | string | Filename of JSON summary |
| `session_summary_csv` | string | Filename of CSV summary |
| `session_left_video` | string | Filename of left camera video |
| `session_right_video` | string | Filename of right camera video |
| `session_left_timestamps` | string | Filename of left timestamps CSV |
| `session_right_timestamps` | string | Filename of right timestamps CSV |

---

## Pitch Manifest

**Location:** `{session_dir}/{pitch_id}/manifest.json`

**Purpose:** Describes a single pitch recording with trajectory analysis, strike zone classification, and optional ML training metrics.

### Schema (v1.2.0)

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.2.0",
  "rig_id": null,
  "created_utc": "2026-01-16T12:35:22Z",
  "pitch_id": "session-2026-01-16_001-pitch-001",
  "t_start_ns": 1234567890000000,
  "t_end_ns": 1234568400000000,
  "is_strike": true,
  "zone_row": 1,
  "zone_col": 1,
  "run_in": 2.3,
  "rise_in": 1.7,
  "measured_speed_mph": 85.5,
  "rotation_rpm": 2200.0,
  "trajectory": {
    "plate_crossing_xyz_ft": [0.5, 2.8, 0.0],
    "plate_crossing_t_ns": 1234568200000000,
    "model": "physics_drag",
    "expected_error_ft": 0.08,
    "confidence": 0.95
  },
  "left_video": "left.avi",
  "right_video": "right.avi",
  "left_timestamps": "left_timestamps.csv",
  "right_timestamps": "right_timestamps.csv",
  "config_path": "configs/default.yaml",
  "performance_metrics": {
    "detection_quality": {
      "stereo_observations": 38,
      "detection_rate_hz": 30.2
    },
    "timing_accuracy": {
      "pre_roll_frames_captured": 15,
      "duration_ns": 510000000,
      "start_ns": 1234567890000000,
      "end_ns": 1234568400000000
    }
  }
}
```

### Field Descriptions

#### Base Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Manifest schema version |
| `app_version` | string | PitchTracker application version |
| `rig_id` | string\|null | Unique rig identifier (future use) |
| `created_utc` | string | ISO 8601 timestamp (UTC) |
| `pitch_id` | string | Unique pitch identifier |

#### Timing

| Field | Type | Description |
|-------|------|-------------|
| `t_start_ns` | int | Pitch start time (nanoseconds, monotonic clock) |
| `t_end_ns` | int | Pitch end time (nanoseconds, monotonic clock) |

**Note:** V2 timing uses first/last detection timestamps for accuracy (<33ms error)

#### Strike Zone Analysis

| Field | Type | Description |
|-------|------|-------------|
| `is_strike` | boolean | True if pitch crosses strike zone |
| `zone_row` | int | Strike zone row (0-2: top, middle, bottom) |
| `zone_col` | int | Strike zone column (0-2: inside, middle, outside) |

**Strike Zone Grid:**
```
      Inside  Middle  Outside
Top      0,0     0,1     0,2
Middle   1,0     1,1     1,2
Bottom   2,0     2,1     2,2
```

#### Movement

| Field | Type | Description |
|-------|------|-------------|
| `run_in` | float | Horizontal break (inches, positive = catcher's right) |
| `rise_in` | float | Vertical break (inches, positive = upward) |

#### Speed & Rotation

| Field | Type | Description |
|-------|------|-------------|
| `measured_speed_mph` | float | Pitch velocity (mph) |
| `rotation_rpm` | float | Estimated spin rate (RPM) |

#### Trajectory

| Field | Type | Description |
|-------|------|-------------|
| `trajectory.plate_crossing_xyz_ft` | [float, float, float] | 3D plate crossing location (X, Y, Z in feet) |
| `trajectory.plate_crossing_t_ns` | int | Time of plate crossing (nanoseconds) |
| `trajectory.model` | string | Trajectory model used ("physics_drag", "polynomial", etc.) |
| `trajectory.expected_error_ft` | float | Expected trajectory error (feet) |
| `trajectory.confidence` | float | Trajectory confidence score (0.0-1.0) |

**Coordinate System:**
- X: Catcher's left (-) to right (+)
- Y: Ground (0) to vertical (+)
- Z: Pitcher (60.5 ft) to plate (0 ft)

#### Files

| Field | Type | Description |
|-------|------|-------------|
| `left_video` | string | Left camera video filename |
| `right_video` | string | Right camera video filename |
| `left_timestamps` | string | Left camera timestamps CSV filename |
| `right_timestamps` | string | Right camera timestamps CSV filename |
| `config_path` | string | Path to config file used |

#### Performance Metrics (v1.2.0+)

**Optional.** Present only if ML training data collection is enabled.

| Field | Type | Description |
|-------|------|-------------|
| `performance_metrics.detection_quality.stereo_observations` | int | Number of 3D observations triangulated |
| `performance_metrics.detection_quality.detection_rate_hz` | float | Detection rate (observations per second) |
| `performance_metrics.timing_accuracy.pre_roll_frames_captured` | int | Frames captured before pitch detection |
| `performance_metrics.timing_accuracy.duration_ns` | int | Pitch duration (nanoseconds) |
| `performance_metrics.timing_accuracy.start_ns` | int | Accurate start time (first detection) |
| `performance_metrics.timing_accuracy.end_ns` | int | Accurate end time (last detection) |

**Purpose:** ML training metrics for data quality assessment and model training.

---

## ML Training Data Files (v1.2.0+)

When ML training data collection is enabled (`recording.save_detections`, `save_observations`, `save_training_frames`), additional files are generated:

### Detection Files

**Location:** `{pitch_dir}/detections/{left|right}_detections.json`

**Schema:**
```json
{
  "pitch_id": "session-001-pitch-001",
  "camera": "left",
  "detection_count": 45,
  "detections": [
    {
      "frame_index": 42,
      "timestamp_ns": 1234567890000000,
      "u_px": 320.5,
      "v_px": 240.2,
      "radius_px": 12.3,
      "confidence": 0.95
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `pitch_id` | string | Pitch identifier |
| `camera` | string | Camera label ("left" or "right") |
| `detection_count` | int | Total detections in pitch |
| `detections[].frame_index` | int | Frame sequence number |
| `detections[].timestamp_ns` | int | Frame capture time (nanoseconds) |
| `detections[].u_px` | float | Horizontal pixel coordinate |
| `detections[].v_px` | float | Vertical pixel coordinate |
| `detections[].radius_px` | float | Detected ball radius (pixels) |
| `detections[].confidence` | float | Detection confidence (0.0-1.0) |

### Observation Files

**Location:** `{pitch_dir}/observations/stereo_observations.json`

**Schema:**
```json
{
  "pitch_id": "session-001-pitch-001",
  "observation_count": 38,
  "observations": [
    {
      "timestamp_ns": 1234567890000000,
      "left_px": [320.5, 240.2],
      "right_px": [280.3, 235.8],
      "X_ft": 0.5,
      "Y_ft": 3.2,
      "Z_ft": 55.0,
      "quality": 1.0,
      "confidence": 0.95
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `pitch_id` | string | Pitch identifier |
| `observation_count` | int | Total stereo observations |
| `observations[].timestamp_ns` | int | Observation time (nanoseconds) |
| `observations[].left_px` | [float, float] | Left camera pixel coordinates [u, v] |
| `observations[].right_px` | [float, float] | Right camera pixel coordinates [u, v] |
| `observations[].X_ft` | float | 3D X coordinate (feet, catcher left/right) |
| `observations[].Y_ft` | float | 3D Y coordinate (feet, vertical) |
| `observations[].Z_ft` | float | 3D Z coordinate (feet, toward plate) |
| `observations[].quality` | float | Stereo match quality (0.0-1.0) |
| `observations[].confidence` | float | Overall confidence (0.0-1.0) |

### Frame Files

**Location:** `{pitch_dir}/frames/{left|right}/*.png`

**Naming Convention:**
- `pre_roll_00001.png` - First pre-roll frame
- `uniform_00005.png` - Frame saved at uniform interval (e.g., every 5th frame)
- `pitch_00015_first.png` - First detection frame
- `pitch_00075_last.png` - Last detection frame
- `post_roll_last.png` - Last post-roll frame

**Format:** PNG (lossless)

**Purpose:** Key frames for ML model training (ball detection, field segmentation, etc.)

### Calibration Files

**Location:** `{session_dir}/calibration/*.json`

#### Stereo Geometry

**File:** `stereo_geometry.json`

```json
{
  "baseline_ft": 8.0,
  "convergence_angle_deg": 15.0,
  "camera_height_ft": 6.5,
  "distance_to_plate_ft": 62.0
}
```

#### Camera Intrinsics

**Files:** `intrinsics_left.json`, `intrinsics_right.json`

```json
{
  "camera_id": "ABC123",
  "fx": 1200.5,
  "fy": 1202.3,
  "cx": 640.1,
  "cy": 480.2,
  "distortion_k1": -0.12,
  "distortion_k2": 0.03
}
```

#### ROI Annotations

**File:** `roi_annotations.json`

```json
{
  "lane_gate_polygon": [[100, 200], [500, 200], [500, 600], [100, 600]],
  "plate_gate_polygon": [[200, 400], [400, 400], [400, 500], [200, 500]]
}
```

---

## Version History

### v1.2.0 (2026-01-16)
- Added `performance_metrics` to pitch manifest
- Added ML training data files (detections, observations, frames, calibration)
- Enhanced timing accuracy with V2 pitch tracking

### v1.1.0 (2026-01-16)
- Improved timing accuracy with V2 pitch tracking
- Added pre-roll buffering support

### v1.0.0
- Initial manifest schema

---

## Usage Examples

### Reading a Pitch Manifest (Python)

```python
import json
from pathlib import Path

# Load manifest
pitch_dir = Path("recordings/session-001/session-001-pitch-001")
manifest_file = pitch_dir / "manifest.json"
manifest = json.loads(manifest_file.read_text())

# Extract key data
is_strike = manifest["is_strike"]
speed_mph = manifest["measured_speed_mph"]
crossing = manifest["trajectory"]["plate_crossing_xyz_ft"]

print(f"Strike: {is_strike}")
print(f"Speed: {speed_mph:.1f} mph")
print(f"Crossing: X={crossing[0]:.2f} ft, Y={crossing[1]:.2f} ft, Z={crossing[2]:.2f} ft")

# Check for ML training data
if "performance_metrics" in manifest:
    metrics = manifest["performance_metrics"]
    obs_count = metrics["detection_quality"]["stereo_observations"]
    print(f"Observations: {obs_count}")
```

### Reading Detection Data (Python)

```python
# Load detections
detections_file = pitch_dir / "detections" / "left_detections.json"
if detections_file.exists():
    detections_data = json.loads(detections_file.read_text())
    print(f"Detections: {detections_data['detection_count']}")

    # First detection
    first = detections_data["detections"][0]
    print(f"First detection: ({first['u_px']:.1f}, {first['v_px']:.1f}) px")
```

---

## Related Documentation

- [CHANGELOG.md](CHANGELOG.md) - Version history
- [ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md) - ML training roadmap
- [ML_TRAINING_IMPLEMENTATION_GUIDE.md](ML_TRAINING_IMPLEMENTATION_GUIDE.md) - Implementation details
