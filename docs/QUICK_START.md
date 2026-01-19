# PitchTracker - Quick Start Guide

**Last Updated:** 2026-01-19
**Version:** 2.0

Get up and running with PitchTracker in 30 minutes!

---

## What You'll Need

Before starting, gather:

- [ ] **Two USB cameras** (1280x720 @ 60fps or 30fps)
- [ ] **USB 3.0 cables** (< 3 feet, high quality)
- [ ] **Camera mounts/tripods**
- [ ] **Checkerboard pattern** (printed on rigid surface)
- [ ] **Ruler or measuring tape** (for camera distance)
- [ ] **Computer** with Windows 10/11, 8GB+ RAM, 100GB+ free disk space

---

## Step 1: Installation (5 minutes)

### Download & Install

1. Download latest installer from GitHub releases
2. Run `PitchTracker-Setup-vX.X.X.exe`
3. Follow installation wizard
4. Launch PitchTracker from desktop shortcut

### First Launch

On first launch, you'll see the **Setup Wizard**.
- Don't skip it! Proper setup is critical for accuracy
- You can re-run it later: Setup menu → Setup Wizard

---

## Step 2: Camera Setup (5 minutes)

### Physical Positioning

1. **Place cameras 6-8 feet apart**
   - Measure from lens center to lens center
   - Write down exact distance (you'll need it)

2. **Angle cameras inward toward strike zone**
   - Both cameras should see the strike zone
   - Overlapping field of view is essential

3. **Height: About chest level**
   - Cameras should see from release point through strike zone
   - Slight downward angle is okay

4. **Secure cameras**
   - Use tripods or mount to wall/ceiling
   - Must be completely stable (no movement)

### Camera Connection

1. **Connect cameras to computer**
   - Use USB 3.0 ports (blue colored)
   - Use separate USB ports (not same hub)
   - Connect directly to motherboard if possible

2. **Verify cameras detected**
   - Check Windows Camera app
   - Both cameras should work independently

---

## Step 3: Setup Wizard (15 minutes)

The Setup Wizard will guide you through:

### 3.1 Camera Selection

- Select left and right cameras from dropdown
- Test preview to verify correct cameras
- Adjust resolution and framerate
  - **Recommended:** 1280x720 @ 60fps
  - **Lower-end PC:** 1280x720 @ 30fps or 640x480 @ 30fps

### 3.2 ROI (Region of Interest)

**Purpose:** Define strike zone area for detection

**Steps:**
1. Position cameras to see strike zone
2. For each camera:
   - Click "Draw ROI"
   - Draw rectangle around strike zone
   - Include a bit extra (ball enters/exits)
3. Click "Next"

**Tips:**
- ROI should be larger than strike zone
- Includes some background above/below
- Both cameras need good view of same area

### 3.3 Intrinsic Calibration

**Purpose:** Correct for lens distortion

**Preparation:**
- Print checkerboard pattern (9x6 or 10x7 squares)
- Mount on rigid surface (foam board, cardboard)
- Don't use flimsy paper (it bends)

**Steps:**
1. Hold checkerboard in camera view
2. Click "Capture" when pattern detected (corners shown in green)
3. Take 20-30 images from different positions:
   - Center of view
   - Four corners
   - Various distances
   - Various angles (tilted, rotated)
4. Click "Calibrate" when done
5. Repeat for second camera
6. Click "Next"

**Success indicators:**
- Green checkmark appears
- Reprojection error < 1.0 pixels (excellent), < 2.0 (acceptable)

**If fails:** See TROUBLESHOOTING.md → Calibration Issues

### 3.4 Stereo Calibration

**Purpose:** Establish 3D coordinate system

**Steps:**
1. Enter exact distance between cameras (in feet)
   - Measure from lens center to lens center
   - Be precise! This is critical for accuracy
2. Verify cameras see overlapping area
3. Click "Calibrate"
4. Verify 3D coordinates look reasonable

**Success indicators:**
- Green checkmark appears
- Test measurement shows reasonable depth (Z coordinate)

### 3.5 Strike Zone Configuration

**Steps:**
1. Enter batter height (inches)
   - Default: 66" (5'6")
   - Adjust for actual batter
2. Strike zone automatically calculated per MLB rules
3. Click "Finish"

**Setup Complete!** PitchTracker is now ready to use.

---

## Step 4: Your First Recording Session (5 minutes)

### Start Capture

1. **Click "Start Capture"**
   - Both camera previews should update
   - Status bar shows "Capturing"
   - Frame rate displayed

2. **Verify everything working:**
   - Preview shows live video
   - Both cameras updating
   - No error messages

### Start Recording

1. **Click "Start Recording"**
   - Dialog appears
   - Enter session name (e.g., "practice-2026-01-19")
   - Click "OK"

2. **Recording indicator:**
   - Red dot in status bar
   - "Recording" message
   - Disk space indicator updates

### Throw Some Pitches!

- Throw pitches through strike zone
- Watch for green circles on ball (detections)
- Check status bar for detection count
- Continue throwing

### Stop Recording

1. **Click "Stop Recording"**
2. **Session saved automatically:**
   - Location: `recordings/` folder
   - Files: Videos (session_left.avi, session_right.avi) + metadata

### Stop Capture

1. **Click "Stop Capture" when done**
   - Cameras released
   - Can close PitchTracker

---

## Step 5: Review Your Session (5 minutes)

### Open Review Mode

1. **Click "Review Session" button** (🎬 icon)
   - Review Mode window opens

2. **Load your session:**
   - File → Review All Sessions
   - Or: File → Open Session (choose specific one)

### Review Playback

**Controls:**
- **Space:** Play/Pause
- **Arrow keys:** Step forward/backward frame
- **Home/End:** Jump to start/end
- **Timeline:** Click to seek to any point
- **Speed:** Adjust playback speed (0.1x - 2.0x)

### Tune Detection Parameters

**Purpose:** Optimize detection for your environment

**Steps:**
1. **Watch for missed detections:**
   - Frames where ball visible but no green circle

2. **Adjust parameters:**
   - Frame Diff Threshold: Lower = more sensitive
   - BG Diff Threshold: Lower = more sensitive
   - Min/Max Area: Filter by blob size
   - Detection Mode: Try MODE_A, MODE_B, MODE_C

3. **See results immediately:**
   - Green circles update as you adjust
   - Find settings that detect ball consistently

4. **Export tuned settings:**
   - Export → Export Config
   - Use in future sessions

### Score Pitches

**Optional but useful for tracking detection quality:**

1. **Select pitch from list**
2. **Click score button:**
   - ✓ Good: Detection worked perfectly
   - ⚠ Partial: Some detections missed
   - ✗ Missed: Detection completely failed
3. **Navigate:** "Go to Selected Pitch" button
4. **Statistics:** See summary of scores

### Export Data

**Export → Export Annotations:**
- JSON file with all scores and annotations
- Detection parameters
- Session metadata
- Import into analysis tools

---

## Common Issues & Quick Fixes

### "Camera not detected"
- **Fix:** Restart PitchTracker, replug cameras, try different USB ports

### "Video is choppy/laggy"
- **Fix:** Lower resolution (Settings → Camera → 1280x720 @ 30fps)

### "Detection not working"
- **Fix:** Check lighting, adjust parameters in Review Mode

### "Low disk space warning"
- **Fix:** Delete old recordings, keep 50GB+ free

### "Calibration failed"
- **Fix:** Take more images (30+), ensure checkerboard is rigid and flat

**For more help:** See TROUBLESHOOTING.md

---

## Tips for Best Results

### Lighting
- ✅ Even, diffuse lighting
- ✅ No direct sunlight
- ✅ No dark shadows
- ❌ Avoid backlighting (bright background, dark subject)

### Camera Setup
- ✅ Completely stable (no vibration)
- ✅ Clean lenses
- ✅ 6-8 feet apart
- ✅ Both see strike zone clearly
- ❌ Don't move cameras after calibration

### Detection
- ✅ Solid background (not moving)
- ✅ Good contrast (ball vs background)
- ✅ Ball fully in both camera views
- ❌ Avoid other moving objects

### Recording
- ✅ Keep 100GB+ free disk space
- ✅ Close other camera software
- ✅ Regularly review and delete bad sessions
- ❌ Don't move cameras during session

---

## Next Steps

Now that you're set up:

1. **Practice throwing** to get feel for system
2. **Review sessions** to tune detection
3. **Adjust batter height** for different players
4. **Experiment with detection modes** for your environment
5. **Export data** for analysis

### Advanced Usage

See documentation for:
- **ML Data Export:** Export training data for ML models
- **Custom configurations:** Edit configs/default.yaml
- **Multiple profiles:** Save different calibrations
- **Batch processing:** Review many sessions quickly

### Get Help

- **FAQ.md:** Common questions and answers
- **TROUBLESHOOTING.md:** Detailed problem solutions
- **GitHub Issues:** Report bugs, request features
- **docs/ folder:** Technical documentation

---

## Quick Reference Card

### Keyboard Shortcuts

**Main Window:**
- `Ctrl+O` - Open file
- `Ctrl+S` - Save
- `Ctrl+P` - Settings

**Review Mode:**
- `Space` - Play/Pause
- `→` / `←` - Step forward/backward
- `Home` / `End` - Jump to start/end
- `A` - Toggle annotation mode
- `Ctrl+O` - Open session
- `Ctrl+Shift+O` - Review all sessions
- `Ctrl+PgUp/PgDown` - Previous/Next session
- `Ctrl+D` - Delete session

### Important Locations

- **Recordings:** `C:\Users\<you>\Documents\PitchTracker\recordings\`
- **Logs:** `<install>\logs\`
- **Config:** `<install>\configs\default.yaml`
- **Settings:** `%APPDATA%\PitchTracker\`

### Status Bar Indicators

- **FPS:** Current frame rate
- **Detections:** Detection count (L=left, R=right)
- **Disk Space:** Free space on recordings drive
- **Recording:** Red dot when recording active

---

**Congratulations!** You're ready to track pitches with PitchTracker!

For questions or issues, see FAQ.md and TROUBLESHOOTING.md.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-19
