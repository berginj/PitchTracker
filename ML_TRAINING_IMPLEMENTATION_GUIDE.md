# ML Training Data - Implementation Guide

## Quick Start (1 Week Implementation)

This guide provides concrete code changes to enable ML training data collection **immediately**, without disrupting existing coaching functionality.

---

## Phase 1: Detection Export (Day 1-2)

### Goal
Export all ball detections to JSON for later ML training

### Implementation

#### 1.1 Add Detection Storage to PitchRecorder

**File:** `app/pipeline/recording/pitch_recorder.py`

```python
class PitchRecorder:
    def __init__(self, config, session_dir, pitch_id):
        # Existing initialization
        ...

        # NEW: Detection storage
        self._save_detections = config.recording.get("save_detections", False)
        self._detections = {"left": [], "right": []}
        self._detection_count = {"left": 0, "right": 0}

    def write_frame_with_detections(
        self,
        label: str,
        frame: Frame,
        detections: Optional[List[Detection]] = None
    ) -> None:
        """Write frame and optionally store detection data.

        Args:
            label: Camera label
            frame: Frame to write
            detections: Optional list of detections in this frame
        """
        # Write video frame (existing)
        self.write_frame(label, frame)

        # NEW: Store detection data
        if self._save_detections and detections:
            for det in detections:
                self._detections[label].append({
                    "frame_index": frame.frame_index,
                    "timestamp_ns": det.t_capture_monotonic_ns,
                    "u_px": float(det.u),
                    "v_px": float(det.v),
                    "radius_px": float(det.radius_px),
                    "confidence": float(det.confidence),
                })
                self._detection_count[label] += 1

    def close(self):
        """Close recorder and export detection data."""
        # Existing video/CSV close
        ...

        # NEW: Export detections
        if self._save_detections and (self._detection_count["left"] > 0 or
                                       self._detection_count["right"] > 0):
            self._export_detections()

    def _export_detections(self):
        """Export detection data to JSON."""
        detections_dir = self._pitch_dir / "detections"
        detections_dir.mkdir(exist_ok=True)

        for camera in ["left", "right"]:
            if self._detections[camera]:
                detection_file = detections_dir / f"{camera}_detections.json"
                data = {
                    "pitch_id": self._pitch_id,
                    "camera": camera,
                    "detection_count": self._detection_count[camera],
                    "detections": self._detections[camera]
                }
                detection_file.write_text(json.dumps(data, indent=2))
                logger.info(f"Exported {self._detection_count[camera]} detections to {detection_file}")
```

#### 1.2 Update Pipeline Service to Pass Detections

**File:** `app/pipeline_service.py`

Find the frame processing code and modify to pass detections:

```python
def _on_stereo_result(self, label: str, frame: Frame, detections: List[Detection]):
    """Process stereo matching result."""
    # Existing stereo matching logic
    ...

    # Write to pitch recording (MODIFIED)
    if self._pitch_recorder and self._pitch_recorder.is_active():
        # NEW: Pass detections along with frame
        self._pitch_recorder.write_frame_with_detections(label, frame, detections)
```

#### 1.3 Add Config Option

**File:** `configs/default.yaml`

```yaml
recording:
  pre_roll_ms: 500
  post_roll_ms: 500
  output_dir: "C:/Users/bergi/Desktop/pitchtracker_recordings"
  session_min_active_frames: 5
  session_end_gap_frames: 10

  # NEW: ML training data options
  save_detections: true  # Export detection JSON files
```

**File:** `configs/settings.py`

```python
@dataclass(frozen=True)
class RecordingConfig:
    pre_roll_ms: int
    post_roll_ms: int
    output_dir: str
    session_min_active_frames: int
    session_end_gap_frames: int
    save_detections: bool = False  # NEW
```

### Testing

```bash
# 1. Update config
# Edit configs/default.yaml, set save_detections: true

# 2. Record a test pitch
# Run the app, record a pitch

# 3. Verify detection export
ls recordings/session-*/session-*-pitch-*/detections/
cat recordings/session-*/session-*-pitch-*/detections/left_detections.json

# Expected output: JSON with array of detections
```

---

## Phase 2: Stereo Observations Export (Day 3)

### Goal
Export 3D trajectory points for trajectory analysis

### Implementation

#### 2.1 Add Observation Storage

**File:** `app/pipeline/recording/pitch_recorder.py`

```python
class PitchRecorder:
    def __init__(self, config, session_dir, pitch_id):
        # Existing...
        ...

        # NEW: Observation storage
        self._save_observations = config.recording.get("save_observations", False)
        self._observations = []

    def add_observation(self, obs: StereoObservation) -> None:
        """Store stereo observation for export.

        Args:
            obs: Stereo observation to store
        """
        if self._save_observations:
            self._observations.append({
                "timestamp_ns": obs.t_ns,
                "left_px": [float(obs.left[0]), float(obs.left[1])],
                "right_px": [float(obs.right[0]), float(obs.right[1])],
                "X_ft": float(obs.X),
                "Y_ft": float(obs.Y),
                "Z_ft": float(obs.Z),
                "quality": float(obs.quality),
                "confidence": float(obs.confidence),
            })

    def close(self):
        # Existing...
        ...

        # NEW: Export observations
        if self._save_observations and self._observations:
            self._export_observations()

    def _export_observations(self):
        """Export stereo observations to JSON."""
        obs_dir = self._pitch_dir / "observations"
        obs_dir.mkdir(exist_ok=True)

        obs_file = obs_dir / "stereo_observations.json"
        data = {
            "pitch_id": self._pitch_id,
            "observation_count": len(self._observations),
            "observations": self._observations
        }
        obs_file.write_text(json.dumps(data, indent=2))
        logger.info(f"Exported {len(self._observations)} observations to {obs_file}")
```

#### 2.2 Update Pipeline Service

**File:** `app/pipeline_service.py`

```python
def _on_stereo_result(self, label: str, frame: Frame, detections: List[Detection]):
    # Existing stereo matching...
    observations = self._stereo.match(left_dets, right_dets)

    # Add observations to pitch tracker
    for obs in observations:
        self._pitch_tracker.add_observation(obs)

        # NEW: Also add to pitch recorder for export
        if self._pitch_recorder and self._pitch_recorder.is_active():
            self._pitch_recorder.add_observation(obs)
```

#### 2.3 Add Config Option

**File:** `configs/default.yaml`

```yaml
recording:
  # Existing...
  save_detections: true
  save_observations: true  # NEW: Export 3D trajectory points
```

---

## Phase 3: Key Frame Extraction (Day 4-5)

### Goal
Save PNG frames at critical moments for ML training

### Implementation

#### 3.1 Frame Extractor Class

**File:** `app/pipeline/recording/frame_extractor.py` (NEW FILE)

```python
"""Extract key frames from pitch video for ML training."""

from pathlib import Path
from typing import Dict, Optional
import cv2
from contracts import Frame

class FrameExtractor:
    """Extracts and saves key frames during pitch recording."""

    def __init__(self, pitch_dir: Path, enabled: bool = True):
        """Initialize frame extractor.

        Args:
            pitch_dir: Directory to save frames
            enabled: Whether frame extraction is enabled
        """
        self._pitch_dir = pitch_dir
        self._enabled = enabled
        self._frames_dir = pitch_dir / "frames"

        if self._enabled:
            self._frames_dir.mkdir(exist_ok=True)
            (self._frames_dir / "left").mkdir(exist_ok=True)
            (self._frames_dir / "right").mkdir(exist_ok=True)

        # Track which frames have been saved
        self._saved_frames = {
            "pre_roll_first": False,
            "pre_roll_last": False,
            "first_detection": False,
            "release_point": False,
            "plate_crossing": False,
            "last_detection": False,
            "post_roll_last": False,
        }

        # Frame counters
        self._frame_count = {"left": 0, "right": 0}

    def save_pre_roll_first(self, label: str, frame: Frame):
        """Save first pre-roll frame."""
        if self._enabled and not self._saved_frames["pre_roll_first"]:
            self._save_frame(label, frame, "pre_roll_00001")
            self._saved_frames["pre_roll_first"] = True

    def save_first_detection(self, label: str, frame: Frame):
        """Save first detection frame."""
        if self._enabled and not self._saved_frames["first_detection"]:
            self._save_frame(label, frame, f"pitch_{self._frame_count[label]:05d}_first")
            self._saved_frames["first_detection"] = True

    def save_last_detection(self, label: str, frame: Frame):
        """Save last detection frame."""
        if self._enabled:
            # Always update (we don't know which is last until pitch ends)
            self._save_frame(label, frame, f"pitch_{self._frame_count[label]:05d}_last")
            self._saved_frames["last_detection"] = True

    def save_post_roll_last(self, label: str, frame: Frame):
        """Save last post-roll frame."""
        if self._enabled and not self._saved_frames["post_roll_last"]:
            self._save_frame(label, frame, "post_roll_last")
            self._saved_frames["post_roll_last"] = True

    def save_uniform(self, label: str, frame: Frame, interval: int = 5):
        """Save frame at uniform intervals.

        Args:
            label: Camera label
            frame: Frame to save
            interval: Save every Nth frame
        """
        if self._enabled:
            self._frame_count[label] += 1
            if self._frame_count[label] % interval == 0:
                self._save_frame(label, frame, f"uniform_{self._frame_count[label]:05d}")

    def _save_frame(self, label: str, frame: Frame, name: str):
        """Save frame as PNG.

        Args:
            label: Camera label
            frame: Frame to save
            name: File name (without extension)
        """
        if frame.image is None:
            return

        frame_path = self._frames_dir / label / f"{name}.png"
        cv2.imwrite(str(frame_path), frame.image)
```

#### 3.2 Integrate into PitchRecorder

**File:** `app/pipeline/recording/pitch_recorder.py`

```python
from app.pipeline.recording.frame_extractor import FrameExtractor

class PitchRecorder:
    def __init__(self, config, session_dir, pitch_id):
        # Existing...
        ...

        # NEW: Frame extractor
        self._save_frames = config.recording.get("save_training_frames", False)
        self._frame_extractor = FrameExtractor(self._pitch_dir, enabled=self._save_frames)
        self._frame_interval = config.recording.get("frame_save_interval", 5)

        # Track pitch phase for keypoint extraction
        self._pitch_started = False
        self._pitch_ended = False

    def start_pitch(self):
        """Start pitch recording."""
        # Existing...
        ...

        self._pitch_started = True

        # NEW: Save pre-roll first frame marker
        # (will be saved when first frame is written)

    def write_frame_with_detections(self, label, frame, detections=None):
        """Write frame with optional detection data and frame extraction."""
        # Existing video write
        self.write_frame(label, frame)

        # Existing detection storage
        if self._save_detections and detections:
            # ... (from Phase 1)

        # NEW: Frame extraction
        if self._save_frames:
            # Save first pre-roll frame
            if not self._pitch_started:
                self._frame_extractor.save_pre_roll_first(label, frame)

            # Save first detection frame
            if self._pitch_started and detections and len(detections) > 0:
                self._frame_extractor.save_first_detection(label, frame)

            # Save uniform intervals
            self._frame_extractor.save_uniform(label, frame, self._frame_interval)

            # Save last detection (continuously updated)
            if detections and len(detections) > 0:
                self._frame_extractor.save_last_detection(label, frame)

            # Save post-roll last frame
            if self._pitch_ended:
                self._frame_extractor.save_post_roll_last(label, frame)

    def end_pitch(self, end_ns: int):
        """End pitch recording (enter post-roll phase)."""
        # Existing...
        ...

        self._pitch_ended = True
```

#### 3.3 Add Config Options

**File:** `configs/default.yaml`

```yaml
recording:
  # Existing...
  save_detections: true
  save_observations: true
  save_training_frames: true  # NEW: Save key frames
  frame_save_interval: 5       # NEW: Save every 5th frame
```

---

## Phase 4: Calibration Metadata Export (Day 6)

### Goal
Export all calibration parameters for self-calibration ML research

### Implementation

#### 4.1 Calibration Export Function

**File:** `app/pipeline/recording/calibration_export.py` (NEW FILE)

```python
"""Export calibration metadata for ML training."""

import json
from pathlib import Path
from typing import Optional
import numpy as np

def export_calibration_metadata(
    session_dir: Path,
    stereo: Any,  # SimpleStereoMatcher
    left_camera_id: str,
    right_camera_id: str,
    lane_gate: Optional[Any] = None,
    plate_gate: Optional[Any] = None,
    strike_zone: Optional[Any] = None
):
    """Export calibration metadata to JSON.

    Args:
        session_dir: Session directory
        stereo: Stereo matcher with calibration
        left_camera_id: Left camera serial
        right_camera_id: Right camera serial
        lane_gate: Lane ROI gate
        plate_gate: Plate ROI gate
        strike_zone: Strike zone definition
    """
    calib_dir = session_dir / "calibration"
    calib_dir.mkdir(exist_ok=True)

    # Stereo geometry
    geometry = {
        "baseline_ft": float(stereo.geometry.baseline_ft),
        "convergence_angle_deg": float(stereo.geometry.convergence_angle_deg),
        "camera_height_ft": float(stereo.geometry.camera_height_ft),
        "distance_to_plate_ft": float(stereo.geometry.distance_to_plate_ft),
    }
    (calib_dir / "stereo_geometry.json").write_text(json.dumps(geometry, indent=2))

    # Camera intrinsics (if available)
    if hasattr(stereo, 'camera_matrix_left'):
        intrinsics_left = {
            "camera_id": left_camera_id,
            "fx": float(stereo.camera_matrix_left[0, 0]),
            "fy": float(stereo.camera_matrix_left[1, 1]),
            "cx": float(stereo.camera_matrix_left[0, 2]),
            "cy": float(stereo.camera_matrix_left[1, 2]),
            "distortion_k1": float(stereo.dist_coeffs_left[0]) if stereo.dist_coeffs_left is not None else 0.0,
            "distortion_k2": float(stereo.dist_coeffs_left[1]) if stereo.dist_coeffs_left is not None else 0.0,
        }
        (calib_dir / "intrinsics_left.json").write_text(json.dumps(intrinsics_left, indent=2))

        intrinsics_right = {
            "camera_id": right_camera_id,
            "fx": float(stereo.camera_matrix_right[0, 0]),
            "fy": float(stereo.camera_matrix_right[1, 1]),
            "cx": float(stereo.camera_matrix_right[0, 2]),
            "cy": float(stereo.camera_matrix_right[1, 2]),
            "distortion_k1": float(stereo.dist_coeffs_right[0]) if stereo.dist_coeffs_right is not None else 0.0,
            "distortion_k2": float(stereo.dist_coeffs_right[1]) if stereo.dist_coeffs_right is not None else 0.0,
        }
        (calib_dir / "intrinsics_right.json").write_text(json.dumps(intrinsics_right, indent=2))

    # ROI annotations
    roi_annotations = {}

    if lane_gate and hasattr(lane_gate, 'polygon'):
        roi_annotations["lane_gate_polygon"] = [[float(x), float(y)] for x, y in lane_gate.polygon]

    if plate_gate and hasattr(plate_gate, 'polygon'):
        roi_annotations["plate_gate_polygon"] = [[float(x), float(y)] for x, y in plate_gate.polygon]

    if roi_annotations:
        (calib_dir / "roi_annotations.json").write_text(json.dumps(roi_annotations, indent=2))

    # Strike zone definition
    if strike_zone:
        zone_def = {
            "top_left_ft": [float(strike_zone.top_left[0]), float(strike_zone.top_left[1]), float(strike_zone.top_left[2])],
            "top_right_ft": [float(strike_zone.top_right[0]), float(strike_zone.top_right[1]), float(strike_zone.top_right[2])],
            "bottom_left_ft": [float(strike_zone.bottom_left[0]), float(strike_zone.bottom_left[1]), float(strike_zone.bottom_left[2])],
            "bottom_right_ft": [float(strike_zone.bottom_right[0]), float(strike_zone.bottom_right[1]), float(strike_zone.bottom_right[2])],
        }
        (calib_dir / "strike_zone_definition.json").write_text(json.dumps(zone_def, indent=2))
```

#### 4.2 Call During Session Start

**File:** `app/pipeline_service.py`

```python
from app.pipeline.recording.calibration_export import export_calibration_metadata

def start_recording(...):
    """Start recording session."""
    # Existing session recorder initialization
    ...

    # NEW: Export calibration metadata
    if self._session_recorder:
        session_dir = self._session_recorder.get_session_dir()
        export_calibration_metadata(
            session_dir=session_dir,
            stereo=self._stereo,
            left_camera_id=left_serial,
            right_camera_id=right_serial,
            lane_gate=self._lane_gate,
            plate_gate=self._plate_gate,
            strike_zone=None,  # TODO: Get from config
        )
        logger.info(f"Exported calibration metadata to {session_dir / 'calibration'}")
```

---

## Phase 5: Enhanced Manifest Schema (Day 7)

### Goal
Add performance metrics and detection quality to manifest

### Implementation

#### 5.1 Update Manifest Creation

**File:** `app/pipeline/recording/manifest.py`

```python
def create_pitch_manifest(summary, config_path: str,
                         performance_metrics: Optional[Dict] = None) -> Dict[str, Any]:
    """Create pitch manifest with optional performance metrics.

    Args:
        summary: PitchSummary object
        config_path: Path to config file
        performance_metrics: Optional dict with detection/tracking metrics

    Returns:
        Complete pitch manifest dictionary
    """
    manifest = create_base_manifest()
    manifest.update({
        # Existing fields...
        "pitch_id": summary.pitch_id,
        # ...
    })

    # NEW: Add performance metrics
    if performance_metrics:
        manifest["performance_metrics"] = performance_metrics

    return manifest
```

#### 5.2 Collect Performance Metrics

**File:** `app/pipeline_service.py`

```python
def _on_pitch_end(self, pitch_data: PitchData):
    """Callback when pitch ends (V2)."""
    # Existing analysis...
    summary = self._pitch_analyzer.analyze_pitch(...)

    # NEW: Collect performance metrics
    performance_metrics = {
        "detection_quality": {
            "left_camera_detections": self._detection_count.get("left", 0),
            "right_camera_detections": self._detection_count.get("right", 0),
            "stereo_observations": len(pitch_data.observations),
            "detection_rate_hz": float(len(pitch_data.observations)) / (pitch_data.duration_ns() / 1e9),
            "frames_with_no_detection": self._no_detection_count,
        },
        "timing_accuracy": {
            "pre_roll_frames_captured": len(pitch_data.pre_roll_frames),
            "duration_ns": pitch_data.duration_ns(),
            "start_ns": pitch_data.start_ns,
            "end_ns": pitch_data.end_ns,
        }
    }

    # Write manifest with metrics
    if self._pitch_recorder:
        config_path = str(self._config_path) if self._config_path else None
        self._pitch_recorder.write_manifest(
            summary,
            config_path,
            performance_metrics=performance_metrics  # NEW
        )

    # Reset counters for next pitch
    self._detection_count = {"left": 0, "right": 0}
    self._no_detection_count = 0
```

---

## Testing the Complete Implementation

### Test Script

```python
# test_ml_data_export.py

import json
from pathlib import Path

def test_ml_data_export(session_dir: Path):
    """Verify ML training data was exported correctly.

    Args:
        session_dir: Path to recorded session
    """
    print(f"Testing ML data export for {session_dir}")

    # Find first pitch directory
    pitch_dirs = list(session_dir.glob("*-pitch-*"))
    if not pitch_dirs:
        print("❌ No pitch directories found")
        return False

    pitch_dir = pitch_dirs[0]
    print(f"✓ Found pitch directory: {pitch_dir.name}")

    # Check for detection export
    left_det = pitch_dir / "detections" / "left_detections.json"
    right_det = pitch_dir / "detections" / "right_detections.json"

    if left_det.exists():
        data = json.loads(left_det.read_text())
        print(f"✓ Left detections: {data['detection_count']} detections")
    else:
        print("❌ Left detections not found")

    if right_det.exists():
        data = json.loads(right_det.read_text())
        print(f"✓ Right detections: {data['detection_count']} detections")
    else:
        print("❌ Right detections not found")

    # Check for observation export
    obs_file = pitch_dir / "observations" / "stereo_observations.json"
    if obs_file.exists():
        data = json.loads(obs_file.read_text())
        print(f"✓ Observations: {data['observation_count']} observations")
    else:
        print("❌ Observations not found")

    # Check for frame export
    frames_dir = pitch_dir / "frames"
    if frames_dir.exists():
        left_frames = list((frames_dir / "left").glob("*.png"))
        right_frames = list((frames_dir / "right").glob("*.png"))
        print(f"✓ Frames: {len(left_frames)} left, {len(right_frames)} right")
    else:
        print("❌ Frames directory not found")

    # Check for calibration export
    calib_dir = session_dir / "calibration"
    if calib_dir.exists():
        calib_files = list(calib_dir.glob("*.json"))
        print(f"✓ Calibration: {len(calib_files)} files")
        for f in calib_files:
            print(f"  - {f.name}")
    else:
        print("❌ Calibration directory not found")

    # Check manifest
    manifest_file = pitch_dir / "manifest.json"
    if manifest_file.exists():
        data = json.loads(manifest_file.read_text())
        if "performance_metrics" in data:
            print("✓ Manifest has performance metrics")
        else:
            print("⚠ Manifest missing performance metrics")
    else:
        print("❌ Manifest not found")

    print("\n✓ ML data export test complete")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_ml_data_export.py <session_dir>")
        sys.exit(1)

    session_dir = Path(sys.argv[1])
    test_ml_data_export(session_dir)
```

### Run Test

```bash
# 1. Enable ML training mode in config
# Edit configs/default.yaml:
recording:
  save_detections: true
  save_observations: true
  save_training_frames: true
  frame_save_interval: 5

# 2. Record a test session
# Run the app, record a few pitches

# 3. Test the export
python test_ml_data_export.py "C:/Users/bergi/Desktop/pitchtracker_recordings/session-2026-01-16_001"

# Expected output:
# ✓ Found pitch directory: session-001-pitch-001
# ✓ Left detections: 45 detections
# ✓ Right detections: 43 detections
# ✓ Observations: 38 observations
# ✓ Frames: 20 left, 20 right
# ✓ Calibration: 4 files
#   - stereo_geometry.json
#   - roi_annotations.json
#   - intrinsics_left.json
#   - intrinsics_right.json
# ✓ Manifest has performance metrics
# ✓ ML data export test complete
```

---

## Summary

After implementing these 5 phases (1 week), you will have:

✅ **Detection export** - All ball detections saved to JSON
✅ **Observation export** - 3D trajectory points saved
✅ **Frame extraction** - Key frames saved as PNG for training
✅ **Calibration export** - All calibration parameters documented
✅ **Enhanced manifests** - Performance metrics included

**Storage Impact:** +25% per session (~1 GB extra for 20 pitches)

**Next Steps:**
1. Collect data for 3 months (target: 10,000 pitches)
2. Build annotation tool (see main strategy doc)
3. Train first ball detector model
4. Integrate model and measure automation impact

**ROI:** Every pitch recorded now serves dual purpose - coaching today, ML training tomorrow!
