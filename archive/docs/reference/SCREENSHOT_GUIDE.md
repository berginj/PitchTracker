# Screenshot Capture Guide

Quick reference for capturing screenshots for demos and documentation.

## Setup

Create screenshots directory:
```powershell
mkdir screenshots
```

## Screenshot List

### 01_launcher.png
**Window:** launcher.py main window
**What to show:**
- Two large role buttons (green setup, blue coaching)
- "About" button in footer
- Clean, professional layout

**How to capture:**
```powershell
python launcher.py
# Take screenshot of full window
```

---

### 02_step1_camera_setup.png
**Window:** Setup Wizard - Step 1
**What to show:**
- Camera selection dropdowns
- Live camera previews (if available)
- "Next" button enabled

**How to capture:**
```powershell
python launcher.py
# Click "Setup & Calibration"
# At Step 1, select cameras
# Take screenshot
```

---

### 03_step2_calibration.png
**Window:** Setup Wizard - Step 2
**What to show:**
- Live camera feeds
- Checkerboard detection (green corners if pattern visible)
- Capture button and counter
- Image thumbnails (if captured)

**How to capture:**
```powershell
# At Step 2
# Hold checkerboard in view (if available)
# Show detection overlay
# Take screenshot
```

---

### 04_step3_roi_configuration.png
**Window:** Setup Wizard - Step 3
**What to show:**
- Camera preview
- Drawn ROI rectangles (lane and plate)
- Drawing mode indicators

**How to capture:**
```powershell
# At Step 3
# Draw lane ROI
# Draw plate ROI
# Take screenshot showing both ROIs
```

---

### 05_step4_detector_tuning.png
**Window:** Setup Wizard - Step 4
**What to show:**
- Detector mode selection
- Configuration parameters
- Preview with detections (if ball visible)

**How to capture:**
```powershell
# At Step 4
# Select detector mode
# Adjust parameters
# Take screenshot
```

---

### 06_step5_validation.png
**Window:** Setup Wizard - Step 5
**What to show:**
- All validation checks passing (green checkmarks)
- System status indicators

**How to capture:**
```powershell
# At Step 5
# Wait for validation to complete
# Take screenshot showing green checkmarks
```

---

### 07_step6_export.png
**Window:** Setup Wizard - Step 6
**What to show:**
- Configuration summary
- "Generate Report" button
- Completion status

**How to capture:**
```powershell
# At Step 6
# Show summary
# Take screenshot
```

---

### 08_coaching_dashboard.png
**Window:** Coaching App - Idle state
**What to show:**
- Full dashboard layout
- All sections visible (cameras, metrics, visualizations)
- "Start Session" button prominent

**How to capture:**
```powershell
python launcher.py
# Click "Coaching Sessions"
# Take screenshot of idle dashboard
```

---

### 09_session_start_dialog.png
**Window:** Session Start Dialog
**What to show:**
- Pitcher selection
- Session name field
- Batter height slider
- Ball type selection
- "Start" button

**How to capture:**
```powershell
# From coaching dashboard
# Click "Start Session"
# Fill in dialog
# Take screenshot before clicking Start
```

---

### 10_live_preview.png
**Window:** Coaching App - Active session
**What to show:**
- Live camera feeds updating
- Strike zone overlays visible
- Recording indicator active

**How to capture:**
```powershell
# After starting session
# Cameras showing live feed
# Take screenshot
```

---

### 11_pitch_detected.png
**Window:** Coaching App - After pitch
**What to show:**
- Pitch count updated (e.g., "Pitches: 1")
- Latest pitch metrics showing:
  - Speed: XX.X mph
  - H-Break: ±X.X in
  - V-Break: ±X.X in
  - Result: STRIKE or BALL (color-coded)

**How to capture:**
```powershell
# After detecting a pitch (or use test data)
# Metrics updated
# Take screenshot
```

---

### 12_heat_map.png
**Window:** Coaching App - Heat map section
**What to show:**
- 3x3 grid with pitch counts
- Color intensity showing distribution
- Numbers in zones

**How to capture:**
```powershell
# After 5-10 pitches recorded
# Heat map populated
# Take screenshot focused on heat map widget
```

---

### 13_strike_zone_overlay.png
**Window:** Coaching App - Camera view closeup
**What to show:**
- Strike zone grid overlay (green)
- Latest pitch marker (red circle)
- 3x3 grid divisions

**How to capture:**
```powershell
# During active session
# After pitch detected
# Take screenshot of left camera view
```

---

### 14_trajectory_view.png
**Window:** Coaching App - Trajectory section
**What to show:**
- Multiple pitch trajectories (faded)
- Mound, plate, strike zone
- Release and crossing markers

**How to capture:**
```powershell
# After 3-5 pitches recorded
# Trajectory widget showing multiple paths
# Take screenshot of trajectory widget
```

---

### 15_recent_pitches.png
**Window:** Coaching App - Recent pitches list
**What to show:**
- List of 5-10 recent pitches
- Speed and result for each
- Color coding (green strikes, red balls)

**How to capture:**
```powershell
# After multiple pitches
# List populated
# Take screenshot of recent pitches widget
```

---

### 16_session_summary.png
**Window:** Session End Dialog
**What to show:**
- Session summary statistics:
  - Total pitches
  - Strikes count
  - Balls count
  - Session data saved message

**How to capture:**
```powershell
# Click "End Session"
# Session summary dialog appears
# Take screenshot
```

---

### 17_session_files.png
**Window:** File Explorer
**What to show:**
- Session folder structure
- Video files (MP4s)
- CSV files
- Manifest.json
- Pitch subfolders

**How to capture:**
```powershell
# Open File Explorer
# Navigate to data/sessions/<session_name>/
# Show folder contents
# Take screenshot
```

---

## Screenshot Tips

### Windows (Built-in)

**Full Window:**
- Press `Alt + Print Screen` to capture active window
- Paste into Paint or image editor
- Save as PNG

**Snipping Tool:**
- Press `Windows + Shift + S`
- Select rectangular snip
- Saves to clipboard
- Paste and save

**Snip & Sketch:**
- Press `Windows + Shift + S`
- Choose area to capture
- Automatically saves to Pictures/Screenshots

### Third-Party Tools

**ShareX** (Recommended):
- Free, open-source
- Automatic numbering
- Region capture with hotkeys
- Built-in editor

**Greenshot**:
- Free for Windows
- Region capture
- Quick annotations
- Auto-save to folder

---

## Screenshot Standards

**Format:** PNG (lossless)
**Resolution:** Native (don't scale)
**Naming:** Use provided names (01_launcher.png, etc.)
**Location:** Save to `screenshots/` directory

**Quality Checklist:**
- [ ] Full window visible (not cropped)
- [ ] Text is readable
- [ ] UI elements are clear
- [ ] No personal information visible
- [ ] Consistent window size across similar screenshots
- [ ] Clean desktop background (if showing taskbar)

---

## Testing with Sample Data

If cameras are not available, use test mode:

```powershell
# Generate test session data
python test_coaching_app.py --mock-data

# Or use pre-recorded session
# Copy sample session to data/sessions/
# Launch coaching app
# Load session for screenshots
```

---

## Batch Screenshot Script

PowerShell script to automate window captures:

```powershell
# screenshot_batch.ps1

# Install required module
# Install-Module -Name PSWindowCapture

# Launch app
Start-Process python -ArgumentList "launcher.py" -PassThru

# Wait for window
Start-Sleep -Seconds 3

# Capture window
# Add-Type -AssemblyName System.Windows.Forms
# $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
# $bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
# $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
# $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
# $bitmap.Save("screenshots/01_launcher.png", [System.Drawing.Imaging.ImageFormat]::Png)

# Repeat for each step...
```

---

## Demo Video Recording

**Recommended Tools:**

1. **OBS Studio** (Free)
   - Download: https://obsproject.com/
   - Settings:
     - 1920x1080 resolution
     - 30 FPS
     - MP4 format (H.264)
     - Audio: Microphone enabled

2. **Screen Recording Settings:**
   - Capture full screen or application window
   - Enable cursor capture
   - Record audio narration
   - Output: 1080p @ 30fps

3. **Editing:**
   - Trim unnecessary parts
   - Add title card (intro)
   - Add captions for key features
   - Export as MP4

---

## Screenshot Delivery

Once all screenshots are captured:

1. **Review:** Check all 17 screenshots for quality
2. **Rename:** Ensure correct naming convention
3. **Organize:** Place in `screenshots/` directory
4. **Compress:** Create `screenshots.zip` for distribution
5. **Update:** Add paths to DEMO_GUIDE.md

---

## Next Steps

After capturing screenshots:

1. Create demo video (10-12 min)
2. Update UI_PROTOTYPES_SUMMARY.md with screenshot links
3. Add screenshots to README.md
4. Prepare demo presentation slides (optional)
5. Test demo on clean machine

---

**End of Screenshot Guide**
