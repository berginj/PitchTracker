# PitchTracker - Calibration Tips & Best Practices

**Last Updated:** 2026-01-27
**Version:** 1.2.1

---

## Table of Contents

- [Why Calibration Matters](#why-calibration-matters)
- [Generate Calibration Board](#generate-calibration-board) ⭐ START HERE
- [Camera Placement](#camera-placement)
- [Equipment Needed](#equipment-needed)
- [Intrinsic Calibration](#intrinsic-calibration)
- [Extrinsic Calibration](#extrinsic-calibration)
- [Strike Zone Setup](#strike-zone-setup)
- [Calibration Profiles](#calibration-profiles)
- [Troubleshooting](#troubleshooting)
- [Advanced Tips](#advanced-tips)

---

## Why Calibration Matters

Calibration is the process of teaching the application about your camera setup. Without proper calibration, you'll get:

❌ **Without Calibration:**
- No 3D tracking (only 2D camera views)
- Inaccurate velocity measurements
- Wrong strike zone positioning
- Unusable trajectory data

✅ **With Calibration:**
- Accurate 3D ball position
- Correct velocity (±1 mph)
- Precise strike zone mapping
- Reliable pitch metrics

**Time Investment:** 30-60 minutes for initial setup, 10-15 minutes for recalibration

---

## Generate Calibration Board

### ⭐ Step 1: Generate the Board

Before starting calibration, generate and print a ChArUco board:

```bash
# From project directory
python generate_charuco.py
```

**Output:** `charuco_board.png`

**Options:**
```bash
# Custom size board (e.g., 7×5 with 25mm squares)
python generate_charuco.py --cols 7 --rows 5 --size 25

# A4 paper instead of US Letter
python generate_charuco.py --paper a4

# Custom output filename
python generate_charuco.py --output my_board.png
```

### 📄 Step 2: Print the Board

**CRITICAL PRINTING INSTRUCTIONS:**

1. **Open File:** Open `charuco_board.png` in image viewer or browser

2. **Print Settings:**
   - ✅ **Scale: 100%** (CRITICAL - NO "Fit to Page" or "Shrink to Fit")
   - ✅ **Quality: High/Best** quality
   - ✅ **Paper: Thick paper or cardstock** (for rigidity)
   - ✅ **Finish: Matte** (reduces glare - important!)
   - ✅ **Color: Black & White** is fine

3. **Mounting:**
   - Mount on **rigid surface** (foam board, cardboard, 1/4" plywood)
   - Keep it **perfectly FLAT** (warping ruins calibration)
   - Optional: **Laminate** for durability and easy cleaning

4. **Verification:**
   - Measure actual square size with a **ruler**
   - Should be **30mm ± 0.5mm**
   - If different, note actual size for Advanced Settings

### ❓ Why ChArUco Board?

**ChArUco** (Checkerboard + ArUco markers) is **superior to plain checkerboard** because:

✅ **Partial Occlusion OK** - Don't need entire board visible
✅ **Auto-Detection** - Automatically detects board size and orientation
✅ **Robust to Lighting** - Works in varied lighting conditions
✅ **Flexible Distance** - Can be closer or further from cameras
✅ **Better Accuracy** - More corners = better calibration

**Alternative:** Plain checkerboard works but requires entire board visible at all times.

### 🤖 Smart Camera Features (NEW)

**1. Auto-Swap on Startup:**
- **What it does:** Automatically detects if cameras are swapped based on historical data
- **How it works:** Remembers which camera serial numbers were previously left/right
- **When it activates:** Every time you enter the calibration step
- **Result:** Cameras are automatically swapped if they were connected in wrong positions
- **Storage:** Camera history saved in `configs/camera_history.json`

**2. Manual Auto-Swap:**
- **Problem:** Not sure which camera is left/right?
- **Solution:** Click "🔍 Auto-Swap" button in Advanced Settings
- Hold board in view of both cameras
- System analyzes marker positions and automatically swaps if needed
- **How it works:** Left camera should see board toward RIGHT, right camera should see board toward LEFT
- **Shows confidence score:** "85% confident cameras are swapped"

**3. Visual Marker Position Overlay:**
- **What it shows:** Colored bar at bottom of camera previews
- **Position indicator:** Shows where markers are detected horizontally
  - **GREEN (RIGHT):** Markers on right side (good for left camera)
  - **ORANGE (LEFT):** Markers on left side (good for right camera)
  - **YELLOW (CENTER):** Markers centered (ambiguous)
- **Marker count:** Displays number of detected markers
- **When visible:** Always enabled during calibration preview

**4. Confidence Score Display:**
- **What it shows:** Percentage confidence in swap decision
- **High confidence (>60%):** Clear indication of correct/swapped orientation
- **Low confidence (<40%):** Board too centered, move to one side
- **Shown in:** Auto-swap dialog results

**5. Multi-Pattern Detection:**
- **What it shows:** Current detected pattern and dictionary
- **Display location:** Next to "Enable Auto-Detection" checkbox
- **Information shown:**
  - Pattern size (e.g., "5×6")
  - Dictionary type (e.g., "6X6 250")
  - Detection status: Scanning / Detected / Locked
- **Color coding:**
  - GREEN: Pattern detected and locked
  - ORANGE: Scanning for patterns
  - GRAY: No pattern detected

**Auto-Detection Toggle:**
- **Purpose:** Control whether system auto-detects board size
- **Enabled** (default): Automatically detects ChArUco pattern size and dictionary
- **Disabled:** Uses your manual pattern settings only
- **When to disable:**
  - Force specific board size
  - Multiple boards in view causing confusion
  - Auto-detection causing issues

### 🖨️ Printing Troubleshooting

**Problem:** Board prints too small or large

**Solution 1:** Check printer settings
- Disable "Fit to Page"
- Disable "Shrink to Fit"
- Set to "Actual Size" or "100%"

**Solution 2:** Measure and adjust
- Print board
- Measure actual square size
- In calibration UI, expand "⚙️ Advanced Settings"
- Enter actual measured size in "Square size (mm)" field

**Problem:** Board is warped or curved

**Solution:** Mount on rigid surface BEFORE calibration
- Foam board (from craft store)
- 1/4" plywood
- Thick cardboard (multiple layers glued together)
- Acrylic sheet (if available)

---

## Camera Placement

### Optimal Setup

```
                      MOUND
                        |
                        | 50-60 ft
                        |
                        v
    LEFT CAMERA    STRIKE ZONE    RIGHT CAMERA
         o         [  PLATE  ]         o
          \            |              /
           \           |             /
            \----------|------------/
                6-8 feet apart
```

### Key Requirements

**Camera Separation:**
- **6-8 feet apart** (2-2.5 meters)
- Wider = better depth perception
- Too wide = reduced overlap
- Narrower = less accuracy

**Camera Angle:**
- **Converge on strike zone** (angled inward ~15-30°)
- Both cameras should see full strike zone
- Avoid parallel placement (reduces accuracy)

**Camera Height:**
- **Same height** as middle of strike zone
- Typically 3-4 feet off ground
- Use level to ensure cameras are even
- Adjust for batter height

**Distance from Mound:**
- **50-60 feet** from pitcher's release point
- Behind home plate (catcher's perspective)
- Closer = larger ball in frame = better detection
- Too close = reduced field of view

### Physical Mounting

✅ **Good Mounting:**
- Sturdy tripods with weight
- Sandbags for outdoor stability
- Vibration isolation
- Fixed position (no wobbling)

❌ **Poor Mounting:**
- Lightweight tripods
- On uneven ground
- Near walkways (vibrations)
- Temporary/adjustable

**Pro Tip:** Once positioned, mark tripod leg positions with tape for consistent setup.

---

## Equipment Needed

### Required

1. **Checkerboard Calibration Pattern**
   - Provided in app: Tools → Print Calibration Pattern
   - Size: 8×6 or 9×7 internal corners
   - Print on rigid surface (foam board, clipboard)
   - **Must be perfectly flat** (no wrinkles or bends)

2. **Measuring Tape**
   - For camera separation distance
   - For camera-to-mound distance
   - For strike zone measurements

3. **Level Tool**
   - Ensure cameras are horizontally level
   - Bubble level or smartphone app

### Optional but Helpful

- **Helper person** (to hold calibration board)
- **Good lighting** (even, no harsh shadows)
- **Notebook** (to record measurements)
- **Marker/tape** (to mark positions)

---

## Intrinsic Calibration

**What it measures:** Internal camera parameters (focal length, lens distortion)

**When to do:** First time setup, after camera firmware update, if using different lens

**Duration:** 15-20 minutes per camera

### Step-by-Step Process

#### 1. Launch Calibration Wizard

```
Tools → Calibration Wizard → Intrinsic Calibration
```

- Follow on-screen instructions
- Calibrate left camera first, then right

#### 2. Prepare Checkerboard

- Print pattern from app (Tools → Print Calibration Pattern)
- Mount on rigid, flat surface
- Ensure good lighting on pattern
- All corners must be visible

#### 3. Capture Images (20-30 required)

**Variety is Key:** Capture pattern at different:
- **Distances:** Close, medium, far (fill 30-70% of frame)
- **Angles:** Center, tilted left/right, rotated
- **Positions:** All four corners of frame, center
- **Orientations:** Horizontal, vertical, diagonal

**Tips for Good Captures:**
```
✓ Hold pattern steady (no motion blur)
✓ All corners visible in frame
✓ Pattern in focus
✓ Even lighting (no glare)
✓ Click "Capture" when green outline appears
```

**Poor Quality Images:**
```
✗ Motion blur (hand shaking)
✗ Pattern too close/far
✗ Corners cut off
✗ Out of focus
✗ Same angle every time (need variety!)
```

#### 4. Image Variety Checklist

Capture at least:
- [x] 3-4 images: Center of frame
- [x] 2-3 images: Each corner (8-12 total)
- [x] 3-4 images: Close distance (pattern fills frame)
- [x] 3-4 images: Far distance (pattern smaller)
- [x] 3-4 images: Tilted/rotated angles
- [x] 3-4 images: Different orientations

**Total: 20-30 good quality images**

#### 5. Run Calibration

- Click "Calibrate" button
- Processing takes 30-60 seconds
- Check RMS (reprojection error):
  - **<0.5 pixels:** Excellent
  - **0.5-1.0 pixels:** Good
  - **1.0-2.0 pixels:** Acceptable
  - **>2.0 pixels:** Poor (redo calibration)

#### 6. Repeat for Second Camera

- Follow same process for other camera
- Use same checkerboard pattern
- Aim for similar RMS error

---

## Extrinsic Calibration

**What it measures:** Relative position/orientation of cameras in 3D space

**When to do:** After intrinsic calibration, after moving cameras

**Duration:** 10-15 minutes

### Prerequisites

- Both cameras have intrinsic calibration
- Cameras in final physical positions
- Camera separation distance measured accurately

### Step-by-Step Process

#### 1. Measure Camera Separation

```
Use measuring tape:
1. Measure center-to-center distance between camera lenses
2. Record in METERS (e.g., 2.13m = 7 feet)
3. Be accurate (±1cm affects 3D accuracy)
```

#### 2. Launch Extrinsic Calibration

```
Tools → Calibration Wizard → Extrinsic Calibration
```

- Enter measured camera separation distance
- Ensure both cameras see the strike zone

#### 3. Position Checkerboard

**Critical:** Both cameras must see pattern simultaneously

```
Ideal position:
- In strike zone area
- Both cameras see full pattern
- Pattern perpendicular to cameras
- Good lighting
```

#### 4. Capture Stereo Images (10-15 pairs)

**Goal:** Various positions in 3D space

Capture pattern at:
- **Left side** of strike zone
- **Right side** of strike zone
- **Top** of strike zone
- **Bottom** of strike zone
- **Center** of strike zone
- **Near** (closer to cameras)
- **Far** (toward mound)

**Tips:**
```
✓ Both cameras must see pattern clearly
✓ Pattern fully visible in both views
✓ Move pattern smoothly between captures
✓ Cover entire strike zone volume
```

#### 5. Run Extrinsic Calibration

- Click "Calibrate" button
- Processing takes 15-30 seconds
- Check results:
  - **Baseline:** Should match measured distance (±1cm)
  - **Rotation:** Verify cameras angled correctly
  - **Reprojection:** <1.0 pixels ideal

#### 6. Verify Calibration

```
Tools → Test 3D Reconstruction:
- Hold ball in strike zone
- Check 3D position displayed
- Move ball around
- Verify tracking follows ball smoothly
```

---

## Strike Zone Setup

**What it does:** Defines coordinate system and strike zone boundaries

**When to do:** After camera calibration, when changing batter

**Duration:** 5-10 minutes

### Step-by-Step Process

#### 1. Measure Physical Setup

```
Record:
- Home plate position (X, Y, Z in camera coordinates)
- Distance from cameras to plate
- Batter height (in inches)
```

#### 2. Define Strike Zone

```
Settings → Strike Zone:

1. **Batter Height:** Enter in inches
   - Adult male: ~72" (6 feet)
   - Adjust for actual batter

2. **Strike Zone Ratios:**
   - Top: 0.56 × batter height (knees to mid-torso)
   - Bottom: 0.28 × batter height (knees)
   - Standard baseball rules

3. **Plate Dimensions:**
   - Width: 17 inches (0.43m)
   - Length: 17 inches (0.43m)
   - These are fixed (regulation plate)
```

#### 3. Set Home Plate Position

**Using Calibration Tool:**
```
Tools → Set Plate Position:
1. Place marker on home plate
2. Both cameras should see marker
3. Click "Detect Plate"
4. Or manually enter coordinates
```

**Manual Coordinates:**
```
If detector doesn't work:
1. Tools → 3D Coordinate Display
2. Hold ball on front of plate
3. Note X, Y, Z coordinates
4. Settings → Strike Zone → Plate Position
5. Enter coordinates
```

#### 4. Verify Strike Zone

```
Tools → Show Strike Zone Overlay:
- Strike zone box should appear
- Verify size looks correct
- Verify position over plate
- Adjust if needed
```

---

## Calibration Profiles

### Saving Profiles

**Why:** Save calibrations for different setups

```
After calibration complete:
1. Tools → Calibration → Save Profile
2. Name profile (e.g., "Backyard_Setup_Jan_2026")
3. Profile includes:
   - Intrinsic calibration
   - Extrinsic calibration
   - Strike zone settings
   - Camera settings
```

### Loading Profiles

```
1. Tools → Calibration → Load Profile
2. Select saved profile
3. Verify cameras in same physical positions
```

### Multiple Profiles Use Cases

- **Indoor vs Outdoor:** Different lighting, backgrounds
- **Different Locations:** Field A, Field B, home
- **Camera Changes:** Swapping camera hardware
- **Batter Heights:** Youth vs Adult leagues

---

## Troubleshooting

### "Calibration Failed" Error

**Cause:** Not enough good images or pattern not detected

**Solution:**
1. Ensure checkerboard is perfectly flat
2. Check lighting (avoid glare)
3. Capture more images (aim for 30)
4. Vary positions/angles more
5. Hold pattern steady (no blur)

### High RMS Error (>2.0)

**Cause:** Poor image quality or camera issues

**Solution:**
1. Check focus (pattern should be sharp)
2. Delete blurry images, recapture
3. Try different distances
4. Check if lens is clean
5. Restart calibration fresh

### 3D Tracking Looks Wrong

**Cause:** Usually extrinsic calibration issue

**Solution:**
1. Verify camera separation distance is accurate
2. Ensure cameras haven't moved
3. Redo extrinsic calibration
4. Check camera alignment (both level)

### Can't See Pattern in Both Cameras

**Cause:** Cameras too far apart or pattern too close

**Solution:**
1. Move pattern to center of field of view
2. Adjust camera angles (converge more)
3. Use larger pattern if available
4. Move pattern farther from cameras

---

## Advanced Tips

### Lens Distortion

**Fisheye/Wide-Angle Lenses:**
- Require more calibration images (30-40)
- Capture images at frame edges
- RMS error may be higher (up to 1.5 OK)

**Telephoto Lenses:**
- Less distortion, easier to calibrate
- Fewer images needed (15-20)
- Tighter field of view

### Outdoor Calibration

**Challenges:**
- Wind (pattern moves)
- Varying lighting (clouds)
- Glare on pattern

**Solutions:**
- Calibrate on overcast day
- Use matte finish on pattern
- Weight pattern to prevent movement
- Morning/evening light (less harsh)

### Camera Synchronization

**For best results:**
- Cameras should capture frames simultaneously
- Use hardware trigger if available
- Otherwise, rely on timestamp matching

**Check sync:**
```
Tools → Camera Sync Test:
- Shows frame timing offset
- Should be <10ms
- If >30ms, detection may suffer
```

### Recalibration Schedule

**When to recalibrate:**
- ✅ **Always:** After moving cameras
- ✅ **Always:** After changing focus/zoom
- ⚠️ **Sometimes:** Monthly for permanent setups
- ⚠️ **Sometimes:** After rough handling
- ❌ **Rarely:** Intrinsic (unless hardware change)

### Calibration Quality Check

**Good calibration indicators:**
- RMS error <1.0 pixels
- Smooth 3D trajectory (no jitter)
- Velocity consistent with radar gun
- Strike zone looks correct size
- Reprojection error low

**Poor calibration indicators:**
- Jumping/jittery 3D position
- Velocity wildly off (±10mph)
- Strike zone too big/small
- Ball appears to curve unnaturally

---

## Quick Reference Card

### Calibration Checklist

**Physical Setup:**
- [ ] Cameras 6-8 feet apart
- [ ] Same height from ground
- [ ] Angled inward (converging)
- [ ] 50-60 feet from mound
- [ ] Firmly mounted (no wobble)
- [ ] Measured separation distance

**Intrinsic (per camera):**
- [ ] Flat checkerboard pattern
- [ ] 20-30 images captured
- [ ] Various distances/angles
- [ ] RMS error <1.0 pixels
- [ ] Saved profile

**Extrinsic:**
- [ ] Both cameras see pattern
- [ ] 10-15 stereo image pairs
- [ ] Cover full strike zone volume
- [ ] Baseline matches measurement
- [ ] 3D test looks good

**Strike Zone:**
- [ ] Plate position set
- [ ] Batter height entered
- [ ] Strike zone overlay verified
- [ ] Saved profile

---

## Example Timeline

**First Time Setup (60 min):**
- Physical setup: 20 min
- Intrinsic calibration: 30 min (15 min × 2 cameras)
- Extrinsic calibration: 15 min
- Strike zone: 5 min
- Testing: 5 min

**Recalibration (15 min):**
- Verify physical setup: 2 min
- Load intrinsic profile: 1 min
- Extrinsic calibration: 10 min
- Verify: 2 min

**Quick Setup (5 min):**
- Load saved profile: 1 min
- Verify cameras in same position: 2 min
- Test 3D tracking: 2 min

---

## Further Resources

- **Video Tutorial:** [YouTube link] (if available)
- **Checkerboard Pattern:** Tools → Print Calibration Pattern
- **Support Forum:** forum.pitchtracker.example.com/calibration
- **Sample Profiles:** docs/calibration/examples/

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**For Version:** PitchTracker 1.2.0

