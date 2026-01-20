# Stereo Baseline Explained

## What is Baseline?

**Baseline** is the physical distance between the centers of your two camera lenses (measured horizontally).

```
    Left Camera          Right Camera
        |                     |
        |<---- Baseline ----->|
        |                     |
       / \                   / \
```

For your setup: **19.5 inches (1.625 feet)**

## Why It Matters

Baseline is **critical** for calculating depth/distance using stereo vision. Here's the math:

```
depth = (baseline × focal_length) / disparity

Where:
- depth = distance to object (in feet)
- baseline = camera spacing (in feet)
- focal_length = camera focal length (in pixels)
- disparity = horizontal pixel difference between left/right images
```

### Example:
- Baseline: 1.625 ft (19.5 inches)
- Focal length: 1200 pixels (from calibration)
- Disparity: 10 pixels (baseball appears 10px left in right camera vs left camera)

```
depth = (1.625 × 1200) / 10
depth = 195 feet
```

## Impact on Accuracy

### Larger Baseline (wider spacing):
✅ **Better** depth accuracy at long distances (60+ ft)
✅ More robust to pixel noise
❌ Harder to see close objects in both cameras
❌ Requires larger physical setup

### Smaller Baseline (narrower spacing):
✅ Can see close objects in both cameras
✅ Easier to mount and align
❌ **Worse** depth accuracy at long distances
❌ More sensitive to pixel errors

## Depth Error Analysis

**Formula:** `depth_error ≈ (depth² × pixel_error) / (baseline × focal_length)`

For 60 ft pitch tracking with 1-pixel disparity error:

| Baseline | Depth Error | Speed Error |
|----------|-------------|-------------|
| 12" (1.0 ft) | ±4.3 ft | ±6.4 mph |
| 19.5" (1.625 ft) | ±2.7 ft | ±4.0 mph |
| 24" (2.0 ft) | ±2.2 ft | ±3.3 mph |
| 30" (2.5 ft) | ±1.7 ft | ±2.5 mph |

**Recommendation:** For 60 ft tracking, 24-30 inches is ideal balance.

## How to Measure Baseline

1. **Lens center to lens center** (not camera housing edge to edge)
2. Measure horizontally when cameras are level
3. Use tape measure or caliper for accuracy
4. Measure in inches, convert to feet: `baseline_ft = inches / 12`

## Setting Baseline in PitchTracker

### Method 1: Manual Entry (Quick Start)
- Setup Wizard → Step 2 → Baseline spinner
- Enter your measured value
- Used for initial testing

### Method 2: Calibration (Accurate)
- Capture 10+ checkerboard images
- Click "Calibrate"
- **Calibration measures baseline precisely** from images
- More accurate than manual measurement (accounts for lens optical centers)

**Best practice:** Set manual baseline close to measurement, then let calibration refine it.

## Your Current Setup

**Measured Baseline:** 19.5 inches (1.625 ft)

**For 60 ft pitching:**
- Expected depth error: ±2.7 ft (with 1px disparity error)
- Expected speed error: ±4.0 mph
- **Recommendation:** Works, but consider 24-30" for better accuracy

**Trade-off:** Your narrower baseline makes it easier to:
- See checkerboard at close range during calibration
- Keep both cameras aligned
- Mount in tight spaces

## Changing Baseline

**When you change camera spacing**, you must:
1. Update baseline value (Setup Wizard or config file)
2. **Re-run calibration** (focal length depends on baseline)
3. Check camera alignment (wider = harder to align)

**Common spacings:**
- 12-18": Close-range tracking (<30 ft)
- 19-24": General purpose (30-60 ft) ← **Your current setup**
- 24-36": Long-range tracking (60-100+ ft)
- 36"+: Very long range, research setups

## Summary

- **Baseline = camera spacing** (19.5 inches for your setup)
- **Affects depth accuracy**: wider = better at distance
- **Trade-off**: wider is harder to align, narrower works at close range
- **Set manually for quick start**, calibration refines it
- **Re-calibrate** whenever you change camera positions

**Your 19.5" baseline is reasonable for pitch tracking at 40-60 ft.**
If you want better accuracy at 60 ft, consider spacing cameras to 24-30 inches.
