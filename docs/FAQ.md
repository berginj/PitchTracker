# PitchTracker - Frequently Asked Questions (FAQ)

**Last Updated:** 2026-01-19
**Version:** 2.0

---

## Table of Contents

- [Installation & Setup](#installation--setup)
- [Camera Issues](#camera-issues)
- [Calibration](#calibration)
- [Recording & Performance](#recording--performance)
- [Data & Export](#data--export)
- [General Usage](#general-usage)

---

## Installation & Setup

### Q: What are the system requirements?

**A:**
- **OS:** Windows 10 (version 1809+) or Windows 11
- **CPU:** Intel i5 or better (quad-core recommended)
- **RAM:** 8GB minimum, 16GB recommended
- **Disk:** 100GB+ free space for recordings
- **USB:** USB 3.0 ports for cameras
- **Cameras:** Two compatible USB cameras (1280x720 @ 60fps recommended)

### Q: How do I install PitchTracker?

**A:**
1. Download the latest installer from GitHub releases
2. Run `PitchTracker-Setup-vX.X.X.exe`
3. Follow the installation wizard
4. Launch from desktop shortcut or Start menu
5. Run the Setup Wizard on first launch

### Q: Do I need Python installed?

**A:** No! The installer includes everything needed. You don't need Python, OpenCV, or any other dependencies.

### Q: Can I install PitchTracker on multiple computers?

**A:** Yes, you can install on as many computers as you need. Each installation is independent.

### Q: How do I update to a new version?

**A:** PitchTracker checks for updates automatically. When a new version is available:
1. You'll see an update notification
2. Click "Download Update"
3. The installer will download and launch
4. Follow the update wizard

---

## Camera Issues

### Q: Why can't I see my cameras in the camera list?

**A:** Try these steps in order:
1. **Check USB connection:**
   - Use USB 3.0 ports (blue ports)
   - Try different USB ports
   - Avoid USB hubs if possible

2. **Restart the application:**
   - Close PitchTracker completely
   - Unplug cameras
   - Plug cameras back in
   - Launch PitchTracker

3. **Check Windows permissions:**
   - Settings → Privacy → Camera
   - Enable "Let apps access your camera"
   - Enable PitchTracker specifically

4. **Update camera drivers:**
   - Open Device Manager
   - Find your cameras under "Imaging devices"
   - Right-click → Update driver

5. **Check if cameras work elsewhere:**
   - Open Windows Camera app
   - If cameras don't work there, it's a system issue

### Q: Why is my video choppy or laggy?

**A:** Performance issues usually come from:

1. **High resolution/framerate:**
   - Try 1280x720 @ 30fps instead of 60fps
   - Settings → Camera → Resolution
   - Lower settings = smoother performance

2. **CPU overload:**
   - Close other applications
   - Check Task Manager for CPU usage
   - PitchTracker should use 40-60% CPU during capture

3. **USB bandwidth:**
   - Don't use USB hubs for cameras
   - Use separate USB 3.0 ports
   - Don't connect both cameras to same USB controller

4. **Background processes:**
   - Disable Windows indexing on recordings folder
   - Close browser tabs, video players, etc.

### Q: Why do I get "Camera disconnected" errors?

**A:** Common causes:

1. **USB cable issues:**
   - Use high-quality USB 3.0 cables (< 3 feet)
   - Replace damaged cables
   - Secure connections

2. **Power issues:**
   - Some cameras need external power
   - USB hubs may not provide enough power
   - Connect directly to motherboard USB ports

3. **Driver conflicts:**
   - Multiple camera software can conflict
   - Close OBS, Zoom, Teams, etc.
   - Restart computer if needed

**Auto-reconnection:** PitchTracker will attempt to reconnect automatically. You'll see status updates in the UI.

### Q: Can I use different camera brands together?

**A:** Yes! PitchTracker supports mixing camera brands. Requirements:
- Both must support same resolution
- Both must support same framerate
- Both must be USB cameras (not IP cameras)

### Q: What's the difference between color and grayscale mode?

**A:**
- **Color mode (recommended):** Better for Review Mode, looks nicer, slightly higher CPU usage
- **Grayscale mode:** Faster processing, detection doesn't use color anyway
- **Setting:** Settings → Camera → Color Mode

---

## Calibration

### Q: How do I calibrate the system?

**A:** Use the Setup Wizard:
1. **ROI (Region of Interest):**
   - Draw boxes around strike zone on both cameras
   - Make sure strike zone is fully visible

2. **Intrinsic Calibration:**
   - Use checkerboard pattern
   - Take 20+ images from different angles
   - Hold pattern steady for each capture

3. **Stereo Calibration:**
   - Measure exact distance between cameras (in feet)
   - Enter distance accurately (measure from lens centers)

4. **Validation:**
   - Test with known object at known distance
   - Verify 3D coordinates are reasonable

### Q: How far apart should cameras be?

**A:**
- **Recommended:** 6-8 feet apart
- **Minimum:** 4 feet (reduces accuracy)
- **Maximum:** 10 feet (may lose ball in flight)

**Important:** Measure from lens center to lens center, not from camera body edges.

### Q: Do I need to recalibrate every session?

**A:** No, calibration persists between sessions. Recalibrate only if:
- You move the cameras
- You change camera angles
- Accuracy seems degraded
- You see warnings about calibration errors

### Q: What if calibration fails?

**A:** Common issues:
1. **Checkerboard not detected:**
   - Print checkerboard on flat, rigid surface (not paper)
   - Ensure good lighting (no glare or shadows)
   - Hold very steady during capture
   - Make sure entire pattern is visible

2. **Reprojection error too high:**
   - Take more images (30+ recommended)
   - Cover full camera field of view
   - Vary angles and positions more
   - Ensure cameras are stable (not moving)

3. **Stereo calibration fails:**
   - Double-check distance measurement
   - Ensure cameras see overlapping area
   - Check cameras are parallel (not angled away)

---

## Recording & Performance

### Q: How much disk space do recordings use?

**A:** Approximate storage per session:
- **30 second session:** ~200-300 MB
- **100 pitches:** ~20-30 GB
- **1 hour recording:** ~10-15 GB

**Recommendations:**
- Keep 100GB+ free space
- Delete old sessions regularly
- Use Review Mode to identify bad recordings before deleting

### Q: Why am I getting disk space warnings?

**A:** PitchTracker monitors disk space continuously:
- **Warning (20GB):** Session may fill disk - consider ending soon
- **Critical (5GB):** Recording will auto-stop to prevent data corruption

**Solutions:**
- Delete old sessions (recordings/ folder)
- Move recordings to external drive
- Free up space on system drive

### Q: Can I change where recordings are saved?

**A:** Yes:
1. Settings → Recording → Output Directory
2. Choose new location (must have 50GB+ free)
3. Recordings save to new location immediately
4. Old recordings stay in previous location

### Q: Why does recording stop automatically?

**A:** Auto-stop triggers:
- **Disk space < 5GB:** Prevents data corruption
- **Camera disconnected:** Can't record without cameras
- **Internal error:** Check logs for details

**Prevention:**
- Monitor disk space indicator in status bar
- Keep 50GB+ free space
- Use stable USB connections

### Q: Can I record without cameras (simulation mode)?

**A:** Yes, for testing:
1. Launch PitchTracker with `--backend sim` flag
2. Simulated cameras generate test patterns
3. Useful for testing UI and workflow
4. No real ball detection or measurements

---

## Data & Export

### Q: How do I export session data?

**A:**
1. Review Mode → File → Open Session
2. Select session to review
3. Export → Export Annotations (JSON)
4. Save file with scores and annotations

**Exported data includes:**
- Pitch scores (Good/Partial/Missed)
- Manual annotations
- Detection parameters
- Session metadata

### Q: What format are the videos saved in?

**A:**
- **Format:** AVI container
- **Codec:** MJPG (preferred) or XVID/H264/MP4V fallback
- **Frame rate:** Matches capture settings (30 or 60 FPS)
- **Resolution:** Matches camera settings

**Note:** Videos are uncompressed/lightly compressed for quality. They're large but can be re-encoded if needed.

### Q: Can I import old session data?

**A:** Yes, all sessions in `recordings/` folder are automatically available:
- Review Mode → File → Review All Sessions
- Navigate through all recordings
- Score and annotate retroactively

### Q: How do I delete bad recordings?

**A:** Two methods:

**Method 1: Review Mode (Recommended)**
1. Review Mode → File → Review All Sessions
2. Review session
3. Press Ctrl+D to delete
4. Confirm deletion
5. Next session loads automatically

**Method 2: Manual**
1. Navigate to `recordings/` folder
2. Find session folder (e.g., `session-2026-01-19_001`)
3. Delete entire folder
4. Restart PitchTracker if needed

---

## General Usage

### Q: What do the detection modes (MODE_A, MODE_B, MODE_C) mean?

**A:** Different detection strategies:
- **MODE_A (Default):** Frame differencing - detects moving objects
- **MODE_B:** Background subtraction - learns background, detects foreground
- **MODE_C:** Hybrid - combines both methods

**When to change:**
- MODE_A works well for most cases
- MODE_B better for static backgrounds
- MODE_C best for difficult lighting

**How to change:** Review Mode → Parameters → Detection Mode

### Q: How do I know if detection is working?

**A:** During capture:
- Green circles appear on moving ball
- Detection count updates in status bar
- No errors in message area

During Review Mode:
- Green circles show detections
- Adjust parameters to improve detection
- Orange X marks manual corrections

### Q: What is "pre-roll" and why is it needed?

**A:** Pre-roll captures frames BEFORE pitch detection starts:
- Default: 300ms before first detection
- Ensures we capture release point
- Critical for accurate trajectory calculation
- Can't be recovered if not captured

**Setting:** configs/default.yaml → pitch_tracking → pre_roll_ms

### Q: Can I use PitchTracker for softball?

**A:** Yes! Calibration and detection work the same. Adjust:
- Batter height (Settings → Strike Zone)
- Expected speed range (affects some algorithms)
- Camera positioning for underhand delivery

### Q: Does PitchTracker work indoors and outdoors?

**A:**
- **Indoors:** Excellent - consistent lighting, minimal background motion
- **Outdoors:** Good with caveats:
  - Avoid direct sunlight (causes glare, shadows)
  - Wind-blown objects cause false detections
  - Birds, cars in background can trigger detection
  - Cloudy days work best

### Q: How accurate is the speed measurement?

**A:** Accuracy depends on:
- **Calibration quality:** Most important factor
- **Detection consistency:** More detections = better measurement
- **Camera framerate:** 60 FPS better than 30 FPS
- **Camera distance:** 6-8 feet apart is optimal

**Expected accuracy:** ±1-2 MPH with good calibration and detection

### Q: Can I customize the strike zone?

**A:** Yes:
1. Settings → Strike Zone
2. Adjust batter height
3. Zone automatically scales based on MLB rules
4. Custom zones: Edit configs/default.yaml

### Q: How do I report bugs or request features?

**A:**
1. **GitHub Issues:** https://github.com/anthropics/claude-code/issues
2. Include:
   - PitchTracker version (Help → About)
   - Windows version
   - Steps to reproduce
   - Screenshots if relevant
   - Log files (logs/ folder)

### Q: Are there any privacy concerns with the cameras?

**A:** PitchTracker:
- Only accesses cameras when you start capture
- Only saves recordings when you start recording
- No data sent to external servers
- All data stored locally on your computer
- You control all recordings and can delete anytime

---

## Still Have Questions?

- Check `TROUBLESHOOTING.md` for specific error messages
- See `docs/` folder for technical documentation
- Report issues on GitHub with logs from `logs/` folder

---

**Document Version:** 1.0
**Covers PitchTracker:** v1.0.0+
