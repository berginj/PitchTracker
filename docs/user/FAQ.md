# PitchTracker - Frequently Asked Questions

**Last Updated:** 2026-01-18
**Version:** 1.2.0

---

## Table of Contents

- [Getting Started](#getting-started)
- [Camera Setup](#camera-setup)
- [Calibration](#calibration)
- [Recording](#recording)
- [Performance](#performance)
- [Data Export](#data-export)
- [Troubleshooting](#troubleshooting)
- [Updates](#updates)

---

## Getting Started

### Q: What is PitchTracker?

**A:** PitchTracker is a baseball pitch tracking application that uses stereo cameras to capture 3D trajectory data. It provides:
- Real-time pitch detection and tracking
- Strike zone visualization
- Pitch metrics (speed, location, movement)
- Session recording and analysis
- ML training data export

### Q: What hardware do I need?

**A:** Minimum requirements:
- **Cameras:** 2x USB cameras (60 FPS recommended, 30 FPS minimum)
- **Computer:**
  - Windows 10/11 (version 1809 or later)
  - Intel i5 or equivalent (i7 recommended)
  - 8GB RAM minimum (16GB recommended)
  - 100GB free disk space for recordings
  - USB 3.0 ports (for 60 FPS cameras)
- **Mounting:** Camera mounts or tripods
- **Optional:** Calibration checkerboard pattern

### Q: How do I install PitchTracker?

**A:**
1. Download the latest installer from [GitHub Releases](https://github.com/yourorg/pitchtracker/releases)
2. Run the `.exe` installer
3. Follow the installation wizard
4. Launch from desktop shortcut or Start menu
5. Complete first-time setup wizard

### Q: Do I need Python or programming knowledge?

**A:** No. PitchTracker is a standalone desktop application. No programming required.

---

## Camera Setup

### Q: Why can't I see my cameras?

**A:** Common causes and solutions:

1. **Camera not connected:**
   - Check USB connections
   - Try different USB ports
   - Restart the application

2. **Wrong backend selected:**
   - Go to: Settings → Camera → Backend
   - Try switching between "UVC", "OpenCV", or "DirectShow"
   - Click "Refresh Cameras"

3. **Camera in use by another app:**
   - Close other applications (Zoom, Skype, etc.)
   - Restart Windows if needed

4. **Permissions issue:**
   - Windows Settings → Privacy → Camera
   - Ensure "Allow apps to access your camera" is ON
   - Ensure PitchTracker has camera permission

5. **Driver issue:**
   - Update camera drivers
   - Try manufacturer's software first to verify camera works

### Q: What cameras are recommended?

**A:** Best results with:
- **60 FPS cameras** for fast pitches (80+ mph)
- **720p resolution minimum** (1080p for better accuracy)
- **USB 3.0** for higher frame rates
- **Global shutter** preferred over rolling shutter
- **Manual exposure control** (to avoid flickering)

Popular models:
- Logitech C920/C922 (30-60 FPS, good for casual use)
- PlayStation Eye (75 FPS when modded)
- Industrial USB cameras (Basler, FLIR - best quality)

### Q: How far apart should cameras be?

**A:** Optimal setup:
- **6-8 feet apart** for standard baseball distances
- **Angled inward** toward strike zone (converging)
- **Same height** relative to ground
- **Same model cameras** for matching specs
- **50-60 feet** from pitcher's mound

### Q: Can I use webcams?

**A:** Yes, but with limitations:
- Most webcams limited to 30 FPS (may miss fast pitches)
- Lower resolution affects accuracy
- Sufficient for slower pitches (<60 mph) or practice

### Q: Why is my video choppy?

**A:** Performance issues - try these solutions:

1. **Reduce resolution:**
   - Settings → Camera → Resolution
   - Try 1280×720 instead of 1920×1080

2. **Lower frame rate:**
   - Settings → Camera → FPS
   - Try 30 FPS instead of 60 FPS

3. **Close other programs:**
   - Close browser tabs, video players, etc.
   - Disable antivirus real-time scanning temporarily

4. **USB issues:**
   - Use USB 3.0 ports (blue connectors)
   - Don't use USB hubs for high-speed cameras
   - Each camera on separate USB controller if possible

5. **Hardware upgrade:**
   - Upgrade to faster CPU
   - Add more RAM (16GB recommended)
   - Ensure adequate cooling

---

## Calibration

### Q: Do I need to calibrate?

**A:** Yes, calibration is required for:
- Accurate 3D tracking
- Strike zone positioning
- Velocity measurements
- Distance calculations

Without calibration, you'll only see 2D camera views.

### Q: How do I calibrate the cameras?

**A:** Follow the Calibration Wizard:

1. **Intrinsic Calibration** (camera parameters):
   - Tools → Calibration Wizard → Intrinsic
   - Print checkerboard pattern (provided in app)
   - Show pattern to each camera at various angles
   - Capture 20-30 images per camera
   - App calculates lens distortion and focal length

2. **Extrinsic Calibration** (camera positions):
   - Tools → Calibration Wizard → Extrinsic
   - Measure exact distance between cameras
   - Show pattern to both cameras simultaneously
   - App calculates relative camera positions

3. **Strike Zone Calibration**:
   - Tools → Setup → Strike Zone
   - Define plate position
   - Set batter height
   - Adjust strike zone bounds

Detailed guide: [CALIBRATION_TIPS.md](./CALIBRATION_TIPS.md)

### Q: How often should I recalibrate?

**A:** Recalibrate when:
- Moving cameras
- Changing camera angle
- Changing camera zoom/focus
- After camera firmware update
- If accuracy seems off

Tip: Save multiple calibration profiles for different setups.

### Q: Can I skip calibration for testing?

**A:** Yes, use **Simulated Mode**:
- Settings → Camera → Backend → "Simulated"
- Uses virtual cameras for testing UI/features
- No real tracking, just for learning the interface

---

## Recording

### Q: How do I start recording?

**A:**
1. Ensure cameras are calibrated
2. Click "Start Recording" button (red circle)
3. Throw pitches within camera view
4. Click "Stop Recording" when done
5. Review session in Session Manager

### Q: Why am I getting disk space warnings?

**A:** The app monitors disk space to prevent data corruption:

- **50GB warning:** Recommended minimum, shows message
- **20GB warning:** Low space, yellow warning icon
- **5GB critical:** Recording auto-stops, red alert

**Solutions:**
- Free up disk space (delete old files, empty recycle bin)
- Change recording directory to drive with more space:
  - Settings → Recording → Output Directory
- Archive old sessions to external drive

### Q: How much disk space do I need?

**A:** Storage estimates (per hour of recording):
- **30 FPS, 720p:** ~10-15 GB/hour
- **60 FPS, 1080p:** ~30-40 GB/hour
- **ML training data:** Add 20-30% for detections/metadata

**Recommendations:**
- Keep 100GB free for active recording
- Archive sessions after review
- Use external SSD for recordings if internal storage limited

### Q: Can I pause recording?

**A:** No, but you can:
- Stop current recording
- Start new recording (creates separate session)
- Use Session Manager to combine sessions later

### Q: Where are recordings saved?

**A:** Default location:
- Windows: `C:\Users\<username>\Documents\PitchTracker\Sessions\`
- Each session in dated subfolder: `session_20260118_143052_<name>/`

Change location:
- Settings → Recording → Output Directory

### Q: Why is the app detecting false pitches?

**A:** Common causes:

1. **Region of Interest (ROI) too large:**
   - Setup → Draw ROI
   - Draw tighter region around strike zone
   - Exclude background movement

2. **Detection sensitivity too high:**
   - Settings → Detection → Threshold
   - Increase threshold (fewer false positives)

3. **Background movement:**
   - Avoid busy backgrounds (people walking, trees)
   - Use static backdrop if possible
   - Adjust lighting to reduce shadows

4. **Ball color similar to background:**
   - Use contrasting ball color
   - Adjust HSV color range in settings

---

## Performance

### Q: What FPS should I use?

**A:** Depends on pitch speed:
- **30 FPS:** Sufficient for <60 mph (practice, youth)
- **60 FPS:** Recommended for 60-90 mph (high school, college)
- **90+ FPS:** Best for 90+ mph (pro, radar verification)

Higher FPS = more tracking points = better accuracy.

### Q: Why is detection slow?

**A:** Optimization tips:

1. **Check CPU usage:**
   - Task Manager → Performance
   - If >80%, reduce resolution or FPS

2. **Detection mode:**
   - Settings → Detection → Mode
   - Try "Classical" mode (faster than ML)
   - ML mode more accurate but slower

3. **ROI size:**
   - Smaller ROI = faster processing
   - Only include strike zone area

4. **Frame skip:**
   - Settings → Detection → Process Every Nth Frame
   - Skip frames if CPU struggling

### Q: Can I run this on a laptop?

**A:** Yes, but:
- **Gaming laptop:** Should work well
- **Ultrabook/Budget laptop:** May struggle with 60 FPS
- **Battery power:** Performance reduced, use AC power
- **Cooling:** Ensure good ventilation

Laptop tips:
- Use 30 FPS instead of 60 FPS
- Lower resolution (720p)
- Close background apps
- Use power plan: "High Performance"

---

## Data Export

### Q: How do I export session data?

**A:**
1. Session Manager → Select session
2. Click "Export"
3. Choose format:
   - **CSV:** Spreadsheet-compatible (Excel, Google Sheets)
   - **JSON:** Programming/analysis tools
   - **ML Training ZIP:** For machine learning

### Q: What data is exported?

**A:** Export includes:
- **Pitch metrics:** Speed, location, movement
- **Trajectory:** 3D coordinates over time
- **Strike zone:** Location relative to zone
- **Videos:** Left/right camera recordings
- **Metadata:** Session info, calibration, config
- **ML data:** (if enabled) Detections, observations, frames

### Q: Can I use the data in Excel?

**A:** Yes:
1. Export as CSV format
2. Open in Excel or Google Sheets
3. Data organized with headers
4. Each row = one pitch or observation

### Q: How do I share sessions with coaches?

**A:**
1. Export session as ZIP
2. Share ZIP file via email/cloud drive
3. Recipient opens with PitchTracker or extracts CSV

Or use cloud upload (if configured):
- Settings → Upload → Enable
- Automatic upload after sessions
- Share cloud link

---

## Troubleshooting

### Q: The app crashed, is my data lost?

**A:** Data is saved continuously:
- Videos flushed every few seconds
- Pitch data written immediately
- Check session folder for partial data
- Uncorrupted videos should be playable
- Manifests may be incomplete but data exists

### Q: Why is my strike zone inaccurate?

**A:** Check:
1. **Calibration:** Recalibrate cameras
2. **Plate position:** Verify physical measurements
3. **Batter height:** Update in Settings → Strike Zone
4. **Camera angle:** Cameras should converge on plate
5. **Distance:** Verify camera-to-mound distance

### Q: Can I use this indoors?

**A:** Yes, if you have:
- **Sufficient space:** 60+ feet from mound to cameras
- **Adequate lighting:** Bright, even lighting (avoid shadows)
- **High ceiling:** For pop-ups (if tracking those)
- **Static background:** Minimal movement behind strike zone

Indoor tips:
- Use bright white ball for contrast
- Add supplementary lighting
- Use backdrop behind strike zone

### Q: The app won't start

**A:** Try:
1. Restart computer
2. Run as Administrator (right-click → Run as Administrator)
3. Check Windows Event Viewer for errors
4. Reinstall application
5. Check antivirus hasn't quarantined files
6. Ensure .NET Framework installed (usually automatic)

### Q: I'm getting camera permission errors

**A:**
1. Windows Settings → Privacy → Camera
2. Enable "Allow apps to access your camera"
3. Scroll down, find PitchTracker, enable
4. Restart application

### Q: Where can I get help?

**A:**
- **Documentation:** Check docs/ folder or GitHub wiki
- **GitHub Issues:** Report bugs or request features
- **Email Support:** support@pitchtracker.example.com
- **Community Forum:** forum.pitchtracker.example.com
- **Discord:** discord.gg/pitchtracker

---

## Updates

### Q: How do I update the app?

**A:** Automatic updates:
- App checks for updates on startup
- Notification appears when update available
- Click "Download Update" button
- Installer downloads and runs automatically
- App restarts with new version

Manual update:
- Help → Check for Updates
- Or download latest from GitHub Releases

### Q: Will updates delete my data?

**A:** No:
- Sessions saved separately from app
- Calibration profiles preserved
- Settings migrated automatically
- Always backup important data before updating

### Q: What's new in version 1.2.0?

**A:** Major features:
- ML training data collection and export
- System hardening and error recovery
- Improved disk space monitoring
- Auto-update mechanism
- Performance optimizations

See CHANGELOG.md for full details.

### Q: Can I rollback to previous version?

**A:** Yes:
1. Uninstall current version
2. Download older version from GitHub Releases
3. Install older version
4. Settings/data should be compatible

Note: Downgrading may lose new features.

---

## Still Have Questions?

- **Troubleshooting Guide:** [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- **Calibration Guide:** [CALIBRATION_TIPS.md](./CALIBRATION_TIPS.md)
- **GitHub Issues:** [Report a Bug](https://github.com/yourorg/pitchtracker/issues)
- **Documentation:** Full docs in `docs/` folder

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**For Version:** PitchTracker 1.2.0

