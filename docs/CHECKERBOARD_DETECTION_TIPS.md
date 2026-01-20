# Checkerboard Detection Tips

## Issue: Detection Failing at 18-25 ft Distance

Checkerboard detection becomes challenging at long distances because:
1. **Small corner features** - At 25 ft, individual squares may be only a few pixels
2. **Focus critical** - Even slight blur makes corners undetectable
3. **Resolution limits** - 720p may not have enough pixels to resolve distant corners
4. **Contrast loss** - Atmospheric/lighting effects reduce black-white contrast

## Solutions (In Priority Order)

### 1. **Use a Larger Checkerboard** (Most Effective)
For 18-25 ft calibration, you need a MUCH larger pattern:
- **Standard**: 9x6 pattern on 8.5x11" paper (~1" squares) - Max 8 ft distance
- **Mid-range**: 9x6 pattern on 24x36" poster (~2.5" squares) - Max 15 ft distance
- **Long-range**: 7x5 pattern on 4'x6' board (~6-10" squares) - Works at 25+ ft

**Recommended for 20 ft:**
- Pattern: 7x5 or 9x6 checkerboard
- Square size: 6-8 inches per square
- Material: White foam board + black paint (high contrast)
- Total size: ~4 ft x 6 ft

### 2. **Improve Lighting** (Critical)
- Use bright, diffuse lighting on checkerboard
- Avoid shadows across the pattern
- Position lights at 45° angles to minimize glare
- Ensure high contrast (deep black, bright white)

### 3. **Optimize Camera Settings**
Using the new focus quality overlay:
- **CRITICAL**: Achieve GREEN focus score (200+) on BOTH cameras
- Focus at exactly 20 ft (use tape measure)
- Lock focus rings in place (tape if needed)
- Verify both cameras show similar focus scores (within 50 points)

### 4. **Use Higher Resolution** (If Available)
If your cameras support it:
- 1080p (1920x1080) instead of 720p
- 4K (3840x2160) for extremely long distances
- Update `configs/default.yaml`:
  ```yaml
  camera:
    width: 1920
    height: 1080
  ```

### 5. **Reduce Detection Stride** (Software Tweak)
The calibration wizard checks for checkerboard every N frames. For difficult detection:
- Increase detection attempts (current: every 10 frames)
- This gives more chances to detect during movement/lighting variations

### 6. **Move Checkerboard During Detection**
- Slowly tilt and rotate the checkerboard
- Detection is easier when corners are near-perpendicular to camera
- Try different angles: flat, 15° tilt, 30° tilt
- Move slowly to avoid motion blur

### 7. **Verify Camera View**
Before trying to detect:
- Is checkerboard fully visible in BOTH camera views?
- Are all corners clearly visible (not cut off)?
- Can YOU see the corner points clearly in the preview?
- If you can't see them clearly, neither can OpenCV

## Quick Troubleshooting Checklist

**Before attempting detection at 20 ft:**
- [ ] Checkerboard is 4+ feet wide (6-8" squares)
- [ ] Focus score is GREEN (200+) on BOTH cameras
- [ ] Both cameras have similar focus scores (matched focus)
- [ ] Checkerboard is evenly lit with no shadows
- [ ] All corners visible in both camera views
- [ ] High contrast (deep black squares, bright white squares)
- [ ] No glare/reflections on checkerboard surface

## Expected Detection Requirements

| Distance | Min Square Size | Min Pattern Size | Resolution | Focus Score |
|----------|-----------------|------------------|------------|-------------|
| 3-6 ft   | 1 inch         | 8.5x11"          | 640x480    | 100+        |
| 6-12 ft  | 2-3 inches     | 18x24"           | 1280x720   | 150+        |
| 12-20 ft | 4-6 inches     | 3'x4'            | 1280x720   | 200+        |
| 20-30 ft | 6-10 inches    | 4'x6'            | 1920x1080  | 250+        |

## Alternative: Two-Stage Calibration

If long-distance detection remains difficult:

1. **Stage 1: Close-range calibration (6-8 ft)**
   - Use standard 8.5x11" checkerboard
   - Easier to detect, get initial calibration parameters

2. **Stage 2: Fine-tune with plate plane calibration**
   - Use the plate plane calibration tool (measures actual field distances)
   - Refines calibration for your specific setup

This approach works because:
- Camera intrinsics (focal length, distortion) are distance-independent
- Baseline (camera separation) is constant
- Only need to refine Z-plane calibration at actual pitch distance

## Testing Detection Before Full Calibration

To test if checkerboard is detectable:
1. Start capture with both cameras
2. Open calibration wizard → "Calibration Target" step
3. Watch the indicator - should turn GREEN when detected
4. Watch the focus score overlay - should be GREEN (200+)
5. Try moving/tilting checkerboard slowly
6. If NO detection after 30 seconds → checkerboard too small or focus too poor

## Common Mistakes

❌ **Using tiny checkerboard far away** - Won't work beyond 6-8 ft
❌ **Ignoring focus quality** - Blur kills corner detection
❌ **Mismatched focus** - Left/right cameras focused at different distances
❌ **Poor lighting** - Shadows, low contrast, glare
❌ **Checkerboard cut off** - All corners must be visible in BOTH views
❌ **Motion blur** - Moving checkerboard too quickly during detection

## Need Help?

If still having trouble:
1. Check focus score - is it GREEN (200+) on both cameras?
2. Measure your checkerboard square size
3. Measure actual distance to checkerboard (tape measure)
4. Calculate: `pixels_per_square = focal_length_px * square_size_ft / distance_ft`
   - Need at least 15-20 pixels per square for reliable detection
   - At 20 ft with 1200px focal length and 0.5 ft squares: `1200 * 0.5 / 20 = 30 pixels` ✓
   - At 20 ft with 1200px focal length and 0.08 ft squares (1"): `1200 * 0.08 / 20 = 5 pixels` ✗

The physics is unforgiving - you need enough pixels per square. If the math says <10 pixels, you need a bigger checkerboard or closer distance.
