# Calibration Troubleshooting Guide

## High RMS Error (>5 pixels) Despite Good Focus

If you're getting high reprojection error (>5px) but focus quality is good (200+), the issue is likely **camera alignment** or **setup geometry**, not image quality.

### Issue: 43.6px RMS Error

This is extremely high (20x worse than acceptable). Here are the causes and fixes:

## 1. Camera Alignment Issues (Most Common)

### Symptoms:
- High RMS error despite sharp images
- Corners detected correctly in individual cameras
- Stereo calibration fails or gives poor results

### Causes:
**Cameras Not Parallel:**
- Left and right cameras pointing at different angles
- Vertical misalignment (one higher than the other)
- Rotation/tilt differences between cameras

**Convergence (Toe-in):**
- Cameras angled inward toward each other
- Creates non-linear disparity
- Violates parallel stereo assumption

### Fixes:

**Step 1: Physical Alignment Check**
```
1. Place cameras on level surface
2. Use bubble level to verify both cameras are level
3. Point both cameras at distant object (20+ ft away)
4. Verify BOTH cameras see the object centered in frame
5. If one camera shows object left/right of center → cameras not parallel
```

**Step 2: Parallel Verification**
```
1. Measure distance from camera lenses to wall at same height
2. Both distances should be identical (within 1-2mm)
3. Draw vertical line on wall
4. Adjust cameras so vertical line appears centered in BOTH views
5. Lock camera positions (tape/secure mount)
```

**Step 3: Vertical Alignment**
```
1. Ensure both camera lenses at EXACTLY same height
2. Use ruler to measure from ground to lens center
3. Difference should be <2mm
4. Use shims if needed to level cameras
```

## 2. Checkerboard Detection Issues

### Symptom: High per-image variance in RMS error

### Causes:
**Checkerboard Movement During Capture:**
- Checkerboard not held steady
- Motion blur from moving too quickly
- Wind causing flutter (outdoor capture)

**Warped/Bent Checkerboard:**
- Paper checkerboards curl/warp over time
- Creates 3D surface instead of flat plane
- Violates flat plane assumption in calibration

**Partial Occlusion:**
- Not all corners visible in both cameras
- Corners cut off at image edges
- Shadows obscuring corners

### Fixes:
```
1. Use rigid checkerboard (foam board, not paper)
2. Hold checkerboard completely still during capture (2-3 seconds)
3. Ensure ALL corners visible in BOTH camera views before capturing
4. Use bright, even lighting (no shadows across pattern)
5. Verify flatness - place on flat surface, look for gaps
```

## 3. Incorrect Checkerboard Dimensions

### Symptom: Consistent high error across all images

### Cause:
- Square size in config doesn't match actual physical size
- Pattern size wrong (counted outer corners instead of inner)

### Fix:
```
1. MEASURE actual square size with ruler (millimeters)
2. Verify pattern size by counting INNER corners:
   - 9x6 checkerboard = 8x5 inner corners
   - 7x5 checkerboard = 6x4 inner corners
3. Update config with measured values
```

## 4. Synchronization Issues

### Symptom: High error, especially with moving checkerboard

### Cause:
- Frames from left and right cameras not captured at same time
- Checkerboard moved between left and right capture
- Frame timing mismatch

### Fix:
```
1. Use frame index pairing instead of timestamp pairing
2. In configs/default.yaml:
   stereo:
     use_frame_index_pairing: true
     frame_index_tolerance: 1

3. Hold checkerboard COMPLETELY STILL during capture
4. Wait 2-3 seconds before moving to next position
```

## 5. Lens Distortion Issues

### Symptom: Error increases toward image edges

### Cause:
- High lens distortion not being corrected properly
- Wide-angle lenses have more distortion
- Cheap lenses with poor optics

### Fix:
```
1. Capture calibration images with checkerboard at many positions:
   - Center
   - Top-left, top-right corners
   - Bottom-left, bottom-right corners
   - Near edges (but all corners still visible)

2. Need 15+ diverse positions for good distortion calibration
3. Consider using higher quality lenses if distortion severe
```

## 6. Baseline Too Large

### Symptom: High error, especially at close distances

### Cause:
- Cameras too far apart relative to object distance
- Creates large disparity differences with small position changes
- Geometric sensitivity increases

### Fix:
```
1. Check baseline (camera separation):
   - For 6 ft calibration: max 1-2 ft separation
   - For 20 ft calibration: 2-4 ft separation acceptable

2. If baseline too large for close calibration:
   - Move cameras closer together temporarily
   - OR calibrate at farther distance (see distance calculator)
```

## Diagnostic Workflow

### Step 1: Verify Camera Alignment
```bash
1. Start capture with both cameras
2. Point both at distant vertical line (door frame, etc.)
3. Check if line appears centered in BOTH views
4. If not centered → cameras not parallel → FIX FIRST
```

### Step 2: Test Corner Detection Quality
```bash
1. Capture single checkerboard image pair
2. Check quick_calibrate output:
   - How many corners detected in left? (should be 8x5 = 40 for 9x6 board)
   - How many corners detected in right? (should match left)
   - Any "detection failed" messages?
```

### Step 3: Check Per-Image Errors
```bash
After calibration, look at per_image_errors in output:
- If all images have high error → systematic issue (alignment, dimensions)
- If only some images have high error → those specific captures were bad
- If error increases toward end → checkerboard warping over time
```

### Step 4: Verify Physical Measurements
```bash
1. Measure square size with ruler: _____ mm
2. Count inner corners: _____ x _____
3. Measure camera separation: _____ mm
4. Measure calibration distance: _____ mm
```

## Expected RMS Errors

| Calibration Quality | RMS Error | Tracking Accuracy |
|---------------------|-----------|-------------------|
| Excellent           | <0.5 px   | Sub-inch at 50 ft |
| Good                | <1.0 px   | ~1-2 inch at 50 ft|
| Acceptable          | <2.0 px   | ~3-4 inch at 50 ft|
| Poor                | >2.0 px   | Unreliable        |
| **Your 43.6px**     | **CRITICAL** | **Not usable** |

## Quick Fixes to Try First

**Before recalibrating, try these:**

1. **Check camera alignment** (5 minutes):
   ```
   - Point both cameras at distant object
   - Verify object centered in both views
   - Adjust if needed
   ```

2. **Verify checkerboard is flat** (2 minutes):
   ```
   - Place on flat table
   - Look for warping/curling
   - Replace if damaged
   ```

3. **Measure square size again** (2 minutes):
   ```
   - Use ruler to measure several squares
   - Calculate average
   - Update config if different
   ```

4. **Reduce camera separation** (if possible):
   ```
   - Move cameras closer together
   - Try 1 ft separation for 6 ft calibration
   ```

## When to Recalibrate from Scratch

Recalibrate if:
- RMS error > 5 px
- Cameras were moved/bumped after last calibration
- Changed lenses or camera settings
- Checkerboard damaged/replaced
- Cannot achieve <2px error after trying all fixes above

## Getting Help

If still having issues after trying above:

1. Run the diagnostic:
   ```bash
   python scripts/checkerboard_distance_calculator.py
   ```

2. Check these values:
   - Camera separation (baseline): _____ ft
   - Calibration distance: _____ ft
   - Checkerboard square size: _____ mm
   - Number of matched pairs: _____
   - RMS error: _____ px
   - Focus scores: L=_____ R=_____

3. Post results with description of camera mounting setup
