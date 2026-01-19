# PitchTracker Demo Guide

## Overview

This guide provides a comprehensive demonstration script for showcasing PitchTracker's dual-camera pitch tracking system with role-based interfaces.

**Version:** 1.0.0
**Target Audience:** Coaches, technicians, potential users, stakeholders
**Demo Duration:** 15-20 minutes

---

## Demo Structure

1. **Introduction** (2 min) - System overview and capabilities
2. **Unified Launcher** (1 min) - Role-based entry point
3. **Setup Wizard** (5-7 min) - System configuration workflow
4. **Coaching App** (7-10 min) - Live session management and tracking
5. **Conclusion** (2 min) - Summary and Q&A

---

## Part 1: Introduction (2 minutes)

### Opening Statement

"Welcome! Today I'll demonstrate PitchTracker, a dual-camera stereo vision system for baseball pitch tracking and analysis. The system provides:

- **Real-time pitch detection** using computer vision
- **3D trajectory reconstruction** via stereo triangulation
- **Strike zone analysis** with configurable batter height
- **Session recording** with detailed metrics
- **Two role-based interfaces** - one for setup, one for coaching"

### Key Features Highlight

- ✓ Dual-camera stereo vision (left/right cameras)
- ✓ Real-time detection (30 FPS preview, 10 Hz metrics)
- ✓ Strike zone analysis (3x3 grid)
- ✓ Session recording (full video + pitch-by-pitch data)
- ✓ Heat map visualization
- ✓ Trajectory plotting

---

## Part 2: Unified Launcher (1 minute)

### Launch Command

```powershell
python launcher.py
```

### What to Show

**Window:** Main launcher with two large role selector buttons

**Screenshot Location:** `screenshots/01_launcher.png`

**Narration:**

"The launcher provides two entry points based on user role:

1. **Setup & Calibration** (Green button)
   - For technicians and installers
   - One-time configuration
   - Camera setup, calibration, ROI configuration

2. **Coaching Sessions** (Blue button)
   - For coaches and pitchers
   - Daily use during practice
   - Quick session start, live tracking, metrics"

**Action:** Click the "About" button to show version and component information.

---

## Part 3: Setup Wizard (5-7 minutes)

### Launch

Click **"🔧 Setup & Calibration"** from the launcher.

### Step 1: Camera Setup (1 min)

**Screenshot:** `screenshots/02_step1_camera_setup.png`

**What to Show:**

- Camera discovery (UVC backend finds connected cameras)
- Left camera selection (dropdown or serial number)
- Right camera selection
- Live preview of both cameras
- Camera info display (resolution, FPS)

**Narration:**

"Step 1 handles camera detection and assignment. The system supports:
- UVC (plug-and-play USB cameras)
- FLIR/Basler cameras via serial numbers
- Live preview to verify camera positioning
- Automatic resolution/FPS configuration"

**Action:** Select left and right cameras, verify previews, click "Next".

---

### Step 2: Stereo Calibration (2 min)

**Screenshot:** `screenshots/03_step2_calibration.png`

**What to Show:**

- Checkerboard pattern detection (live feed)
- Capture button with image counter
- Captured image thumbnails
- Calibration progress (need 10+ images)
- Calibration button and results

**Narration:**

"Stereo calibration computes the geometric relationship between cameras:
- Hold a checkerboard pattern visible to both cameras
- System detects corners in real-time (green overlay)
- Capture 10-20 image pairs from different angles
- Click 'Run Calibration' to compute camera matrices
- Results show reprojection error (should be < 1.0 pixels)"

**Action:**

1. Show checkerboard detection (green corners overlay)
2. Capture 3-4 images (show counter incrementing)
3. Click "Run Calibration"
4. Show success message with error metrics

---

### Step 3: ROI Configuration (1 min)

**Screenshot:** `screenshots/04_step3_roi_configuration.png`

**What to Show:**

- Camera preview with drawing tools
- Lane ROI (region where ball travels)
- Plate ROI (region near home plate)
- Interactive rectangle drawing
- Save confirmation

**Narration:**

"ROI (Region of Interest) configuration focuses detection on relevant areas:
- **Lane ROI**: Wide corridor from mound to plate
- **Plate ROI**: Focused area near home plate for strike zone
- Draw rectangles by clicking and dragging
- ROIs are shared between left and right cameras
- Reduces false detections and improves performance"

**Action:**

1. Draw lane ROI (large rectangle covering pitch path)
2. Draw plate ROI (small rectangle near plate)
3. Click "Save ROIs"

---

### Step 4: Detector Tuning (1 min)

**Screenshot:** `screenshots/05_step4_detector_tuning.png`

**What to Show:**

- Detection mode selection (Classical vs ML)
- Detector type options (CircleFinder, ContourFinder, etc.)
- Configuration parameters (sliders/inputs)
- Preview with detection overlay

**Narration:**

"Detection tuning configures the computer vision algorithm:
- **Classical mode**: Circle detection, contour detection
- **ML mode**: Neural network detectors (if trained)
- Adjust sensitivity, thresholds, filters
- Preview shows detected balls in real-time"

**Action:** Select "Classical - CircleFinder", adjust parameters, show detections.

---

### Step 5: System Validation (1 min)

**Screenshot:** `screenshots/06_step5_validation.png`

**What to Show:**

- Automated validation checks
- Green checkmarks for passing tests
- Warning/error indicators if issues found
- Validation report

**Narration:**

"Validation ensures the system is ready for use:
- ✓ Cameras accessible
- ✓ Calibration data present
- ✓ ROIs configured
- ✓ Detector initialized
- ✓ All dependencies available

Any failures are highlighted with suggestions for fixes."

**Action:** Show all checks passing (green checkmarks).

---

### Step 6: Export & Complete (30 sec)

**Screenshot:** `screenshots/07_step6_export.png`

**What to Show:**

- Configuration summary
- Export report button
- Completion message

**Narration:**

"Final step generates a setup report:
- Configuration summary (cameras, calibration, ROIs)
- Validation results
- System specifications
- Ready for coaching use!"

**Action:** Click "Generate Report", show `setup_report.txt`.

---

## Part 4: Coaching App (7-10 minutes)

### Launch

Return to launcher, click **"⚾ Coaching Sessions"**.

### Main Dashboard (1 min)

**Screenshot:** `screenshots/08_coaching_dashboard.png`

**What to Show:**

- Clean interface with large "Start Session" button
- Three main areas:
  1. Camera previews (left and right)
  2. Metrics panel (speed, break, result)
  3. Visualizations (heat map, trajectory, recent pitches)

**Narration:**

"The coaching dashboard is optimized for quick session starts:
- Large, color-coded buttons
- Real-time camera preview (30 FPS)
- Live metrics updated every 100ms
- Three visualization types:
  - Heat map (pitch location distribution)
  - Trajectory (side view of pitch path)
  - Recent pitches list"

---

### Start Session Dialog (1 min)

**Screenshot:** `screenshots/09_session_start_dialog.png`

**What to Show:**

- Pitcher selection (dropdown of saved pitchers)
- Session name (auto-generated: "Pitcher_2026-01-16_14-30")
- Batter height slider (48-84 inches)
- Ball type selection (Baseball/Softball)
- Calibration status indicator

**Narration:**

"Starting a session takes less than 10 seconds:
- Select pitcher from saved list
- Session name auto-generated (editable)
- Adjust batter height for strike zone
- Choose ball type (affects tracking)
- Verify calibration is loaded"

**Action:**

1. Select pitcher "John Doe"
2. Set batter height to 60 inches
3. Choose "Baseball"
4. Click "Start Session"

---

### Live Camera Preview (1 min)

**Screenshot:** `screenshots/10_live_preview.png`

**What to Show:**

- Left and right camera views updating at 30 FPS
- Strike zone overlay (green 3x3 grid)
- Latest pitch marker (red circle)
- Clear, smooth video

**Narration:**

"Camera preview provides real-time feedback:
- 30 frames per second refresh rate
- Strike zone overlay shows target area
- Latest pitch marked with red circle
- Overlay updates automatically with batter height changes"

**Action:** Show cameras running, overlay visible.

---

### Pitch Detection (2 min)

**Screenshot:** `screenshots/11_pitch_detected.png`

**What to Show:**

- Session actively recording (red "● Recording" indicator)
- Pitch count incrementing
- Latest pitch metrics updating:
  - Speed: 65.2 mph
  - H-Break: +2.3 in
  - V-Break: -1.1 in
  - Result: STRIKE (green) or BALL (red)

**Narration:**

"When a pitch is thrown, the system automatically:
1. Detects ball in both cameras
2. Triangulates 3D position
3. Tracks trajectory to plate
4. Calculates metrics (speed, break, strike/ball)
5. Updates all visualizations
6. Records pitch video with pre/post-roll

All of this happens in real-time, with metrics appearing within 1 second."

**Demo Scenario:**

- Simulate or show recorded pitch
- Point out pitch count incrementing
- Highlight speed and break values
- Show STRIKE/BALL result

---

### Heat Map Visualization (1 min)

**Screenshot:** `screenshots/12_heat_map.png`

**What to Show:**

- 3x3 grid with pitch counts per zone
- Color intensity gradient:
  - White (0 pitches)
  - Light blue (few pitches)
  - Blue (moderate)
  - Purple (many)
  - Red (most pitches)
- Numbers showing count in each zone

**Narration:**

"The heat map shows pitch location distribution across the strike zone:
- 3x3 grid divides strike zone
- Color intensity indicates frequency
- Only counts pitches inside strike zone
- Helps identify pitcher tendencies
- Updates automatically as pitches accumulate

In this example, we can see the pitcher is targeting the lower-right quadrant."

---

### Strike Zone Overlay (1 min)

**Screenshot:** `screenshots/13_strike_zone_overlay.png`

**What to Show:**

- Strike zone grid overlaid on camera views
- Latest pitch location marked
- Grid adjusts with batter height

**Narration:**

"The strike zone overlay provides immediate visual feedback:
- 3x3 grid drawn on live camera feed
- Latest pitch location shown as red circle
- Zone boundaries update when batter height changes
- Helps pitcher see accuracy in real-time
- Transparent design doesn't obscure camera view"

**Action:** Show multiple pitches accumulating on overlay.

---

### Trajectory Visualization (1 min)

**Screenshot:** `screenshots/14_trajectory_view.png`

**What to Show:**

- 2D side view (Y-Z plane)
- Mound and plate positions
- Ground line and strike zone rectangle
- Last 5 pitch trajectories:
  - Fading effect (oldest = lightest)
  - Release point markers (circles)
  - Plate crossing markers
- Distance markers (20, 40, 60 feet)

**Narration:**

"The trajectory view shows pitch path from release to plate:
- Side view (distance vs height)
- Shows last 5 pitches with fade effect
- Release point and plate crossing marked
- Strike zone rectangle for reference
- Helps identify release point consistency
- Visualizes pitch arc and drop

Notice how the pitches follow similar arcs but vary slightly in release height and plate crossing."

---

### Recent Pitches List (30 sec)

**Screenshot:** `screenshots/15_recent_pitches.png`

**What to Show:**

- List of last 10 pitches (most recent first)
- Each entry shows:
  - Pitch number
  - Speed (mph)
  - Result (STRIKE/BALL)
- Color-coded (green for strikes, red for balls)

**Narration:**

"Recent pitches list provides quick summary:
- Last 10 pitches visible
- Speed and result for each
- Color-coded for quick scanning
- Helps track performance trends during session"

---

### End Session (1 min)

**Screenshot:** `screenshots/16_session_summary.png`

**What to Show:**

- Click "End Session" button
- Confirmation dialog
- Session summary:
  - Total pitches: 15
  - Strikes: 9
  - Balls: 6
  - Session data saved message

**Narration:**

"Ending a session captures all data:
- Confirmation prevents accidental stops
- Session summary shows key stats
- All videos saved to data/sessions/ directory
- Manifest.json contains detailed metrics
- Ready for post-session analysis"

**Action:**

1. Click "⏹ End Session"
2. Confirm in dialog
3. Show session summary
4. Return to ready state

---

### Session Data Location (30 sec)

**Screenshot:** `screenshots/17_session_files.png`

**What to Show:**

File structure:
```
data/sessions/JohnDoe_2026-01-16_14-30/
├── manifest.json          # Session metadata
├── left_session.mp4       # Left camera full session
├── right_session.mp4      # Right camera full session
├── left_detections.csv    # Frame-by-frame detections
├── right_detections.csv
└── pitches/               # Individual pitch recordings
    ├── pitch_001/
    │   ├── left.mp4
    │   ├── right.mp4
    │   └── manifest.json  # Pitch metadata, trajectory
    └── pitch_002/
        └── ...
```

**Narration:**

"All session data is organized and accessible:
- Full session videos from both cameras
- Detection CSV files for analysis
- Individual pitch folders with pre/post-roll clips
- Manifest files contain all metrics and trajectories
- Ready for import into analysis tools or review"

---

## Part 5: Conclusion (2 minutes)

### Summary

"We've demonstrated PitchTracker's complete workflow:

**Setup (One-time):**
- Camera detection and configuration
- Stereo calibration for 3D tracking
- ROI setup to focus detection
- Validation ensures system readiness

**Coaching (Daily Use):**
- Quick session starts (<10 seconds)
- Real-time pitch tracking (30 FPS)
- Live metrics (speed, break, strike/ball)
- Three visualization types (heat map, trajectory, recent list)
- Automatic recording and data organization

**Key Benefits:**
- ✓ Accurate tracking using stereo vision
- ✓ Real-time feedback during practice
- ✓ Comprehensive data collection
- ✓ Easy-to-use role-based interfaces
- ✓ Professional data organization"

---

### Q&A Topics

**Common Questions:**

1. **"What cameras are supported?"**
   - Any UVC (USB Video Class) camera
   - FLIR BlackFly S (via Spinnaker SDK)
   - Basler cameras (via Pylon SDK)
   - Recommended: 720p+ resolution, 60+ FPS

2. **"How accurate is the tracking?"**
   - Calibration reprojection error typically < 0.5 pixels
   - Speed accuracy within ±1 mph (depends on calibration)
   - Strike zone accuracy within ±1 inch

3. **"Can it track different ball types?"**
   - Yes, supports baseball and softball
   - Configurable ball radius in settings
   - Detection parameters tunable per ball type

4. **"Does it work outdoors?"**
   - Best results indoors with controlled lighting
   - Outdoor use requires good lighting (cloudy day ideal)
   - Direct sunlight can cause issues with detection

5. **"What hardware is required?"**
   - Dual cameras (see supported list)
   - Windows 10/11 or Linux
   - Python 3.9+
   - CPU: i5 or better (for real-time processing)
   - RAM: 8GB minimum, 16GB recommended

6. **"Can I export data for analysis?"**
   - Yes, all data saved in standard formats
   - Videos: MP4 (H.264)
   - Detections: CSV files
   - Metadata: JSON files
   - Easy to import into Excel, Python, R, etc.

---

## Screenshot Checklist

Create screenshots for each of the following:

- [ ] `01_launcher.png` - Main launcher window with role buttons
- [ ] `02_step1_camera_setup.png` - Camera selection with previews
- [ ] `03_step2_calibration.png` - Calibration step with checkerboard detection
- [ ] `04_step3_roi_configuration.png` - ROI drawing interface
- [ ] `05_step4_detector_tuning.png` - Detector configuration panel
- [ ] `06_step5_validation.png` - Validation checklist with green checkmarks
- [ ] `07_step6_export.png` - Setup completion summary
- [ ] `08_coaching_dashboard.png` - Coaching app main view (idle)
- [ ] `09_session_start_dialog.png` - Session configuration dialog
- [ ] `10_live_preview.png` - Live camera feeds with overlays
- [ ] `11_pitch_detected.png` - Dashboard with pitch metrics displayed
- [ ] `12_heat_map.png` - Heat map with multiple pitches
- [ ] `13_strike_zone_overlay.png` - Camera view with strike zone grid
- [ ] `14_trajectory_view.png` - Trajectory visualization with multiple pitches
- [ ] `15_recent_pitches.png` - Recent pitches list populated
- [ ] `16_session_summary.png` - Session end summary dialog
- [ ] `17_session_files.png` - File explorer showing session data structure

---

## Video Demo Script

**Duration:** 10-12 minutes

### Intro (30 sec)
- Show launcher
- "Today we'll demonstrate PitchTracker..."

### Setup Wizard (4 min)
- Fast-forward through all 6 steps
- Highlight key actions (camera selection, calibration, ROI drawing)
- Show validation success

### Coaching Session (5 min)
- Start session (show dialog)
- Show live camera preview
- Demonstrate 3-4 pitch detections
- Highlight each visualization updating
- Show metrics changing
- End session and show summary

### Data Review (1 min)
- Open session folder
- Show video files
- Open manifest.json
- Briefly show CSV data

### Closing (30 sec)
- Recap key features
- Call to action (GitHub, documentation)

---

## Tips for Effective Demonstration

### Before the Demo

1. **Test Everything:**
   - Run through entire demo flow
   - Verify cameras are connected
   - Check lighting conditions
   - Prepare sample data if cameras unavailable

2. **Prepare Backup:**
   - Have screenshots ready if live demo fails
   - Pre-record video as fallback
   - Test on presentation machine

3. **Know Your Audience:**
   - Technical audience: Show code, configuration files
   - Non-technical: Focus on UI and results
   - Coaches: Emphasize speed, ease of use
   - Developers: Highlight architecture, extensibility

### During the Demo

1. **Pace Yourself:**
   - Don't rush through steps
   - Pause for questions
   - Highlight key features clearly

2. **Narrate Actions:**
   - Explain what you're clicking
   - Describe what's happening
   - Point out important details

3. **Show, Don't Tell:**
   - Actual system interaction > slides
   - Live demo > screenshots
   - Real data > mock data

4. **Engage Audience:**
   - Ask questions ("What would you like to see?")
   - Invite suggestions for parameters
   - Encourage hands-on trial if possible

### Handling Issues

1. **Camera Not Detected:**
   - Have screenshots ready
   - Show pre-recorded video
   - Explain typical setup process

2. **Calibration Fails:**
   - Use pre-existing calibration data
   - Skip to coaching app demo
   - Explain requirements (lighting, pattern visibility)

3. **No Pitch Detection:**
   - Show pre-recorded session
   - Explain detection requirements
   - Demo with archived data

---

## Additional Resources

- **README_LAUNCHER.md** - Quick start guide
- **UI_PROTOTYPES_SUMMARY.md** - Complete UI documentation
- **setup_report.txt** - Sample setup report
- **GitHub Repository** - Source code and issues
- **Demo Video** - Pre-recorded full demonstration

---

## Demo Customization

### For Different Audiences

**Technical Teams:**
- Show configuration files (YAML structure)
- Demonstrate detector tuning parameters
- Discuss architecture and extensibility
- Review code organization

**Coaches/End Users:**
- Focus on ease of use
- Emphasize speed (< 10 sec session start)
- Show data export for athlete review
- Demonstrate session comparison

**Stakeholders/Decision Makers:**
- Highlight key benefits and ROI
- Show professional UI design
- Emphasize data organization
- Discuss deployment options

---

## Version History

**v1.0.0** (2026-01-16)
- Initial demo guide
- Complete screenshot checklist
- Video script included
- Q&A section added

---

## Contact & Support

For questions or issues during demonstration:
- Check console output for error messages
- Review logs in project directory
- Consult README_LAUNCHER.md
- Submit issues to GitHub repository

---

**End of Demo Guide**
