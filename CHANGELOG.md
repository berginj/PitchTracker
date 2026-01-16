# Changelog

## 1.2.0 (2026-01-16)

### Added - ML Training Data Collection
- **Detection export** - All ball detections saved to JSON with pixel coordinates, confidence scores, timestamps
- **Observation export** - Stereo observations (3D trajectory points) saved to JSON with 2D/3D coordinates
- **Frame extraction** - Key frames saved as PNG at critical moments (pre-roll, first detection, uniform intervals, last detection, post-roll)
- **Calibration export** - Stereo geometry, camera intrinsics, and ROI polygons automatically exported per session
- **Performance metrics** - Manifest enhanced with detection quality, timing accuracy, and observation counts
- **Test script** - `test_ml_data_export.py` validates all ML data export features

### New Modules
- `app/pipeline/recording/frame_extractor.py` - Extracts and saves key frames as PNG
- `app/pipeline/recording/calibration_export.py` - Exports calibration metadata for ML training
- `test_ml_data_export.py` - Validation script for ML data export

### Changed - Dual-Purpose Data Capture
- `app/pipeline/recording/pitch_recorder.py` - Added detection/observation/frame storage
  - New method: `write_frame_with_detections()` - Stores detection data alongside video
  - New method: `add_observation()` - Stores stereo observations for export
  - Integrated `FrameExtractor` for key frame saving
  - Export methods: `_export_detections()`, `_export_observations()`
- `app/pipeline_service.py` - Integrated ML data collection
  - Detection results passed to `pitch_recorder` via `write_frame_with_detections()`
  - Observations passed to `pitch_recorder` via `add_observation()`
  - Calibration metadata exported on session start
  - Performance metrics collected and passed to manifest
- `app/pipeline/recording/manifest.py` - Enhanced with performance metrics
  - `create_pitch_manifest()` now accepts optional `performance_metrics` parameter
  - Manifest includes detection quality and timing accuracy data
- `configs/settings.py` - Added ML training configuration options
  - `RecordingConfig.save_detections` - Enable detection JSON export
  - `RecordingConfig.save_observations` - Enable observation JSON export
  - `RecordingConfig.save_training_frames` - Enable frame extraction
  - `RecordingConfig.frame_save_interval` - Frame sampling rate
- `configs/default.yaml` - Added ML training config (disabled by default)

### New Directory Structure
```
session-001/
├── calibration/                     # NEW: Calibration metadata
│   ├── stereo_geometry.json
│   ├── intrinsics_left.json
│   ├── intrinsics_right.json
│   └── roi_annotations.json
└── session-001-pitch-001/
    ├── manifest.json                # Enhanced with performance_metrics
    ├── detections/                  # NEW: Detection data
    │   ├── left_detections.json
    │   └── right_detections.json
    ├── observations/                # NEW: 3D trajectory data
    │   └── stereo_observations.json
    └── frames/                      # NEW: Key frames for training
        ├── left/*.png
        └── right/*.png
```

### Configuration
Enable ML training data collection in `configs/default.yaml`:
```yaml
recording:
  save_detections: true       # Export detection JSON files
  save_observations: true     # Export 3D trajectory points
  save_training_frames: true  # Save key frames as PNG
  frame_save_interval: 5      # Save every Nth frame
```

### Documentation
- `ML_TRAINING_DATA_STRATEGY.md` - 18-month roadmap to near-zero configuration
- `ML_TRAINING_IMPLEMENTATION_GUIDE.md` - Week 1 implementation details

### Purpose
Enable dual-purpose data capture:
1. **Coaching** - Videos and summaries for player review (unchanged)
2. **ML Training** - Detections, observations, frames, and calibration for building automation models

### Storage Impact
- With all ML features enabled: +25% per session (~1 GB extra for 20 pitches)
- All ML features disabled by default - no impact on existing workflows

### Future Automation (18-Month Roadmap)
Data collected enables training 4 models to eliminate manual setup:
1. **Ball detector** (6 months) - Eliminate HSV threshold tuning
2. **Field segmentation** (9 months) - Auto-detect ROI boundaries
3. **Batter pose estimation** (12 months) - Auto-calculate strike zone
4. **Self-calibration** (18 months) - Refine calibration from trajectories

**Goal:** Reduce setup time from 30 minutes to <2 minutes

## 1.1.0 (2026-01-16)

### Added - Pitch Tracking V2
- **Zero data loss architecture** replacing V1 with critical bug fixes
- **Pre-roll buffering** - Frames captured continuously BEFORE pitch detection
- **Ramp-up observation capture** - Explicit RAMP_UP phase prevents data loss during confirmation
- **Thread-safe operations** - RLock protects all state access for concurrent camera threads
- **Accurate timing** - Uses first/last detection timestamps (not trigger/gap frames)
- **Data validation** - Minimum observations (3) and duration (100ms) requirements
- **False trigger filtering** - Short bursts (<100ms) automatically rejected
- **Error recovery** - Callback exceptions handled gracefully with state rollback
- **Event logging** - Circular buffer (1000 events) for debugging
- **Comprehensive test suite** - 8/8 automated tests passing, 500+ lines of unit tests

### Fixed - V1 Critical Issues
- **Pre-roll buffer always empty** (V1 bug) - Was buffered AFTER pitch starts, now buffered continuously before detection
- **Lost ~5 observations during ramp-up** (V1 bug) - No ramp-up phase, observations now captured and promoted
- **Timing errors of ±330ms** (V1 bug) - Used trigger frame instead of first/last detection, now accurate to <33ms
- **Race conditions** (V1 bug) - No thread safety, now fully thread-safe with RLock
- **Callback exceptions corrupt state** (V1 bug) - No error handling, now recovers gracefully
- **No data validation** (V1 bug) - Saved empty/junk pitches, now validates before finalization
- **No false trigger filtering** (V1 bug) - Random noise triggered pitches, now filtered by duration
- **Total data loss eliminated:** ~16 frames per pitch (~533ms @ 30fps)

### Changed
- `app/pipeline_service.py` - Integrated V2 pitch tracking
  - Updated imports to use `pitch_tracking_v2`
  - Changed callback signatures to use `PitchData` object
  - Added `buffer_frame()` calls for continuous pre-roll buffering
  - Updated `PitchConfig` initialization with validation parameters

### Deprecated
- `app/pipeline/pitch_tracking.py` (V1) - Archived to `archive/deprecated/pitch_tracking_v1.py`
  - V1 had 12 critical issues causing data loss and timing errors
  - V2 is production-ready replacement with all issues fixed
  - V1 preserved for reference only

### Documentation
- `PITCH_TRACKING_V2_GUIDE.md` - Complete integration guide
- `PITCH_TRACKING_V2_SUMMARY.md` - Quick V1 vs V2 comparison
- `PITCH_TRACKING_V2_INTEGRATION.md` - Integration changes summary
- `PITCH_TRACKING_ANALYSIS.md` - Detailed analysis of V1 issues
- `V2_TEST_RESULTS.md` - Comprehensive test results
- `V2_CLEANUP_TASKS.md` - Optional cleanup and enhancement tasks

### Performance Impact
- Memory: +2 MB (pre-roll buffers) - Negligible
- CPU: +0.07ms per frame (RLock overhead) - Negligible
- Accuracy: +500ms better timing - **Significant improvement**
- Data loss: -16 frames per pitch - **Zero data loss**

## 1.0.0
- Initial session summary schema.
