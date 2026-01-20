# Baseline Workflow - Why the Value Changes

## Quick Answer

**Q: Why does the baseline value change when I reopen calibration?**

**A: Calibration refines your manual measurement to a precise value.**

- **Manual entry (✏️ Manual):** Your tape measure reading (e.g., 1.625 ft / 19.5 inches)
- **After calibration (📐 Calibrated):** Precise calculation from images (e.g., 1.638 ft / 19.656 inches)

**This is correct behavior!** The calibrated value is more accurate than manual measurement.

---

## The Complete Workflow

### Step 1: Initial Setup (Manual Baseline)

**You measure cameras with tape measure:**
- Distance: 19.5 inches
- Convert: 19.5 ÷ 12 = 1.625 feet
- Enter in UI: Baseline spinner shows `1.625 ft`
- Status shows: **`(19.5 in) ✏️ Manual`** (orange)

**What happens:**
- Value immediately saves to `configs/default.yaml`
- System uses this value for depth calculations **until you calibrate**
- This is a "good enough" starting point

### Step 2: Run Calibration

**You capture 10+ checkerboard images and click "Calibrate"**

**What calibration measures:**
1. **Intrinsic parameters:**
   - Focal length (pixels)
   - Principal point (optical center)
   - Lens distortion

2. **Extrinsic parameters:**
   - Rotation between cameras
   - Translation (baseline) between cameras
   - **Baseline calculated from image triangulation**

**Result:**
- Calibration calculates baseline: `1.638 ft` (19.656 inches)
- This accounts for:
  - Exact lens optical centers (not housing edges)
  - Camera mounting angles
  - Any slight toe-in or convergence
- **Calibration writes this to `configs/default.yaml`**
- **Overwrites your 1.625 ft manual value**

**UI updates:**
- Baseline spinner changes from `1.625` → `1.638`
- Status changes: **`(19.7 in) 📐 Calibrated`** (blue)
- Tooltip: "This value was calculated by stereo calibration"

### Step 3: Reopen Calibration

**Next time you open the calibration step:**
- UI reads `configs/default.yaml`
- Loads value: `1.638 ft`
- Shows: **`(19.7 in) 📐 Calibrated`** (blue)

**This is why it's different from your original 1.625 ft!**

---

## Why Calibration Changes the Value

### Manual Measurement Limitations

**When you measure with tape:**
- ✅ You measure housing edge to housing edge
- ❌ Lenses are recessed inside housing
- ❌ Tape might be slightly angled
- ❌ You might round to nearest 0.5 inch
- **Result:** ±0.1-0.3 inch error (±0.008-0.025 ft)

**Your measurement:** 19.5 inches (1.625 ft)

### Calibration Precision

**Calibration uses triangulation math:**
```
For each checkerboard corner:
- Left camera sees it at pixel (x_L, y_L)
- Right camera sees it at pixel (x_R, y_R)
- Known: Checkerboard square size (30mm)
- Unknown: Baseline, focal length, rotation

Calibration solves for unknowns using all corners from all images.
Result: Baseline accurate to ~0.01 inch (0.0008 ft)
```

**Calibrated baseline:** 19.656 inches (1.638 ft)

**Difference:** 0.156 inches (4mm) - **This is normal!**

### Which Value is Used?

| Time Period | Baseline Used | Source |
|-------------|---------------|--------|
| Before calibration | 1.625 ft (manual) | Your measurement |
| During calibration | 1.625 ft → refines → 1.638 ft | Calculation |
| After calibration | 1.638 ft (calibrated) | Config file |
| Next session | 1.638 ft (calibrated) | Config file |

**Once you calibrate, the system always uses the calibrated value.**

---

## Visual Indicators

### ✏️ Manual (Orange)
```
Baseline: [1.625] ft  (19.5 in) ✏️ Manual
          ↑ You entered this
```
- **Meaning:** Value was manually entered by user
- **When:** Before calibration, or if you manually change it
- **Accuracy:** ±0.1-0.3 inches (±0.008-0.025 ft)
- **Tooltip:** "This is a manually entered value. Run calibration to get a precise measurement."

### 📐 Calibrated (Blue)
```
Baseline: [1.638] ft  (19.7 in) 📐 Calibrated
          ↑ Calibration measured this
```
- **Meaning:** Value was calculated by stereo calibration
- **When:** After running calibration
- **Accuracy:** ±0.01 inches (±0.0008 ft)
- **Tooltip:** "This value was calculated by stereo calibration (more accurate than manual measurement)"

---

## Common Scenarios

### Scenario 1: First Time Setup

```
1. Measure cameras: 19.5 inches
2. Enter: 1.625 ft → Shows "✏️ Manual" (orange)
3. Run calibration
4. Result: 1.638 ft → Shows "📐 Calibrated" (blue)
5. Close wizard, reopen → Still shows 1.638 ft "📐 Calibrated"
```

**✅ This is correct!** Use the calibrated value.

### Scenario 2: Recalibration After Moving Cameras

```
1. Open calibration: Shows 1.638 ft "📐 Calibrated" (old value)
2. You moved cameras → measure new distance: 24 inches
3. Enter: 2.000 ft → Shows "✏️ Manual" (orange)
4. Run calibration with new spacing
5. Result: 2.015 ft → Shows "📐 Calibrated" (blue)
```

**✅ Always recalibrate after moving cameras!**

### Scenario 3: Quick Testing Without Calibration

```
1. Want to test different baseline spacings
2. Change spinner: 1.625 → 2.000 ft
3. Shows "✏️ Manual" (orange)
4. Don't run calibration
5. Close wizard, reopen → Shows 2.000 ft "✏️ Manual" (orange)
```

**⚠️ Manual value is saved, but less accurate. Calibrate when done testing.**

---

## When to Manually Change Baseline

### You SHOULD manually change it when:

1. **Before first calibration**
   - Enter your measured value
   - Helps calibration converge faster

2. **Testing different camera positions**
   - Quickly try 2 ft vs 2.5 ft
   - See effect on depth accuracy
   - **But recalibrate before using for real!**

3. **Cameras were moved**
   - Measure new spacing
   - Enter new value
   - Run calibration to refine it

### You should NOT manually change it when:

1. **After successful calibration**
   - Don't "correct" the calibrated value
   - Calibration is more accurate than your tape measure
   - Changing it makes calibration worse!

2. **"Tuning" to match expectations**
   - If calibrated baseline seems wrong, the issue is:
     - Camera alignment (run alignment checker)
     - Bad calibration images
     - Wrong checkerboard size setting
   - Don't manually "fix" the calibrated baseline

---

## FAQ

### Q: My manual measurement was 19.5", calibration says 19.7". Which is right?

**A: Calibration (19.7") is more accurate.**

Your tape measure:
- Measures housing edges, not lens centers
- Subject to parallax error
- Rounded to nearest 0.5"

Calibration:
- Triangulates from 100+ image points
- Accounts for lens optical centers
- Accurate to 0.01"

**Use the calibrated value.**

### Q: Should I update the manual value to match calibration?

**A: No need.** The system uses whatever is in the config file:
- Before calibration: Uses manual value
- After calibration: Uses calibrated value (overwrites manual)
- You can leave the manual value as-is

### Q: I changed the baseline but nothing happened?

**A: Changes take effect in different places:**

1. **Config file:** Updated immediately (used for depth calculations)
2. **Stereo matcher:** Needs pipeline restart (stop/start capture)
3. **Calibration results:** Only used AFTER you click "Calibrate"

**To see changes in depth calculations:**
- Change baseline → Close wizard → Start capture → New value is used

### Q: My baseline keeps changing by small amounts (1.638 → 1.642 → 1.635)?

**A: This indicates:**
- Inconsistent calibration quality
- Camera alignment changing between sessions
- Not enough checkerboard images
- Checkerboard warping or not held flat

**Solutions:**
1. Run alignment checker before calibration
2. Capture 15-20 images (not just 10)
3. Hold checkerboard very flat
4. Vary positions/angles more
5. Check cameras are securely mounted (not shifting)

**Good calibration:** Baseline changes by <0.01 ft between runs

---

## Summary

**The baseline value changes because:**
1. You enter manual measurement (✏️ Manual)
2. Calibration refines it with precision (📐 Calibrated)
3. Config file is updated with calibrated value
4. Next time you open UI, it loads the calibrated value

**This is correct behavior!**

**Color coding helps you know:**
- 🟠 Orange = Manual (less accurate)
- 🔵 Blue = Calibrated (more accurate)

**Best practice:**
1. Measure and enter baseline manually (starting point)
2. Run calibration to refine it (precise value)
3. Use the calibrated value (don't change it back)
4. Only update manually if you move cameras (then recalibrate)
