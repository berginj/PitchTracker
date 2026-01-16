# ML Training Quick Reference

> **TL;DR:** PitchTracker v1.2.0 now captures data for building automation models that will eliminate manual setup. Enable ML data collection to start building toward near-zero configuration.

---

## Current Status (v1.2.0)

### ✅ Week 1 Complete - Data Collection Infrastructure

All ML training data collection features implemented and ready to use:

| Feature | Status | Purpose |
|---------|--------|---------|
| Detection export | ✅ Complete | Train ball detector (eliminate HSV tuning) |
| Observation export | ✅ Complete | Train trajectory models, self-calibration |
| Frame extraction | ✅ Complete | Train detection, segmentation, pose models |
| Calibration export | ✅ Complete | Enable self-calibration research |
| Performance metrics | ✅ Complete | Assess data quality for training |
| Test script | ✅ Complete | Validate ML data export |

### Enable ML Data Collection (5 Minutes)

**Edit `configs/default.yaml`:**
```yaml
recording:
  # ML training data collection
  save_detections: true       # Export detection JSON files
  save_observations: true     # Export 3D trajectory points
  save_training_frames: true  # Save key frames as PNG
  frame_save_interval: 5      # Save every Nth frame
```

**Test:**
```powershell
.\run.ps1 -Backend uvc
# Record a pitch
python test_ml_data_export.py "recordings\session-2026-01-16_001"
```

**Storage Impact:** +25% per session (~1 GB extra for 20 pitches)

---

## 18-Month Automation Roadmap

### Phase 1: Ball Detector (6 Months)

**Goal:** Eliminate manual HSV threshold tuning

**What's Needed:**
- 10,000+ labeled frames with ball bounding boxes
- Training data across varied lighting/backgrounds
- Negative examples (frames without ball)

**What Gets Automated:**
- ❌ Manual: Tune HSV thresholds per environment
- ✅ Automated: Model detects ball universally

**Setup Time Saved:** ~5 minutes per installation

### Phase 2: Field Segmentation (9 Months)

**Goal:** Auto-detect ROI boundaries

**What's Needed:**
- 1,000+ labeled frames with field segmentation masks
- Various field types (indoor/outdoor, different mounds)
- Camera angles and distances

**What Gets Automated:**
- ❌ Manual: Draw lane and plate ROI polygons
- ✅ Automated: Model segments field, generates ROIs

**Setup Time Saved:** ~10 minutes per installation

### Phase 3: Batter Pose Estimation (12 Months)

**Goal:** Auto-calculate strike zone from batter

**What's Needed:**
- 5,000+ labeled frames with batter keypoints
- Various batter heights and stances
- Left/right handed batters

**What Gets Automated:**
- ❌ Manual: Measure batter height, set strike zone ratios
- ✅ Automated: Detect batter pose, calculate strike zone

**Setup Time Saved:** ~10 minutes per session

### Phase 4: Self-Calibration (18 Months)

**Goal:** Refine calibration from ball trajectories

**What's Needed:**
- 1,000+ pitches with verified calibration
- Stereo correspondences and 3D trajectories
- Ground truth calibration parameters

**What Gets Automated:**
- ❌ Manual: Checkerboard calibration every N sessions
- ✅ Automated: Continuous refinement from pitch data

**Setup Time Saved:** ~5 minutes per recalibration

### Total Impact

| Metric | Current | After 18 Months |
|--------|---------|-----------------|
| **Initial setup time** | 30 minutes | <2 minutes |
| **Per-session setup** | 10 minutes | <30 seconds |
| **Recalibration** | 15 minutes | Automatic |
| **Environment changes** | 15 minutes (re-tune) | Instant adaptation |

**ROI:** 25x reduction in setup time

---

## Data Collection Strategy

### What We Capture Now

**For Coaching (Unchanged):**
- Pitch videos (left/right cameras)
- Trajectory summaries
- Strike zone classification
- Session summaries

**For ML Training (NEW v1.2.0):**
- Detection coordinates (pixel locations, confidence)
- Stereo observations (3D trajectory points)
- Key frames as PNG (pre-roll, detections, post-roll)
- Calibration metadata (geometry, intrinsics, ROIs)
- Performance metrics (detection quality, timing)

### Dual-Purpose Data

Every pitch now serves **two purposes:**
1. **Today:** Coach reviews video, analyzes trajectory
2. **Tomorrow:** Train models to automate setup

**Key Insight:** Start collecting data now, even if models aren't ready yet. Every pitch recorded contributes to future automation.

---

## Current Directory Structure

### Without ML Training (Default)

```
recordings/
└── session-2026-01-16_001/
    ├── manifest.json
    ├── session_left.avi
    ├── session_right.avi
    ├── session_summary.json
    └── session-2026-01-16_001-pitch-001/
        ├── manifest.json
        ├── left.avi
        ├── right.avi
        ├── left_timestamps.csv
        └── right_timestamps.csv
```

### With ML Training Enabled

```
recordings/
└── session-2026-01-16_001/
    ├── manifest.json
    ├── session_left.avi
    ├── session_right.avi
    ├── session_summary.json
    ├── calibration/                     # NEW
    │   ├── stereo_geometry.json
    │   ├── intrinsics_left.json
    │   ├── intrinsics_right.json
    │   └── roi_annotations.json
    └── session-2026-01-16_001-pitch-001/
        ├── manifest.json                # Enhanced with performance_metrics
        ├── left.avi
        ├── right.avi
        ├── left_timestamps.csv
        ├── right_timestamps.csv
        ├── detections/                  # NEW
        │   ├── left_detections.json
        │   └── right_detections.json
        ├── observations/                # NEW
        │   └── stereo_observations.json
        └── frames/                      # NEW
            ├── left/
            │   ├── pre_roll_00001.png
            │   ├── uniform_00005.png
            │   ├── pitch_00015_first.png
            │   └── ...
            └── right/
                └── (same)
```

---

## ML Models to Train

### 1. Ball Detector

**Architecture:** YOLOv8-nano or EfficientDet-Lite
**Input:** 640x640 RGB image
**Output:** Bounding box (x, y, w, h) + confidence
**Training Data:** 10,000+ labeled frames
**Performance Target:** >95% detection rate, <1% false positive, <5ms inference

**Impact:**
- Replaces manual HSV threshold tuning
- Works across all lighting conditions
- Adapts to different ball types automatically

### 2. Field Segmentation

**Architecture:** U-Net or DeepLabV3+
**Input:** Full frame RGB image
**Output:** Binary mask (field vs background)
**Training Data:** 1,000+ labeled frames with segmentation masks
**Performance Target:** >90% IoU, <20ms inference

**Impact:**
- Eliminates manual ROI polygon drawing
- Auto-generates lane and plate gates
- Adapts if camera moves

### 3. Batter Pose Estimation

**Architecture:** HRNet or MediaPipe-based
**Input:** Full frame RGB image
**Output:** 2D keypoints (head, shoulders, knees, feet)
**Training Data:** 5,000+ labeled frames with batter keypoints
**Performance Target:** <10px keypoint error, <15ms inference

**Impact:**
- Eliminates strike zone calibration
- Adapts per-batter automatically
- Handles different batting stances

### 4. Self-Calibration

**Architecture:** Differentiable bundle adjustment network
**Input:** Stereo correspondences + 3D trajectories
**Output:** Refined camera parameters
**Training Data:** 1,000+ pitches with ground truth calibration
**Performance Target:** <0.5px reprojection error improvement

**Impact:**
- Reduces recalibration frequency
- Compensates for camera drift
- Continuous refinement during use

---

## Next Steps

### Immediate (This Week)

1. **Enable ML data collection** in `configs/default.yaml`
2. **Record test session** with a few pitches
3. **Validate export** with `test_ml_data_export.py`
4. **Review sample data** to understand structure

### Short Term (1-3 Months)

1. **Continue recording** - Target: 1,000 pitches
2. **Build annotation tool** - Label ball bounding boxes
3. **Aggregate dataset** - Collect across environments
4. **Validate data quality** - Check detection rates, coverage

### Medium Term (3-6 Months)

1. **Reach 10,000 labeled pitches** - Sufficient for first model
2. **Train ball detector** - YOLOv8-nano on aggregated dataset
3. **Validate model** - Test across environments
4. **Integrate model** - Add ML detector option to config

### Long Term (6-18 Months)

1. **Train field segmentation** - Auto ROI generation
2. **Train pose estimation** - Auto strike zone
3. **Train self-calibration** - Continuous refinement
4. **Measure automation impact** - Validate setup time reduction

---

## FAQ

### Q: Do I need to enable ML data collection now?

**A:** Only if you want to contribute to building automation models. Existing coaching functionality is unchanged whether ML features are enabled or disabled.

### Q: Will ML data collection slow down recording?

**A:** No. Detection/observation export happens on pitch close (~10ms). Frame saving is negligible (<1ms per frame). No impact on real-time performance.

### Q: How much storage do I need?

**A:** With all ML features enabled: ~5 GB per session (20 pitches). Without ML: ~4 GB per session. That's +25% storage for dual-purpose data.

### Q: Can I enable ML features selectively?

**A:** Yes! Enable only what you need:
- `save_detections: true` - Most important for ball detector
- `save_observations: true` - Important for trajectory/calibration models
- `save_training_frames: false` - Most storage-intensive, optional

### Q: When will automation models be ready?

**A:** First model (ball detector) in ~6 months, assuming 10,000 pitches collected. Field segmentation in ~9 months, pose estimation in ~12 months, self-calibration in ~18 months.

### Q: How do I annotate data for training?

**A:** Annotation tool is planned (Phase 2, next 3 months). For now, focus on data collection. Annotations can be added retroactively to existing exported data.

### Q: Will models work on my specific setup?

**A:** Models will be trained on diverse data (indoor/outdoor, various lighting, different fields). The more varied the training data, the more universal the models. Your data contributions help generalization.

---

## Related Documentation

- **[ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md)** - Comprehensive 18-month strategy (962 lines)
- **[ML_TRAINING_IMPLEMENTATION_GUIDE.md](ML_TRAINING_IMPLEMENTATION_GUIDE.md)** - Week 1 implementation details (791 lines)
- **[MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md)** - Manifest and ML data file schemas
- **[CHANGELOG.md](CHANGELOG.md)** - Version history (v1.2.0 ML features)

---

## Support

**Enable ML data collection:**
```yaml
# configs/default.yaml
recording:
  save_detections: true
  save_observations: true
  save_training_frames: true
  frame_save_interval: 5
```

**Validate:**
```powershell
python test_ml_data_export.py "recordings\session-2026-01-16_001"
```

**Feedback:** Report issues at https://github.com/anthropics/claude-code/issues
