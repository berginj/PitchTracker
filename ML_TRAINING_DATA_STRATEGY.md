# ML Training Data Strategy - Comprehensive Analysis

## Executive Summary

**Current State:** The system captures good data for coaching but is missing critical annotations and metadata needed for ML training.

**Goal:** Create a data capture strategy that serves dual purposes:
1. **Coaching** - Review and analysis for players
2. **ML Training** - Build domain-specific models to automate setup and reduce manual steps

**Key Gap:** We capture videos and trajectory data, but **missing ground truth annotations** needed to train models that can replace manual calibration steps.

---

## Current Data Capture Analysis

### What We Currently Save ✅

#### Per-Pitch Data
```
session-001/
├── session-001-pitch-001/
│   ├── left.avi              # Left camera video
│   ├── right.avi             # Right camera video
│   ├── left_timestamps.csv   # Frame timestamps
│   ├── right_timestamps.csv
│   └── manifest.json         # Pitch metadata
```

**Manifest Contents:**
- Timing (start_ns, end_ns)
- Strike zone classification (is_strike, zone_row, zone_col)
- Movement (run_in, rise_in)
- Speed (measured_speed_mph)
- Rotation (rotation_rpm)
- Trajectory (plate crossing XYZ, model, confidence)
- Config snapshot path

#### Per-Session Data
- Full session videos (session_left.avi, session_right.avi)
- Frame timestamps for entire session
- Session summary (pitch count, strikes/balls, heatmap)
- Config used

### What We DON'T Save ❌

**Critical Missing Data for ML Training:**

1. **Individual frame detections** (u, v pixel coordinates)
2. **Detection confidence scores**
3. **Stereo observation sequences** (3D points over time)
4. **ROI polygons** used for detection
5. **Calibration parameters** (camera matrices, distortion, stereo geometry)
6. **Strike zone 3D coordinates**
7. **Detection failure cases** (where detector failed to find ball)
8. **Labeled frame indices** (which frames contain ball vs no ball)
9. **Object masks/bounding boxes** (for detector training)
10. **Environmental metadata** (lighting conditions, background complexity)

---

## Problem Statement: Manual Setup Steps

### Current Manual Steps That Should Be Automated:

1. **ROI Calibration** (Lane & Plate Gates)
   - User must manually draw polygons on camera views
   - Different for every installation
   - Requires understanding of detection pipeline
   - **ML Opportunity:** Auto-detect field of play boundaries

2. **Strike Zone Calibration**
   - User must measure and input strike zone dimensions
   - Batter height changes per player
   - Top/bottom ratio adjustments
   - **ML Opportunity:** Auto-detect strike zone from pitcher perspective

3. **Camera Calibration** (Stereo Geometry)
   - Requires checkerboard pattern
   - Multiple capture angles
   - Intrinsics + extrinsics calibration
   - **ML Opportunity:** Self-calibration from ball flight

4. **Detector Tuning**
   - Classical: HSV thresholds, size filters, morphology
   - ML: Model selection, confidence threshold
   - **ML Opportunity:** Auto-tune from environment

5. **Ball Type Selection**
   - Different ball types (baseb all, softball, etc.)
   - Different sizes and colors
   - **ML Opportunity:** Auto-detect ball type

---

## Recommended Data Capture Enhancements

### Priority 1: Training Data for Automation Models 🔴

#### 1.1 Detection Ground Truth Dataset

**Purpose:** Train robust ball detector that works across environments

**What to Add:**
```json
{
  "pitch_id": "session-001-pitch-001",
  "detection_annotations": [
    {
      "frame_index": 42,
      "camera": "left",
      "timestamp_ns": 1234567890,
      "detections": [
        {
          "u_px": 320.5,
          "v_px": 240.2,
          "radius_px": 12.3,
          "confidence": 0.95,
          "detection_method": "classical_hsv",
          "is_true_positive": true  // Manual annotation
        }
      ],
      "ground_truth_bbox": {  // For training
        "x_min": 308,
        "y_min": 228,
        "x_max": 333,
        "y_max": 253,
        "annotator": "auto_v2",
        "annotation_confidence": 0.99
      },
      "frame_saved": "frames/left_000042.png"  // Save actual frame
    }
  ]
}
```

**Storage:**
- Save frames with detections as PNG (lossless)
- Save detection annotations as JSON
- Link to video timestamp for context

**Use Case:** Train universal ball detector that works in:
- Indoor/outdoor lighting
- Different backgrounds
- Various ball types
- Motion blur scenarios

#### 1.2 ROI Auto-Detection Training Data

**Purpose:** Train model to automatically detect field boundaries

**What to Add:**
```json
{
  "session_id": "session-001",
  "camera_id": "left_ABC123",
  "roi_annotations": {
    "lane_gate_polygon": [
      [100, 200], [500, 200], [500, 600], [100, 600]
    ],
    "plate_gate_polygon": [
      [200, 400], [400, 400], [400, 500], [200, 500]
    ],
    "field_boundaries": {
      "pitcher_mound": [[x1, y1], [x2, y2], ...],
      "home_plate": [[x1, y1], [x2, y2], ...],
      "backstop": [[x1, y1], [x2, y2], ...],
      "foul_lines": {
        "left": [[x1, y1], [x2, y2]],
        "right": [[x1, y1], [x2, y2]]
      }
    },
    "annotator": "manual_v1",
    "annotation_confidence": 1.0,
    "reference_frame": "frames/roi_reference_left.png"
  }
}
```

**Storage:**
- Save reference frame used for ROI annotation
- Store polygon coordinates in image space
- Include field landmarks (mound, plate, backstop)

**Use Case:** Train model to segment field from background, then auto-generate ROIs

#### 1.3 Strike Zone Auto-Detection Training Data

**Purpose:** Automatically detect and dimension strike zone

**What to Add:**
```json
{
  "session_id": "session-001",
  "strike_zone_annotations": {
    "batter_height_inches": 72.0,
    "strike_zone_3d": {
      "top_left_ft": [0.0, 3.5, 60.5],
      "top_right_ft": [1.42, 3.5, 60.5],
      "bottom_left_ft": [0.0, 1.7, 60.5],
      "bottom_right_ft": [1.42, 1.7, 60.5]
    },
    "strike_zone_2d_projections": {
      "left_camera": {
        "top_left_px": [320, 180],
        "top_right_px": [360, 185],
        "bottom_left_px": [315, 280],
        "bottom_right_px": [365, 285]
      },
      "right_camera": {
        "top_left_px": [280, 175],
        "top_right_px": [320, 180],
        "bottom_left_px": [275, 275],
        "bottom_right_px": [325, 280]
      }
    },
    "batter_pose_landmarks": [
      {"name": "head", "xyz_ft": [0.7, 5.5, 60.5]},
      {"name": "knees", "xyz_ft": [0.7, 1.7, 60.5]},
      {"name": "shoulders", "xyz_ft": [0.7, 4.8, 60.5]}
    ],
    "reference_frames": {
      "left": "frames/batter_stance_left.png",
      "right": "frames/batter_stance_right.png"
    }
  }
}
```

**Use Case:** Train pose estimation model to detect batter and auto-calculate strike zone

#### 1.4 Calibration Self-Discovery Training Data

**Purpose:** Enable self-calibration from ball trajectories (no checkerboard needed)

**What to Add:**
```json
{
  "session_id": "session-001",
  "calibration_verification": {
    "stereo_geometry": {
      "baseline_ft": 8.0,
      "convergence_angle_deg": 15.0,
      "camera_height_ft": 6.5,
      "distance_to_plate_ft": 62.0
    },
    "intrinsics_left": {
      "fx": 1200.5, "fy": 1202.3,
      "cx": 640.1, "cy": 480.2,
      "distortion_k1": -0.12, "distortion_k2": 0.03
    },
    "intrinsics_right": {
      "fx": 1198.2, "fy": 1200.7,
      "cx": 638.9, "cy": 479.5,
      "distortion_k1": -0.11, "distortion_k2": 0.03
    },
    "extrinsics": {
      "rotation_matrix": [[...], [...], [...]],
      "translation_vector": [8.0, 0.0, 0.0]
    },
    "calibration_method": "checkerboard_opencv",
    "reprojection_error_px": 0.42,
    "calibration_frames": [
      "calibration/checkerboard_01.png",
      "calibration/checkerboard_02.png"
    ]
  }
}
```

**Use Case:**
- Validate calibration against ground truth
- Train bundle adjustment model to refine calibration from pitch data
- Enable calibration-free setup

### Priority 2: Enhanced Metadata for Analysis 🟡

#### 2.1 Environmental Conditions

**What to Add:**
```json
{
  "session_id": "session-001",
  "environment": {
    "location": "indoor" | "outdoor",
    "lighting": {
      "type": "natural" | "artificial" | "mixed",
      "brightness_lux": 800,  // From camera sensor
      "shadows": "minimal" | "moderate" | "high",
      "glare_detected": false
    },
    "background_complexity": {
      "static_score": 0.3,  // 0=uniform, 1=complex
      "motion_detected": false,
      "crowd_present": false
    },
    "weather": {  // If outdoor
      "conditions": "clear" | "cloudy" | "rain",
      "wind_mph": 5.2,
      "temperature_f": 72
    }
  }
}
```

**Use Case:** Understand which conditions affect detection accuracy

#### 2.2 Performance Metrics

**What to Add:**
```json
{
  "pitch_id": "session-001-pitch-001",
  "performance_metrics": {
    "detection_quality": {
      "left_camera_detections": 45,
      "right_camera_detections": 43,
      "stereo_observations": 38,
      "detection_rate_hz": 30.0,
      "avg_detection_confidence": 0.92,
      "frames_with_no_detection": 2
    },
    "tracking_quality": {
      "track_continuity_pct": 95.6,
      "max_gap_frames": 1,
      "tracking_errors_detected": 0
    },
    "timing_accuracy": {
      "frame_period_actual_ms": 33.2,
      "frame_period_expected_ms": 33.3,
      "jitter_ms": 0.1,
      "pre_roll_frames_captured": 10,
      "post_roll_frames_captured": 15
    }
  }
}
```

**Use Case:** Identify data quality issues, filter training data

#### 2.3 Player & Session Context

**What to Add:**
```json
{
  "session_id": "session-001",
  "player_context": {
    "player_id": "player_123",  // Anonymous ID
    "player_profile": {
      "hand": "right" | "left",
      "height_inches": 72,
      "skill_level": "youth" | "high_school" | "college" | "pro",
      "position": "pitcher" | "catcher" | "infielder"
    },
    "session_goal": "bullpen" | "practice" | "warmup" | "assessment",
    "pitch_types_thrown": ["fastball", "curveball", "changeup"],
    "session_duration_minutes": 30
  }
}
```

**Use Case:**
- Stratify training data by skill level
- Understand typical pitch characteristics
- Improve trajectory models

### Priority 3: Frame-Level Data for Deep Learning 🟢

#### 3.1 Saved Raw Frames

**Recommendation:** Save frames at key points for training

**What to Save:**
```
session-001-pitch-001/
├── frames/
│   ├── left/
│   │   ├── pre_roll_00001.png  // First pre-roll frame
│   │   ├── pre_roll_00010.png  // Last pre-roll frame
│   │   ├── pitch_00015.png     // First detection frame
│   │   ├── pitch_00030.png     // Pitch release
│   │   ├── pitch_00060.png     // Ball at plate
│   │   ├── pitch_00075.png     // Last detection frame
│   │   └── post_roll_00090.png // Last post-roll frame
│   └── right/
│       └── (same structure)
│
├── detections/
│   ├── left_detections.json    // All detection data
│   └── right_detections.json
│
└── observations/
    └── stereo_observations.json  // 3D trajectory points
```

**Storage Strategy:**
- Save keyframes as PNG (lossless)
- Compress with zstd for storage efficiency
- Keep videos for review, frames for training

#### 3.2 Detection Sequence Export

**Recommendation:** Export all detections for analysis

```json
{
  "pitch_id": "session-001-pitch-001",
  "camera": "left",
  "detections": [
    {
      "frame_index": 15,
      "timestamp_ns": 1234567890,
      "u_px": 320.5,
      "v_px": 240.2,
      "radius_px": 12.3,
      "confidence": 0.95,
      "detection_method": "classical_hsv",
      "hsv_values": {"h": 20, "s": 180, "v": 200},  // Debug info
      "roi_used": "plate_gate",
      "processing_time_ms": 2.3
    }
  ]
}
```

---

## Proposed New Directory Structure

```
recordings/
├── session_2026-01-16_001/
│   ├── manifest.json                    # Session metadata
│   ├── session_left.avi                 # Full session (coaching)
│   ├── session_right.avi
│   ├── session_left_timestamps.csv
│   ├── session_right_timestamps.csv
│   ├── session_summary.json
│   │
│   ├── calibration/                     # NEW: Calibration data
│   │   ├── stereo_geometry.json
│   │   ├── intrinsics_left.json
│   │   ├── intrinsics_right.json
│   │   ├── roi_annotations.json         # ROI polygons
│   │   ├── strike_zone_definition.json
│   │   └── reference_frames/
│   │       ├── left_reference.png
│   │       └── right_reference.png
│   │
│   ├── environment.json                 # NEW: Environmental metadata
│   │
│   └── pitches/
│       ├── pitch_001/
│       │   ├── manifest.json            # Pitch metadata (enhanced)
│       │   ├── left.avi                 # Pitch video (coaching)
│       │   ├── right.avi
│       │   ├── left_timestamps.csv
│       │   ├── right_timestamps.csv
│       │   │
│       │   ├── frames/                  # NEW: Key frames for ML
│       │   │   ├── left/
│       │   │   │   ├── pre_roll_00001.png
│       │   │   │   ├── pitch_00015.png
│       │   │   │   ├── pitch_00030.png
│       │   │   │   └── ...
│       │   │   └── right/
│       │   │       └── (same)
│       │   │
│       │   ├── detections/              # NEW: All detection data
│       │   │   ├── left_detections.json
│       │   │   ├── right_detections.json
│       │   │   └── detection_summary.json
│       │   │
│       │   ├── observations/            # NEW: 3D trajectory
│       │   │   ├── stereo_observations.json
│       │   │   ├── trajectory_fit.json
│       │   │   └── trajectory_residuals.json
│       │   │
│       │   └── annotations/             # NEW: Ground truth
│       │       ├── ball_masks/          # For semantic segmentation
│       │       │   ├── left_00015_mask.png
│       │       │   └── ...
│       │       └── bounding_boxes.json  # For object detection
│       │
│       ├── pitch_002/
│       └── ...
│
└── ml_training/                         # NEW: Aggregated training datasets
    ├── ball_detection_dataset/
    │   ├── images/
    │   ├── labels/
    │   ├── train.txt
    │   ├── val.txt
    │   └── dataset.yaml
    │
    ├── roi_detection_dataset/
    │   └── ...
    │
    ├── strike_zone_dataset/
    │   └── ...
    │
    └── calibration_dataset/
        └── ...
```

---

## ML Models to Train (Priority Order)

### 1. Ball Detector Model 🔴 **HIGHEST IMPACT**

**Purpose:** Replace manual HSV threshold tuning

**Training Data Needed:**
- 10,000+ labeled frames with ball bounding boxes
- Various lighting conditions
- Different ball types
- Motion blur examples
- Negative examples (no ball)

**Architecture:** YOLOv8-nano or EfficientDet-Lite
**Output:** (x, y, w, h, confidence) bounding box
**Performance Target:** >95% detection rate, <1% false positive, <5ms inference

**Impact:**
- Eliminates detector tuning
- Works across installations
- Adapts to lighting automatically

### 2. Field Segmentation Model 🟡

**Purpose:** Auto-detect ROI boundaries

**Training Data Needed:**
- 1,000+ labeled frames with field segmentation masks
- Various field types (indoor/outdoor, different mounds)
- Camera angles and distances

**Architecture:** U-Net or DeepLabV3+
**Output:** Semantic segmentation (field vs background)
**Performance Target:** >90% IoU, <20ms inference

**Impact:**
- Eliminates manual ROI drawing
- Adapts to different installations
- Updates automatically if camera moves

### 3. Batter Pose Estimation Model 🟡

**Purpose:** Auto-detect strike zone from batter

**Training Data Needed:**
- 5,000+ labeled frames with batter keypoints
- Various batter heights and stances
- Left/right handed batters

**Architecture:** HRNet or MediaPipe-based
**Output:** 2D keypoints (head, shoulders, knees, feet)
**Performance Target:** <10px keypoint error, <15ms inference

**Impact:**
- Eliminates strike zone calibration
- Adapts per-batter automatically
- Handles batter movement

### 4. Stereo Self-Calibration Model 🟢

**Purpose:** Refine calibration from ball trajectories

**Training Data Needed:**
- 1,000+ pitches with known ground truth calibration
- Stereo correspondences (left/right detections)
- 3D trajectories

**Architecture:** Differentiable bundle adjustment network
**Output:** Refined camera parameters
**Performance Target:** <0.5px reprojection error improvement

**Impact:**
- Reduces calibration frequency
- Compensates for camera drift
- Enables calibration-free setup (future)

---

## Implementation Roadmap

### Phase 1: Enhanced Data Collection (2 weeks)

**Goal:** Start capturing ML training data alongside coaching data

**Tasks:**
1. Add detection export to PitchRecorder
2. Add frame extraction at key points
3. Add calibration metadata export
4. Add environmental metadata collection
5. Update manifest schema

**Code Changes:**
```python
class PitchRecorder:
    def __init__(self, ...):
        self._save_frames = config.recording.save_training_frames  # NEW
        self._save_detections = config.recording.save_detections    # NEW
        self._detections = {"left": [], "right": []}                # NEW

    def write_frame(self, label, frame, detections=None):
        # Existing video write
        self._write_to_video(label, frame)

        # NEW: Save detections
        if self._save_detections and detections:
            self._detections[label].extend(detections)

        # NEW: Save key frames
        if self._save_frames and self._should_save_frame(label, frame):
            self._save_training_frame(label, frame)

    def close(self):
        # Existing video close
        ...

        # NEW: Export detections
        if self._save_detections:
            self._export_detections()
```

**Config Changes:**
```yaml
recording:
  save_training_frames: true       # NEW
  save_detections: true             # NEW
  frame_save_interval: 5            # NEW: Save every Nth frame
  save_environmental_metadata: true # NEW
```

### Phase 2: Annotation Tools (3 weeks)

**Goal:** Create tools to annotate existing data

**Tools Needed:**
1. **Frame Annotation UI**
   - Label ball bounding boxes
   - Draw ROI polygons
   - Mark batter keypoints
   - Export to COCO/YOLO format

2. **Detection Validator**
   - Review automated detections
   - Mark false positives/negatives
   - Correct bounding boxes
   - Export corrected ground truth

3. **Dataset Export**
   - Aggregate data from multiple sessions
   - Split train/val/test sets
   - Balance class distributions
   - Generate dataset.yaml

**UI Mockup:**
```
╔════════════════════════════════════════════════════════════════╗
║ Annotation Tool - Frame 42                                     ║
╠════════════════════════════════════════════════════════════════╣
║  Left Camera          │  Right Camera                          ║
║  [Image with bbox]    │  [Image with bbox]                     ║
║                       │                                         ║
║  Bbox: (320, 240)     │  Bbox: (280, 235)                      ║
║  Size: 24x24          │  Size: 23x25                           ║
║  Confidence: 0.95     │  Confidence: 0.92                      ║
║                       │                                         ║
║  [✓] True Positive    │  [✓] True Positive                     ║
║  [ ] False Positive   │  [ ] False Positive                    ║
║  [ ] Missed Detection │  [ ] Missed Detection                  ║
║                       │                                         ║
║  [Correct] [Skip] [Delete] [Next Frame]                        ║
╚════════════════════════════════════════════════════════════════╝
```

### Phase 3: Initial Model Training (4 weeks)

**Goal:** Train first version of ball detector model

**Steps:**
1. Collect 10,000+ labeled frames
   - Use existing recordings
   - Annotate with tool from Phase 2
   - Validate annotations

2. Train YOLOv8-nano model
   - Fine-tune from COCO weights
   - Train for 300 epochs
   - Validate on held-out data

3. Integrate model into detector
   - Add ML detector option
   - Compare with classical detector
   - A/B test on live data

4. Measure performance
   - Detection rate
   - False positive rate
   - Inference time
   - Compare vs manual tuning

**Success Criteria:**
- >95% detection rate
- <1% false positive rate
- <5ms inference time
- Works across 5+ different installations without tuning

### Phase 4: ROI Auto-Detection (4 weeks)

**Goal:** Train field segmentation model

**Steps:**
1. Collect 1,000+ labeled frames with field masks
2. Train U-Net segmentation model
3. Generate ROI polygons from segmentation
4. Integrate into calibration wizard

**Success Criteria:**
- >90% IoU on field segmentation
- Auto-generated ROIs work without modification in 80% of cases
- Reduces setup time from 10 minutes to <1 minute

### Phase 5: Strike Zone Auto-Detection (6 weeks)

**Goal:** Train batter pose estimation model

**Steps:**
1. Collect 5,000+ labeled frames with batter keypoints
2. Train HRNet pose model
3. Calculate strike zone from pose
4. Integrate into UI

**Success Criteria:**
- <10px keypoint error on test set
- Strike zone accurate within ±2 inches
- Works for 90% of batters without adjustment

### Phase 6: Self-Calibration (8 weeks)

**Goal:** Enable calibration refinement from pitch data

**Steps:**
1. Collect 1,000+ pitches with verified calibration
2. Train bundle adjustment network
3. Refine calibration from trajectories
4. Validate against checkerboard calibration

**Success Criteria:**
- Calibration drift detected and corrected automatically
- <0.5px reprojection error improvement
- Extends time between manual recalibration

---

## Configuration Changes Needed

### Add ML Training Options to Config

```yaml
# configs/default.yaml

recording:
  # Existing options
  pre_roll_ms: 500
  post_roll_ms: 500
  output_dir: "C:/Users/bergi/Desktop/pitchtracker_recordings"

  # NEW: ML training data collection
  ml_training_mode: false            # Enable enhanced data capture
  save_training_frames: false        # Save key frames as PNG
  frame_save_interval: 5             # Save every Nth frame
  save_all_detections: false         # Export detection JSON
  save_stereo_observations: false    # Export 3D trajectory points
  save_calibration_metadata: true    # Always save calibration
  save_environmental_metadata: false # Capture environment info

  # Frame selection strategy
  frame_selection: "keypoints"       # "keypoints" | "uniform" | "all"
  keypoints_strategy:
    save_pre_roll_first: true
    save_pre_roll_last: true
    save_first_detection: true
    save_release_point: true
    save_plate_crossing: true
    save_last_detection: true
    save_post_roll_last: true

ml_annotation:
  # Annotation assistance
  auto_generate_bboxes: true         # Use detector output as initial bbox
  bbox_margin_px: 5                  # Expand bbox by N pixels
  confidence_threshold: 0.7          # Min confidence to suggest bbox

dataset_export:
  # Dataset generation
  format: "yolo"                     # "yolo" | "coco" | "pascal_voc"
  train_split: 0.7
  val_split: 0.2
  test_split: 0.1
  balance_classes: true              # Balance positive/negative examples
```

### Add Detector Options

```yaml
detector:
  type: "ml"  # "classical" | "ml" | "ensemble"

  # ML detector options
  model_path: "models/ball_detector_v1.onnx"
  model_input_size: [640, 640]
  model_conf_threshold: 0.25
  model_iou_threshold: 0.45
  model_backend: "onnx"  # "onnx" | "tensorrt" | "openvino"

  # Ensemble options (use both classical and ML)
  ensemble_mode: "voting"  # "voting" | "confidence_max" | "ml_fallback"
  ensemble_agreement_threshold: 0.8
```

---

## Data Privacy & Ethics Considerations

### Player Privacy

**Concerns:**
- Players may be identifiable in videos
- Performance data is sensitive

**Mitigations:**
1. **Anonymization:**
   - Assign anonymous player IDs
   - No names or identifying info in metadata
   - Blur faces in exported frames (optional)

2. **Consent:**
   - Obtain consent for ML training use
   - Allow opt-out from training dataset
   - Clear data retention policy

3. **Access Control:**
   - Encrypted storage for training data
   - Access logs for dataset downloads
   - Limit data sharing to authorized researchers

### Data Ownership

**Policy:**
- Player owns coaching data (videos, summaries)
- Organization can use anonymized data for ML training with consent
- Clear licensing for trained models

---

## Storage Requirements

### Current Storage (Per Session)

```
Session videos: ~2 GB (30 min × 2 cameras × 30fps)
Pitch videos: ~100 MB each × 20 pitches = 2 GB
Manifests: <1 MB
Total: ~4 GB per session
```

### Enhanced Storage (With ML Training Data)

```
Session videos: ~2 GB (unchanged - for coaching)
Pitch videos: ~100 MB each × 20 pitches = 2 GB (unchanged)
Frames (PNG): ~500 KB each × 100 frames/pitch × 20 = 1 GB
Detections (JSON): ~10 KB/pitch × 20 = 200 KB
Observations (JSON): ~50 KB/pitch × 20 = 1 MB
Calibration metadata: ~500 KB
Annotations (future): ~200 KB/pitch × 20 = 4 MB
Total: ~5 GB per session (+25% increase)
```

**Optimization:**
- Compress frames with zstd (50% reduction)
- Save frames only for selected pitches
- Archive old sessions to cold storage
- **Estimated:** ~3.5 GB per session with compression

### ML Training Dataset Storage

**Goal:** Collect 10,000 labeled pitches for training

```
10,000 pitches × 3.5 GB = 35 TB raw data
After deduplication and selection: ~10 TB
With compression and frame selection: ~5 TB
```

**Storage Strategy:**
- Local NAS for recent sessions (2 TB)
- Cloud storage for training dataset (S3/Azure Blob)
- Dataset version control with DVC/Git LFS

---

## Success Metrics

### For Coaching (Existing)
✅ Video quality acceptable for review
✅ Trajectory data accurate within ±2 inches
✅ Strike zone classification >90% accurate
✅ Session summary helpful for coaching

### For ML Training (New)

**Dataset Quality:**
- [ ] 10,000+ labeled ball detections collected
- [ ] 1,000+ field segmentation masks annotated
- [ ] 5,000+ batter pose keypoints labeled
- [ ] 90%+ annotation agreement between annotators
- [ ] Balanced dataset (varied conditions, skill levels)

**Model Performance:**
- [ ] Ball detector: >95% detection rate, <1% FP, <5ms
- [ ] Field segmentation: >90% IoU, <20ms
- [ ] Batter pose: <10px keypoint error, <15ms
- [ ] Self-calibration: <0.5px reprojection error improvement

**Automation Impact:**
- [ ] Setup time reduced from 30 min to <5 min
- [ ] Zero manual detector tuning required
- [ ] ROI calibration automated in 80% of cases
- [ ] Strike zone calibration automated in 70% of cases

---

## Conclusion

**Current System:** Excellent for coaching, missing critical data for ML training

**Recommended Actions (Immediate):**
1. **Enable detection export** - Add JSON export of all detections (1 day)
2. **Save key frames** - Extract frames at pitch milestones (2 days)
3. **Export calibration metadata** - Save all calibration parameters (1 day)
4. **Update manifest schema** - Add performance metrics (1 day)

**Impact:** With these changes, you can:
- Start collecting ML training data immediately
- Build datasets while system is in use
- Train models to automate setup over time
- Reduce manual configuration dramatically

**ROI Timeline:**
- **3 months:** 10,000 labeled pitches collected
- **6 months:** First ball detector model trained and deployed
- **9 months:** ROI auto-detection working
- **12 months:** Strike zone auto-detection working
- **18 months:** Near-zero configuration setup achieved

**The key insight:** Every pitch you capture now can serve dual purpose if you save the right metadata and annotations. Start collecting this data immediately, even if models aren't ready yet.
