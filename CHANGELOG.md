# Changelog

## 1.5.0 (2026-01-19)

### Pattern Detection System - Complete UI Integration

**New Features:**
- **Pattern Analysis Dialog** - One-click pattern detection with tabbed results interface
  - Summary tab: Pitch counts, velocity, strikes, consistency, repertoire
  - Anomalies tab: Unusual pitches with severity levels and recommendations
  - Pitch Types tab: Classification results with confidence scores
  - Baseline tab: Comparison to pitcher's historical performance
- **"Analyze Patterns" Button** - Integrated into Session Summary dialog for instant access
- **Pitcher Profile Integration** - Saved profiles appear in coaching session start dialog
- **30-Second Workflow** - From session end to viewing results (vs 5-10 minutes CLI)

**Pattern Detection Features (Implemented):**
- **Pitch Type Classification** - MLB-standard heuristic rules + K-means clustering hybrid approach
- **Anomaly Detection** - Multi-method ensemble (Z-score + IQR intersection) with trajectory quality analysis
- **Pitcher Profiles** - Opt-in baseline tracking with session history and performance comparison
- **HTML Reports** - Self-contained reports with embedded charts (velocity, movement, heatmap, repertoire)
- **JSON Export** - Machine-readable analysis data with complete diagnostics
- **Cross-Session Analysis** - Velocity trends, strike consistency, pitch mix evolution

### Testing & Quality Improvements

**Test Suite:**
- **45 Pattern Detection Tests** - 100% passing (pitch classification, anomaly detection, profiles, integration)
- **375 Total Tests Executed** - ~85% pass rate (320+ passing)
- **0 Critical Failures** - No production blockers identified
- **Comprehensive Documentation** - `TEST_SUITE_DOCUMENTATION.md` with detailed failure analysis

**Python 3.13 Compatibility:**
- Fixed deprecated `datetime.utcnow()` → `datetime.now(UTC)` (6 occurrences)
- Eliminated 57 deprecation warnings

**Test Improvements:**
- Increased statistical sample sizes (5→10-11 pitches) for reliable anomaly detection
- Fixed pitcher profile session tracking (accumulative sessions)
- Fixed dict access patterns in profile tests
- All pattern detection tests passing at 100%

### Documentation

**New Documentation:**
- `docs/TEST_SUITE_DOCUMENTATION.md` - Exhaustive test suite documentation (~1000 lines)
  - Complete test breakdown (376 tests across all modules)
  - Detailed failure analysis by severity
  - Performance benchmark specifications
  - Test execution instructions
- `docs/UNICODE_CHARACTERS_GUIDE.md` - Unicode character usage explanation (~400 lines)
  - Intentional Unicode symbols for readability
  - UTF-8 encoding standard compliance
  - Display compatibility matrix
  - Windows CMD limitations and fixes
- `docs/PATTERN_DETECTION_GUIDE.md` - Updated with UI workflows
  - UI vs CLI usage guidelines
  - Quick start with screenshots
  - Pattern analysis workflow
  - Pitcher profile management

**Updated Documentation:**
- `docs/CURRENT_STATUS.md` - Updated project status with pattern detection completion
- `docs/SESSION_SUMMARY_2026-01-19_UI_INTEGRATION.md` - Complete implementation session log
- `README.md` - Updated with pattern detection quick start

### Files Modified

**Pattern Detection UI:**
- `ui/dialogs/pattern_analysis_dialog.py` - NEW (415 lines) - Main pattern analysis UI
- `ui/dialogs/session_summary_dialog.py` - Added "Analyze Patterns" button
- `ui/main_window.py` - Pass session_dir parameter for analysis
- `ui/coaching/dialogs/session_start.py` - Integrated pitcher profiles with coaching UI

**Pattern Detection Core:**
- `analysis/pattern_detection/pitcher_profile.py` - Fixed session tracking, datetime deprecation
- `analysis/pattern_detection/detector.py` - Pass session count to profile manager, datetime deprecation
- `analysis/pattern_detection/schemas.py` - Fixed datetime deprecation

**Tests:**
- `tests/analysis/test_anomaly_detector.py` - Increased sample sizes for statistical reliability
- `tests/analysis/test_pitcher_profile.py` - Fixed dict access patterns, session tracking expectations

### Performance

**Pattern Detection Performance:**
- Classification: <1ms per pitch (heuristics), ~2-5ms total for 100 pitches (K-means)
- Anomaly Detection: <5ms for 100 pitches
- JSON Generation: <5ms for 100 pitches
- HTML + Charts: 50-100ms for 100 pitches
- **Total: <120ms for 100 pitches** (target: <5 seconds) ✓

**UI Workflow:**
- Session end → pattern analysis: ~30 seconds (vs 5-10 minutes CLI)
- One-click access from Session Summary dialog
- Instant feedback with progress indicators

### Commits

- `9908d5d` - Add comprehensive production readiness status document
- `0c2150a` - Fix resource leak test parameter names
- `e198e88` - Add comprehensive user-facing documentation
- `0a8f9b7` - Add comprehensive session summary for 2026-01-18
- `d126b8c` - Add state corruption recovery and error bus integration
- `da59fb7` - Add comprehensive test suite and Unicode documentation for v1.5.0

---

## 1.3.0 (2026-01-18)

### Performance Optimizations - 3-5x Overall Improvement

**Phase 1: Critical Optimizations (10-100x speedup)**
- **OpenCV connected components** - Replaced pure-Python BFS with `cv2.connectedComponentsWithStats` (10-20x faster blob detection)
- **OpenCV Sobel edges** - Replaced manual convolution with `cv2.Sobel` (50-100x faster edge detection)
- **Memory-efficient backgrounds** - Store background models as uint8 instead of float32 (75% memory reduction per camera, -7.2MB total)
- **NumPy multi-threading** - Configured OMP, MKL, OpenBLAS thread counts for multi-core utilization

**Phase 2: High-Priority Optimizations (30-50% improvement)**
- **Epipolar pre-filtering** - Apply epipolar constraint to reduce stereo match candidates by 80-90% (50 → 5-10 matches typical)
- **Lock-free error tracking** - Minimize critical sections and release locks before I/O operations (15-30% latency reduction)

**Phase 3: Low-Priority Optimizations (5-20% improvement)**
- **Adaptive queue sizing** - Dynamically adjust queue depth (3-12) based on drop patterns (5-15% frame retention improvement)
- **Strike zone caching** - Cache strike zone computation across frames, rebuild only on config change (10-20% metrics latency reduction)
- **BGR buffer pre-allocation** - Reuse buffer for grayscale→BGR conversion during recording (5-10% video writing speedup)

### Performance Impact Summary

**Before (v1.2.0):**
- Detection: ~30 FPS per camera
- Stereo latency: ~30ms
- Match candidates: 50 per stereo pair
- Memory: ~120MB working set
- CPU: ~60% on 4-core system

**After (v1.3.0):**
- Detection: 60-90 FPS per camera (2-3x improvement)
- Stereo latency: 15-20ms (1.5-2x improvement)
- Match candidates: 5-10 per stereo pair (80-90% reduction)
- Memory: ~100MB working set (16% reduction)
- CPU: ~35% on 4-core system (42% reduction)

**Overall: 3-5x end-to-end performance improvement**

### Files Modified
- `detect/utils.py` - OpenCV-optimized algorithms
- `detect/modes.py` - uint8 background model storage
- `ui/qt_app.py` - Multi-threading configuration
- `app/pipeline/utils.py` - Epipolar stereo matching
- `app/pipeline/detection/threading_pool.py` - Lock-free I/O, adaptive queuing
- `app/pipeline/detection/processor.py` - Strike zone caching
- `record/dual_capture.py` - BGR buffer pre-allocation

### Documentation
- `PERFORMANCE_OPTIMIZATION.md` - Detailed analysis and implementation roadmap
- `OPTIMIZATION_SUMMARY.md` - Complete implementation summary with validation guide
- `PERFORMANCE_BENCHMARKS.md` - Benchmark results and methodology
- `MEMORY_LEAK_TESTING.md` - Memory stability validation
- `README.md` - Updated with performance characteristics and hardware recommendations

### Commits
- `6f4b337` - Phase 1: Critical optimizations (10-100x)
- `61912d0` - Phase 2: High-priority optimizations (30-50%)
- `7450045` - Phase 3: Low-priority optimizations (5-20%)
- `8e59280` - Documentation updates
- `cdd3841` - Optimization summary

---

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

### Cloud Submission
- `export_ml_submission.py` - Package sessions for cloud ML training upload
- Two variants: Full (videos + telemetry) and Telemetry-only (no videos)
- Full package enables all 5 ML models (100% automation roadmap)
- Telemetry-only enables 2 of 5 models (privacy-preserving, 40% automation)

### Documentation
- `ML_TRAINING_DATA_STRATEGY.md` - 18-month roadmap to near-zero configuration
- `ML_TRAINING_IMPLEMENTATION_GUIDE.md` - Week 1 implementation details
- `CLOUD_SUBMISSION_SCHEMA.md` - Cloud upload contract and API specification
- `ML_QUICK_REFERENCE.md` - Quick start guide for ML features

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
