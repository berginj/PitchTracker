# Camera Timestamp Sync & Calibration Quality Improvements

This document addresses two critical issues for accurate ball tracking:
1. Camera timestamp synchronization
2. Calibration quality metrics

## Problem 1: Timestamp Synchronization

### Current State ⚠️

**How it works now:**
- Each camera captures frames independently in separate threads
- Software timestamps added AFTER frame is read from USB
- Frame pairing happens by matching timestamps within tolerance
- Default tolerance: `config.stereo.pairing_tolerance_ms`

**Code location:**
```python
# app/pipeline/detection/processor.py:201-206
delta = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
tolerance = int(self._config.stereo.pairing_tolerance_ms * 1e6)

if tolerance and delta > tolerance:
    # Frames not synchronized - one gets dropped
```

**Issues:**
- ❌ No hardware sync - relies on thread scheduling
- ❌ USB latency varies between cameras
- ❌ Can't guarantee frames captured at same instant
- ❌ Typical jitter: 5-30ms between cameras
- ❌ Causes 3D triangulation errors for fast-moving objects

### Solutions (Prioritized)

#### Option 1: Hardware Trigger (BEST - but requires hardware)

**What:** External trigger signal to both cameras

**Hardware needed:**
- Trigger generator (Arduino, function generator, or camera with trigger out)
- Wiring to both cameras' trigger input pins
- Cameras with hardware trigger support

**Benefits:**
- ✅ Perfect synchronization (<1ms jitter)
- ✅ Guaranteed simultaneous capture
- ✅ Best for high-speed objects (baseballs)

**Implementation:**
```python
# capture/uvc_backend.py additions needed
def enable_hardware_trigger(self, mode="external"):
    """Enable hardware trigger mode."""
    if self._capture is None:
        raise RuntimeError("Camera not opened.")

    # Set trigger mode (camera-specific)
    # Most industrial cameras support this
    self._capture.set(cv2.CAP_PROP_TRIGGER, 1)
    self._capture.set(cv2.CAP_PROP_TRIGGER_MODE, mode)
```

**Cost:** $50-200 for trigger hardware + camera support

#### Option 2: Software Sync with Frame Numbers (GOOD - no hardware)

**What:** Use frame indices to pair frames instead of timestamps

**How it works:**
1. Start both cameras simultaneously
2. Track frame_index from each camera
3. Pair frames with matching indices (frame N from left with frame N from right)
4. Assumes cameras capture at same rate

**Benefits:**
- ✅ No hardware needed
- ✅ Better than timestamp matching
- ✅ Works if cameras maintain sync

**Limitations:**
- ⚠️ Assumes cameras don't drop frames differently
- ⚠️ Needs monitoring for drift

**Implementation:**
```python
# app/pipeline/detection/processor.py modifications
def _pair_by_frame_index(self, left_frame, right_frame):
    """Pair frames by index instead of timestamp."""
    # Frames must have matching indices
    if left_frame.frame_index != right_frame.frame_index:
        return None

    # Additional check: timestamps should still be close
    delta = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns)
    max_delta = 50_000_000  # 50ms warning threshold

    if delta > max_delta:
        logger.warning(
            f"Frame {left_frame.frame_index}: Large timestamp delta {delta/1e6:.1f}ms"
        )

    return (left_frame, right_frame)
```

#### Option 3: Increase Tolerance + Monitoring (EASY - immediate)

**What:** Accept looser sync but monitor drift

**Implementation:**
```python
# configs/settings.py
class StereoConfig:
    pairing_tolerance_ms: float = 30.0  # Increase from default
    log_sync_warnings: bool = True
    max_acceptable_drift_ms: float = 50.0
```

**Add monitoring:**
```python
# app/pipeline/detection/processor.py
def _check_sync_quality(self):
    """Monitor timestamp synchronization quality."""
    recent_deltas = self._recent_frame_deltas[-100:]  # Last 100 frames

    if recent_deltas:
        mean_delta = np.mean(recent_deltas)
        max_delta = np.max(recent_deltas)

        if max_delta > self._config.stereo.max_acceptable_drift_ms * 1e6:
            logger.warning(
                f"Poor timestamp sync: mean={mean_delta/1e6:.1f}ms, "
                f"max={max_delta/1e6:.1f}ms"
            )

        # Add to stats display
        self._sync_stats = {
            'mean_delta_ms': mean_delta / 1e6,
            'max_delta_ms': max_delta / 1e6,
        }
```

### Recommendation

**Phase 1 (Now):** Implement Option 3 (increase tolerance + monitoring)
- Quick to implement
- Provides visibility into sync quality
- Works with existing hardware

**Phase 2 (Soon):** Implement Option 2 (frame index pairing)
- Better synchronization
- No additional hardware
- Can validate with current recordings

**Phase 3 (Future):** Consider Option 1 (hardware trigger)
- If accuracy requirements demand it
- For professional/commercial use
- After validating other improvements

---

## Problem 2: Calibration Quality Metrics

### Current State ⚠️

**What's captured:**
```python
# calib/quick_calibrate.py:104-114
_, _, _, _, _, R, T, _, _ = cv2.stereoCalibrate(...)
# Returns: (retval, cameraMatrix1, distCoeffs1, cameraMatrix2, distCoeffs2, R, T, E, F)
# Only R and T are kept! Everything else discarded with _
```

**What user sees:**
```
✅ Calibration Complete!

Baseline: 3.456 ft
Focal Length: 850.2 px
Principal Point: (320.5, 240.1)
```

**Issues:**
- ❌ No indication if calibration is good or bad
- ❌ Reprojection error thrown away
- ❌ No per-image quality metrics
- ❌ User doesn't know if they should recalibrate

### Solution: Add Comprehensive Quality Metrics

#### Step 1: Capture Reprojection Error

**Modify calib/quick_calibrate.py:**
```python
# Line 104 - Change from:
_, _, _, _, _, R, T, _, _ = cv2.stereoCalibrate(...)

# To:
rms_error, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
    objpoints,
    left_img,
    right_img,
    mtx_left,
    dist_left,
    mtx_right,
    dist_right,
    img_size,
    flags=cv2.CALIB_FIX_INTRINSIC,
)

# rms_error is the overall reprojection error in pixels
```

#### Step 2: Calculate Per-Image Errors

```python
def compute_per_image_errors(
    objpoints, left_img, right_img,
    mtx_left, dist_left, mtx_right, dist_right,
    R, T
):
    """Calculate reprojection error for each calibration image."""
    errors = []

    for obj_pts, left_pts, right_pts in zip(objpoints, left_img, right_img):
        # Project 3D points back to 2D
        left_projected, _ = cv2.projectPoints(
            obj_pts, np.zeros(3), np.zeros(3),
            mtx_left, dist_left
        )
        right_projected, _ = cv2.projectPoints(
            obj_pts, R, T,
            mtx_right, dist_right
        )

        # Calculate error
        left_error = np.sqrt(np.mean((left_pts - left_projected) ** 2))
        right_error = np.sqrt(np.mean((right_pts - right_projected) ** 2))

        errors.append({
            'left_rms': float(left_error),
            'right_rms': float(right_error),
            'combined_rms': float(np.sqrt(left_error**2 + right_error**2)),
        })

    return errors
```

#### Step 3: Create Quality Rating

```python
def rate_calibration_quality(rms_error: float, num_images: int) -> dict:
    """Rate calibration quality based on metrics."""

    # Thresholds (in pixels)
    EXCELLENT_RMS = 0.5
    GOOD_RMS = 1.0
    ACCEPTABLE_RMS = 2.0
    MIN_IMAGES_GOOD = 15
    MIN_IMAGES_ACCEPTABLE = 10

    # Determine rating
    if rms_error < EXCELLENT_RMS and num_images >= MIN_IMAGES_GOOD:
        rating = "EXCELLENT"
        emoji = "🟢"
        description = "Outstanding calibration! Ready for high-accuracy tracking."
    elif rms_error < GOOD_RMS and num_images >= MIN_IMAGES_GOOD:
        rating = "GOOD"
        emoji = "🟢"
        description = "Good calibration. Suitable for most tracking needs."
    elif rms_error < ACCEPTABLE_RMS and num_images >= MIN_IMAGES_ACCEPTABLE:
        rating = "ACCEPTABLE"
        emoji = "🟡"
        description = "Acceptable calibration. Consider recalibrating for better accuracy."
    else:
        rating = "POOR"
        emoji = "🔴"
        description = "Poor calibration. Please recalibrate with more images and better coverage."

    return {
        'rating': rating,
        'emoji': emoji,
        'description': description,
        'rms_error_px': rms_error,
        'num_images': num_images,
        'recommendations': _get_calibration_recommendations(rms_error, num_images)
    }

def _get_calibration_recommendations(rms_error: float, num_images: int) -> list:
    """Get specific recommendations for improving calibration."""
    recommendations = []

    if rms_error > 1.0:
        recommendations.append("• Hold checkerboard steadier during capture")
        recommendations.append("• Ensure checkerboard is perfectly flat")
        recommendations.append("• Check camera focus is sharp")

    if num_images < 15:
        recommendations.append(f"• Capture {15 - num_images} more images for better calibration")

    if rms_error > 2.0:
        recommendations.append("• Try recalibrating from scratch")
        recommendations.append("• Verify checkerboard dimensions are correct")

    return recommendations
```

#### Step 4: Enhanced UI Display

**Update ui/setup/steps/calibration_step.py:**
```python
def _on_calibration_complete(self, result: dict) -> None:
    """Handle successful calibration with quality metrics."""
    quality = result['quality']

    results_text = (
        f"{quality['emoji']} Calibration {quality['rating']}!\n\n"
        f"Baseline: {result['baseline_ft']:.3f} ft\n"
        f"Focal Length: {result['focal_length_px']:.1f} px\n"
        f"Principal Point: ({result['cx']:.1f}, {result['cy']:.1f})\n\n"
        f"Quality Metrics:\n"
        f"  Reprojection Error: {quality['rms_error_px']:.3f} px\n"
        f"  Images Used: {quality['num_images']}\n\n"
        f"{quality['description']}\n"
    )

    if quality['recommendations']:
        results_text += "\nRecommendations:\n"
        results_text += "\n".join(quality['recommendations'])

    # Color code based on quality
    if quality['rating'] in ['EXCELLENT', 'GOOD']:
        bg_color = "#c8e6c9"  # Green
        text_color = "#2e7d32"
    elif quality['rating'] == 'ACCEPTABLE':
        bg_color = "#fff9c4"  # Yellow
        text_color = "#f57f17"
    else:  # POOR
        bg_color = "#ffcdd2"  # Red
        text_color = "#c62828"

    self._results_text.setText(results_text)
    self._results_text.setStyleSheet(
        f"background-color: {bg_color}; color: {text_color}; "
        f"padding: 12px; border-radius: 4px;"
    )
    self._results_text.show()

    # Add warning dialog for poor calibration
    if quality['rating'] == 'POOR':
        QtWidgets.QMessageBox.warning(
            self,
            "Poor Calibration Quality",
            f"Calibration quality is poor (RMS error: {quality['rms_error_px']:.2f} px).\n\n"
            f"We strongly recommend recalibrating:\n"
            + "\n".join(quality['recommendations']),
            QtWidgets.QMessageBox.Ok
        )
```

### Quality Benchmarks

| Rating | RMS Error | Images | Use Case |
|--------|-----------|--------|----------|
| 🟢 EXCELLENT | < 0.5 px | 15+ | Professional tracking, research |
| 🟢 GOOD | < 1.0 px | 15+ | Most applications, coaching |
| 🟡 ACCEPTABLE | < 2.0 px | 10+ | Casual use, practice |
| 🔴 POOR | > 2.0 px | Any | Recalibration needed |

### Validation

After implementing, validate with your 100 recorded pitches:
1. Run calibration with current setup
2. Note RMS error and rating
3. Record 100 pitches
4. Measure velocity/location accuracy
5. Correlate accuracy with calibration quality

---

## Implementation Priority

### Immediate (Today):
- [x] Document current issues
- [ ] Add timestamp sync monitoring
- [ ] Capture reprojection error from stereoCalibrate

### This Week:
- [ ] Implement calibration quality rating
- [ ] Add enhanced UI feedback
- [ ] Test with real calibration session

### Next Sprint:
- [ ] Implement frame-index pairing
- [ ] Add calibration validation tests
- [ ] Consider hardware trigger evaluation

---

## Testing Plan

### Test Calibration Quality System:
1. Calibrate with 10 images (minimum)
   - Should get ACCEPTABLE or POOR rating
2. Calibrate with 20 images (good coverage)
   - Should get GOOD or EXCELLENT rating
3. Calibrate with shaky images
   - Should get POOR rating with specific recommendations
4. Calibrate with perfect technique
   - Should get EXCELLENT rating

### Test Timestamp Monitoring:
1. Run 100 pitch session
2. Review sync stats logs
3. Check for drift warnings
4. Correlate sync quality with detection accuracy

---

## Expected Impact

**Calibration Quality:**
- Users know if calibration is good before using system
- Clear guidance on how to improve
- Reduces support requests from poor calibration
- Improves overall tracking accuracy

**Timestamp Sync:**
- Better visibility into sync issues
- Can diagnose frame pairing problems
- Foundation for frame-index pairing
- Path to hardware trigger if needed

---

## Related Documentation

- `CAMERA_VALIDATION_GUIDE.md` - Testing camera reliability
- `PITCH_RECORDING_GUIDE.md` - Using recordings for training
- Setup wizard documentation (inline)
