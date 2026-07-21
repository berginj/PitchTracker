# Auto-Calibration System

The PitchTracker now includes a comprehensive auto-calibration system that simplifies setup while maintaining accuracy. This system includes camera capability detection, quick calibration mode, and online parameter refinement.

## Features

### 1. Camera Capability Detection

Automatically detects camera type (webcam vs industrial) and provides tailored recommendations.

**Detection Methods:**
- **Warmup Stability**: Monitors brightness variance over 20 frames
- **Focus Stability**: Tracks Laplacian variance over 30 frames
- **Focal Drift**: Uses ORB feature matching to detect scale changes over 5 seconds
- **UVC Query**: Future support for querying camera capabilities directly

**Classification:**
- **Industrial (Fixed Focus)**: Focus CV < 0.05, Focal drift < 1%
- **Webcam (Autofocus)**: Focus CV > 0.15, Focal drift > 5%
- **Unknown**: Between thresholds

### 2. Quick Calibration Mode

Fast calibration requiring only 3-5 image pairs instead of 10-15, completing in under 3 minutes.

**Key Features:**
- Simplified parameter estimation (zero distortion, fixed principal point)
- Achieves 90-95% accuracy compared to full calibration
- Quality thresholds: RMS < 2.0px = GOOD, < 3.0px = ACCEPTABLE
- Recommended for webcams and casual users

**Trade-offs:**
- Full calibration: 0.3-0.5px RMS error (EXCELLENT)
- Quick calibration: 1.0-2.0px RMS error (GOOD/ACCEPTABLE)
- Missing distortion adds ~1px error (acceptable for most use cases)

### 3. Online Parameter Refinement

Automatically improves calibration parameters over time using pitch tracking data.

**Refinable Parameters:**
- ✅ Drag coefficient (drag_k0): Refined from trajectory fits
- ✅ Time sync offset: Corrects systematic time synchronization bias
- ✅ Plate plane Z: Adjusts strike zone reference location

**Non-Refinable** (require full recalibration):
- ❌ Baseline: Needs known world scale
- ❌ Focal length: Needs multi-view geometry
- ❌ Rotation/Translation: Needs extrinsic reference

**How It Works:**
1. Accumulates high-confidence trajectories (>70% confidence, <2px error)
2. After 50 trajectories, analyzes systematic biases
3. Refines parameters if bias exceeds thresholds (drag >10%, time sync >5ms, plate Z >1ft)
4. Updates config automatically
5. Monitors calibration health and alerts if degradation detected

## Usage

### Running Quick Calibration

**Option 1: Via UI (Recommended)**
1. Open PitchTracker Setup Doctor
2. Navigate to the calibration diagnostics step
3. Wait for automatic camera detection (~30 seconds)
4. Select **Quick** mode from radio buttons
5. Capture 3-5 ChArUco board poses
6. Calibration completes automatically

Quick calibration is diagnostic/fallback-only. Use full matrix calibration in Setup Doctor for a production-ready active rig profile.

**Option 2: Via Command Line**
```bash
python -m calib.quick_calibrate \
    --quick \
    --left-dir recordings/calib_20250210/left \
    --right-dir recordings/calib_20250210/right \
    --pattern-size 7 5 \
    --square-mm 30.0 \
    --config configs/default.yaml
```

### Camera Detection

Camera detection runs automatically when you enter the calibration step. Results are displayed:

```
Camera Type: Industrial ✓
Stability Score: 95/100
Recommendations:
  • Fixed focal length detected
  • Excellent stability for accurate tracking
  • Full calibration recommended for best accuracy
```

For webcams:
```
Camera Type: Webcam ⚠
Stability Score: 65/100
Recommendations:
  ⚠ Autofocus camera detected
  • Disable autofocus in camera settings for best accuracy
  • Use manual focus or consider upgrading to industrial cameras
  • Quick calibration mode recommended (less sensitive to drift)
```

### Online Refinement

Online refinement is enabled by default. To monitor refinement status:

**Via Python API:**
```python
from app.services.analysis.implementation import AnalysisServiceImpl

# Get refinement summary
summary = analysis_service.get_refinement_summary()

if summary:
    print(f"Drag coefficient: {summary['drag_k0']:.4f}")
    print(f"Trajectories accumulated: {summary['trajectories_accumulated']}")
    print(f"Calibration healthy: {summary['calibration_healthy']}")
    print(f"Mean epipolar error: {summary['mean_epipolar_error_px']:.2f}px")
```

**Configuration:**
```yaml
# configs/default.yaml

metrics:
  online_refinement_enabled: true  # Enable/disable refinement
  drag_k0_default: 0.1             # Refined automatically
  plate_plane_z_ft: 0.0            # Refined automatically

stereo:
  time_sync_offset_ns: 0           # Refined automatically

calibration_validation:
  enabled: true
  alert_threshold_px: 5.0          # Alert when error exceeds this
  recalibration_interval_days: 30  # Suggest recalibration every N days
  min_trajectories_for_refinement: 50
```

## Quality Thresholds

### Quick Calibration
- **GOOD**: RMS < 2.0px, 5+ images
- **ACCEPTABLE**: RMS < 3.0px, 3+ images
- **POOR**: RMS ≥ 3.0px

### Full Calibration
- **EXCELLENT**: RMS < 0.5px, 15+ images
- **GOOD**: RMS < 1.0px, 10+ images
- **ACCEPTABLE**: RMS < 2.0px, 5+ images
- **POOR**: RMS ≥ 2.0px

### Online Refinement
- **MIN_CONFIDENCE**: 0.70 (minimum trajectory confidence)
- **MAX_EPIPOLAR_ERROR**: 2.0px (maximum epipolar error)
- **MIN_TRAJECTORIES**: 50 (accumulate before refining)
- **BIAS_THRESHOLD**: 10% (refine if bias exceeds)

## Calibration Health Monitoring

The system continuously monitors calibration health:

**Metrics:**
- **Epipolar error trend**: Tracks error over last 100 trajectories
- **Trend classification**: Stable, improving, or degrading
- **Alert conditions**:
  - Mean error > 5.0px
  - 30+ days since last refinement

**Example Alert:**
```
⚠ Calibration health alert: High epipolar error (6.2px). Recalibration recommended.
```

## Troubleshooting

### Webcam Autofocus Issues

**Problem**: Webcam with autofocus causes focal drift during calibration.

**Solutions:**
1. **Disable autofocus** in camera settings:
   - Windows: Camera app → Settings → Manual focus
   - Third-party apps: Use software like Webcam Settings or Camera Controls

2. **Use quick calibration**: Less sensitive to drift

3. **Upgrade hardware**: Consider industrial cameras with manual focus

### Low Calibration Quality

**Problem**: Calibration RMS error is high (>3px).

**Solutions:**
1. **Ensure good lighting**: Avoid shadows on calibration board
2. **Keep board flat**: Board should be perfectly flat, not warped
3. **Vary board positions**: Capture from different angles and distances
4. **Use full calibration**: More image pairs = better accuracy
5. **Check camera focus**: Ensure cameras are in focus before calibration

### Online Refinement Not Working

**Problem**: Parameters not being refined after many pitches.

**Checklist:**
1. Verify `online_refinement_enabled: true` in config
2. Check trajectory confidence: Must be >70%
3. Check epipolar error: Must be <2.0px
4. Verify 50+ trajectories accumulated
5. Check logs for refinement attempts

## Configuration Reference

### Camera Metadata
```yaml
camera:
  type: null  # Auto-set: "webcam", "industrial", "unknown"
  has_autofocus: null  # Auto-detected: true/false/null
  focal_stability_score: null  # 0-100, auto-computed
```

### Calibration Metadata
```yaml
stereo:
  calibration_mode: null  # Auto-set: "QUICK" or "FULL"
  calibration_date: null  # ISO timestamp
  calibration_quality_rating: null  # "EXCELLENT", "GOOD", "ACCEPTABLE", "POOR"
  calibration_rms_error_px: null  # Reprojection error
  calibration_num_images: null  # Number of image pairs used
  time_sync_offset_ns: 0  # Refined online
```

### Refinement Settings
```yaml
metrics:
  online_refinement_enabled: true
  last_refinement_date: null  # ISO timestamp
  drag_k0_default: 0.1  # Refined online

calibration_validation:
  enabled: true
  alert_threshold_px: 5.0
  recalibration_interval_days: 30
  min_trajectories_for_refinement: 50
```

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    PitchTracker System                       │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Camera       │    │ Quick        │    │ Online       │
│ Detection    │    │ Calibration  │    │ Refinement   │
└──────────────┘    └──────────────┘    └──────────────┘
```

### File Structure

```
PitchTracker/
├── calib/
│   ├── camera_capabilities.py     # Camera detection (500 lines)
│   ├── quick_calibrate.py         # Quick mode (300 lines added)
│   └── online_refinement.py       # Parameter refinement (450 lines)
│
├── app/services/analysis/
│   └── implementation.py          # Integration point
│
├── tests/
│   ├── test_camera_capabilities.py   # 16 tests
│   ├── test_quick_calibrate.py       # 9 tests
│   └── test_online_refinement.py     # 26 tests
│
├── configs/
│   └── default.yaml               # Configuration schema
│
└── docs/
    └── AUTO_CALIBRATION.md        # This file
```

## Testing

Run all auto-calibration tests:
```bash
python -m pytest tests/test_camera_capabilities.py \
                tests/test_quick_calibrate.py \
                tests/test_online_refinement.py -v
```

Expected: **51 tests passing**

## Performance

- **Camera detection**: ~30 seconds (one-time per session)
- **Quick calibration**: <3 minutes (3-5 image pairs)
- **Full calibration**: 10-15 minutes (10-15 image pairs)
- **Online refinement**: Background process, no user impact

## Future Enhancements

1. **UVC Camera Query**: Direct autofocus capability detection
2. **Time Sync Residual**: Extract from trajectory fitting for better refinement
3. **Automatic Recalibration**: Trigger when health degrades significantly
4. **Multi-Camera Support**: Extend to more than 2 cameras
5. **Web UI**: Browser-based calibration interface

## References

- **Camera Capabilities**: `calib/camera_capabilities.py`
- **Quick Calibration**: `calib/quick_calibrate.py`
- **Online Refinement**: `calib/online_refinement.py`
- **Configuration Schema**: `configs/default.yaml`
- **Tests**: `tests/test_*.py`

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Verify configuration in `configs/default.yaml`
3. Run tests to verify system integrity
4. Open GitHub issue with detailed description

---

**Last Updated**: 2026-06-22
**System Version**: v2.0.0 (historical implementation metrics above require remeasurement)
**Note**: Original implementation metrics in this guide may be historical; use `docs/CURRENT_STATUS.md` for current release status.
