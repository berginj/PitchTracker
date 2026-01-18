# PitchTracker - Troubleshooting Guide

**Last Updated:** 2026-01-18
**Version:** 1.2.0

---

## Table of Contents

- [Camera Issues](#camera-issues)
- [Performance Issues](#performance-issues)
- [Detection Issues](#detection-issues)
- [Recording Issues](#recording-issues)
- [Calibration Issues](#calibration-issues)
- [Installation Issues](#installation-issues)
- [Error Messages](#error-messages)
- [Advanced Troubleshooting](#advanced-troubleshooting)

---

## Camera Issues

### Problem: Cameras Not Detected

**Symptoms:**
- "No cameras found" message
- Camera list is empty
- Cameras show in device manager but not in app

**Solutions:**

**Step 1: Verify Camera Hardware**
```
1. Open Windows Device Manager (Win + X → Device Manager)
2. Expand "Cameras" or "Imaging Devices"
3. Verify cameras are listed and no yellow warning icons
4. If warning icon, right-click → Update Driver
```

**Step 2: Check Camera Backend**
```
1. Settings → Camera → Backend
2. Try each backend option:
   - UVC (Universal Video Class)
   - DirectShow (Windows default)
   - OpenCV (Cross-platform)
3. Click "Refresh Cameras" after each change
```

**Step 3: Close Conflicting Applications**
```
1. Close all video apps (Zoom, Skype, Teams, OBS, etc.)
2. Check Task Manager for hidden processes
3. Restart PitchTracker
```

**Step 4: Windows Camera Permissions**
```
1. Windows Settings → Privacy → Camera
2. Enable "Allow apps to access your camera"
3. Scroll down to PitchTracker, enable permission
4. Restart application
```

**Step 5: Reinstall Camera Drivers**
```
1. Device Manager → Cameras → Right-click camera
2. Uninstall Device (check "Delete driver software")
3. Restart computer
4. Windows will reinstall drivers automatically
```

**Still not working?**
- Try camera on another computer to verify hardware works
- Check manufacturer's website for updated drivers
- Some cameras require proprietary software installed first

---

### Problem: Camera Preview is Black

**Symptoms:**
- Camera detected but shows black screen
- Preview was working, now black
- One camera works, other doesn't

**Solutions:**

**Quick Fixes:**
```
1. Unplug and replug camera USB
2. Try different USB port (especially USB 3.0)
3. Restart application
4. Restart computer
```

**Camera Settings:**
```
1. Settings → Camera → Exposure
2. Try "Auto" exposure mode first
3. If manual, increase exposure value
4. Increase Gain setting if image too dark
```

**USB Power Issues:**
```
1. Don't use USB hubs (connect directly to PC)
2. Try different USB port
3. Use powered USB hub if needed
4. Check USB cable quality
```

**Camera Busy:**
```
1. Task Manager → End process for other video apps
2. Check for webcam surveillance software
3. Reboot if process can't be ended
```

**Driver/Firmware:**
```
1. Update camera firmware (check manufacturer site)
2. Reinstall camera drivers
3. Try camera with manufacturer's software to verify
```

---

### Problem: One Camera Works, Other Doesn't

**Symptoms:**
- Left camera OK, right camera fails (or vice versa)
- Cameras work individually but not together
- Intermittent connection

**Solutions:**

**USB Controller Check:**
```
1. Connect cameras to different USB controllers
   - Check Device Manager → USB controllers
   - Spread cameras across USB 2.0 and USB 3.0
2. Avoid using two cameras on same USB hub
3. High-bandwidth cameras need dedicated controllers
```

**Power Management:**
```
1. Device Manager → USB Root Hub → Properties
2. Power Management tab
3. Uncheck "Allow computer to turn off this device"
4. Repeat for all USB Root Hubs
5. Restart computer
```

**Camera Mismatch:**
```
1. Verify both cameras are same model
2. Check firmware versions match
3. Use identical camera settings (resolution, FPS)
```

**Timing Issues:**
```
1. Settings → Camera → Backend → Try different backend
2. Enable "Sync Mode" if available
3. Reduce FPS (60 → 30) to reduce USB bandwidth
```

---

## Performance Issues

### Problem: Low Frame Rate / Choppy Video

**Symptoms:**
- FPS counter shows <20 FPS
- Video stutters or lags
- CPU usage >80%
- "Dropping frames" warnings

**Solutions:**

**Reduce Camera Settings:**
```
Settings → Camera:
1. Resolution: 1920×1080 → 1280×720
2. FPS: 60 → 30
3. Exposure: Manual (prevents auto-exposure lag)
4. Disable auto-focus if available
```

**Optimize Detection:**
```
Settings → Detection:
1. Mode: ML → Classical (much faster)
2. Frame Skip: Process every 2nd or 3rd frame
3. ROI: Draw smaller region (less pixels to process)
```

**Close Background Apps:**
```
1. Close browser tabs (especially video/streaming)
2. Close Discord, Slack, etc.
3. Disable antivirus real-time scanning temporarily
4. Check Task Manager for CPU hogs
```

**Windows Optimization:**
```
1. Power Plan: High Performance
   - Control Panel → Power Options
2. Disable Windows Search indexing temporarily
3. Disable Windows Update during recording
4. Close notification center
```

**Hardware Check:**
```
1. CPU temperature (use HWMonitor)
   - If >80°C, check cooling
2. RAM usage (should have 4GB+ free)
3. Disk space (SSD faster than HDD)
```

**Advanced:**
```
1. Update graphics drivers
2. Disable Windows visual effects
3. Set PitchTracker to "High Priority":
   - Task Manager → Details → Right-click PitchTracker
   - Set priority → High
```

---

### Problem: App Freezes or Hangs

**Symptoms:**
- App stops responding
- White screen/"Not Responding"
- Must force close

**Solutions:**

**Immediate:**
```
1. Wait 30 seconds (may be processing)
2. Task Manager → End Task
3. Restart application
4. Check if session data saved (may be partial)
```

**Prevent Future Freezes:**
```
1. Update to latest version
2. Check disk space (>10GB free)
3. Reduce resolution/FPS
4. Don't minimize during processing
```

**Long Processing:**
```
If freeze during:
- Calibration: Expected for 20-30 images
- Export: Large sessions take time
- Session load: Many pitches = slower load
```

**Check Logs:**
```
Location: C:\Users\<user>\AppData\Local\PitchTracker\logs\
Look for:
- Exceptions or errors before freeze
- "Out of memory" messages
- Disk write errors
```

---

## Detection Issues

### Problem: No Pitches Detected

**Symptoms:**
- Ball visible in camera but not detected
- Detection count stays at 0
- No trajectory shown

**Solutions:**

**Check Region of Interest (ROI):**
```
1. Setup → Draw ROI
2. Ensure ROI covers entire strike zone
3. ROI should include ball flight path
4. Draw new ROI if needed
```

**Detection Settings:**
```
Settings → Detection:
1. Threshold: Lower value (more sensitive)
   - Try 0.3-0.5 for testing
2. Min Area: Reduce (default 10)
3. Max Area: Increase if ball appears large
4. Mode: Try switching Classical ↔ ML
```

**Ball Visibility:**
```
1. Verify ball is bright/contrasting color
2. Check lighting (avoid shadows)
3. Ball must be in focus
4. Check camera exposure settings
```

**HSV Color Range:**
```
For white ball detection:
Settings → Detection → HSV Range:
- Lower: [0, 0, 200]
- Upper: [180, 30, 255]

For yellow ball:
- Lower: [20, 100, 100]
- Upper: [30, 255, 255]
```

**Test Detection:**
```
1. Tools → Test Detection Mode
2. Move ball slowly through strike zone
3. Verify detection boxes appear
4. Adjust settings until detection reliable
```

---

### Problem: Too Many False Detections

**Symptoms:**
- Detecting background objects
- False pitches recorded
- Detection count artificially high

**Solutions:**

**Tighten ROI:**
```
1. Setup → Draw ROI
2. Draw smallest possible region
3. Only include strike zone area
4. Exclude background movement
```

**Increase Threshold:**
```
Settings → Detection → Threshold:
- Increase from 0.5 → 0.7
- Higher = fewer false positives
- May miss some real pitches
```

**Filter Settings:**
```
Settings → Detection → Filters:
1. Min Velocity: Set minimum (e.g., 20 mph)
2. Max Velocity: Set maximum (e.g., 100 mph)
3. Min Circularity: Increase (more round = more ball-like)
```

**Background Issues:**
```
1. Use static backdrop behind strike zone
2. Avoid trees, flags, people in background
3. Cover reflective surfaces
4. Reduce lighting variations
```

---

## Recording Issues

### Problem: Recording Stops Unexpectedly

**Symptoms:**
- Recording auto-stops without user action
- "Recording stopped" message
- Short sessions when expecting longer

**Possible Causes & Solutions:**

**Disk Space (Most Common):**
```
Check: Bottom-left corner shows free space

If <5GB:
1. Free up disk space immediately
2. Settings → Recording → Output Directory
3. Change to drive with more space
4. Empty Recycle Bin
```

**Camera Disconnection:**
```
1. Check USB connections
2. Error log shows camera errors
3. Use quality USB cables
4. Avoid USB hubs
```

**Errors During Recording:**
```
Check error notifications (bell icon):
- Detection errors (pipeline continues)
- Camera errors (may stop)
- Disk write errors (stops immediately)
```

**Timeout/Inactivity:**
```
Settings → Recording:
- Check "Auto-stop after X minutes inactivity"
- Disable or increase timeout
```

---

### Problem: Video Files Corrupted

**Symptoms:**
- Can't play video files
- Video stops mid-file
- "Codec not found" errors

**Solutions:**

**Immediate:**
```
1. Try playing with VLC Media Player (supports more formats)
2. Check file size (should be >1KB, typically MB-GB)
3. Check if manifest.json exists (partial saves)
```

**Codec Issues:**
```
App tries codecs in order: MJPG → XVID → H264 → MP4V
Install codec pack:
- K-Lite Codec Pack (Windows)
- Or use VLC (includes all codecs)
```

**Prevent Corruption:**
```
1. Don't force-close app during recording
2. Ensure sufficient disk space
3. Use SSD instead of external HDD if possible
4. Don't unplug USB during recording
```

**Recovery:**
```
If video corrupted but session exists:
1. Check for backup in session folder
2. Use video repair tools (e.g., VLC repair)
3. At minimum, manifest.json has pitch data
```

---

## Calibration Issues

### Problem: Calibration Fails

**Symptoms:**
- "Calibration failed" error
- RMS error too high
- Can't complete calibration wizard

**Solutions:**

**Checkerboard Pattern:**
```
Requirements:
1. Print on flat, rigid surface (not paper)
2. Pattern must be perfectly flat (no warping)
3. Good lighting (no glare on pattern)
4. All corners visible in frame
5. Pattern fills 30-70% of frame
```

**Image Quality:**
```
1. Focus cameras properly
2. Avoid motion blur (hold pattern steady)
3. Capture from various angles:
   - Center
   - Corners
   - Rotated
   - Different distances
4. Need 20-30 good images per camera
```

**Common Mistakes:**
```
✗ Pattern too close/too far
✗ Pattern at same angle every time
✗ Poor lighting
✗ Out of focus
✗ Too few images (<15)
✗ Pattern partially out of frame
```

**If Still Failing:**
```
1. Delete partial calibration
2. Start fresh calibration
3. Use different checkerboard size
4. Try different camera backend
5. Ensure cameras fixed in position (not moving)
```

---

### Problem: 3D Tracking Inaccurate

**Symptoms:**
- Trajectory looks wrong
- Strike zone position off
- Velocity wildly inaccurate

**Solutions:**

**Recalibrate:**
```
Most common issue is calibration drift:
1. Redo extrinsic calibration
2. Verify camera positions haven't moved
3. Check camera-to-mound distance measurement
```

**Verify Physical Setup:**
```
1. Measure exact camera separation distance
2. Cameras must be level (use level tool)
3. Cameras converging on strike zone
4. No camera shake/vibration
```

**Strike Zone:**
```
Settings → Strike Zone:
1. Verify batter height correct
2. Check plate position coordinates
3. Top/bottom ratios (typically 0.56/0.28)
4. Plate width (17 inches = 0.43m)
```

**Check Stereo Matching:**
```
Tools → View Stereo Matches:
- Should see corresponding points on left/right
- If no matches, check:
  - ROI overlaps strike zone
  - Both cameras see the ball
  - Cameras properly calibrated
```

---

## Installation Issues

### Problem: Installer Won't Run

**Symptoms:**
- Double-click does nothing
- "Windows protected your PC" message
- Installer crashes immediately

**Solutions:**

**Windows SmartScreen:**
```
If "Windows protected your PC" appears:
1. Click "More info"
2. Click "Run anyway"
3. (App not yet code-signed, safe to run)
```

**Run as Administrator:**
```
1. Right-click installer
2. "Run as administrator"
3. Accept UAC prompt
```

**Antivirus Blocking:**
```
1. Temporarily disable antivirus
2. Run installer
3. Re-enable antivirus
4. Add PitchTracker to exclusions
```

**Corrupted Download:**
```
1. Delete downloaded installer
2. Clear browser cache
3. Re-download from GitHub Releases
4. Verify file size matches (should be 50-100MB)
```

---

### Problem: Missing Dependencies

**Symptoms:**
- "VCRUNTIME140.dll missing" error
- ".NET Framework" error
- App won't start after install

**Solutions:**

**Visual C++ Redistributable:**
```
Download and install:
- Microsoft Visual C++ 2015-2022 Redistributable (x64)
- Link: https://aka.ms/vs/17/release/vc_redist.x64.exe
```

**.NET Framework:**
```
Download and install:
- .NET Framework 4.8 or later
- Usually included in Windows 10/11
- Windows Update should install automatically
```

**Verify Installation:**
```
1. Control Panel → Programs and Features
2. Look for:
   - Microsoft Visual C++ 2015-2022 Redistributable
   - Microsoft .NET Framework 4.8
3. If missing, download and install from Microsoft
```

---

## Error Messages

### "Camera connection error"

**Meaning:** Can't access camera hardware

**Check:**
1. Camera plugged in?
2. Other apps using camera?
3. Windows camera permissions enabled?
4. Try different USB port

---

### "Detection failed for left/right camera"

**Meaning:** Detection pipeline error (non-critical)

**Action:**
- Pipeline continues operating
- Check error details in error log
- May be temporary glitch
- If persistent (10+ errors), check detection settings

---

### "Critical disk space: X.XGB remaining"

**Meaning:** Disk space below 5GB threshold

**Action:**
- Recording auto-stopped
- Free up disk space immediately
- Change output directory to different drive
- Archive/delete old sessions

---

### "All video codecs failed"

**Meaning:** Can't initialize video recording

**Action:**
1. Install K-Lite Codec Pack
2. Update graphics drivers
3. Try different camera resolution
4. Check Windows Updates

---

### "Calibration RMS error too high"

**Meaning:** Calibration quality insufficient

**Action:**
- Capture more images (20-30)
- Vary pattern positions/angles
- Ensure pattern is flat
- Check focus and lighting
- Start fresh calibration

---

## Advanced Troubleshooting

### Check Application Logs

**Location:**
```
C:\Users\<username>\AppData\Local\PitchTracker\logs\
```

**Files:**
- `pitchtracker.log` - Main application log
- `error.log` - Error-only log
- `camera.log` - Camera subsystem
- `detection.log` - Detection subsystem

**What to look for:**
```
ERROR   - Actual errors
WARNING - Potential issues
CRITICAL - Severe problems
```

### Performance Profiling

**Built-in Tools:**
```
1. Tools → Performance Monitor
2. Shows real-time:
   - FPS
   - CPU usage
   - Memory usage
   - Frame drop count
   - Detection latency
```

**Windows Task Manager:**
```
1. Open Task Manager (Ctrl+Shift+Esc)
2. More Details → Performance tab
3. Monitor while running:
   - CPU (should be <80%)
   - Memory (should have 4GB+ free)
   - Disk (should not be at 100%)
   - GPU (if using ML detector)
```

### Reset to Defaults

**Reset Settings:**
```
1. Settings → Advanced → Reset to Defaults
2. Or delete config file:
   C:\Users\<username>\AppData\Roaming\PitchTracker\config.yaml
3. Restart application
```

**Full Reinstall:**
```
1. Uninstall PitchTracker
2. Delete folders:
   - C:\Program Files\PitchTracker\
   - C:\Users\<username>\AppData\Roaming\PitchTracker\
   - (Keep \Documents\PitchTracker\ if you want sessions)
3. Restart computer
4. Reinstall latest version
```

### Enable Debug Mode

**For detailed diagnostics:**
```
1. Settings → Advanced → Debug Mode → Enable
2. Restart application
3. Reproduce issue
4. Check logs for detailed output
5. Disable debug mode when done (impacts performance)
```

### Network/Firewall Issues

**If using cloud features:**
```
1. Firewall: Allow PitchTracker
   - Windows Defender Firewall → Allow an app
2. Antivirus: Add to exclusions
3. Check proxy settings if on corporate network
```

---

## Still Need Help?

### Before Contacting Support

Collect this information:
1. PitchTracker version (Help → About)
2. Windows version (Settings → System → About)
3. Camera models
4. Error logs (zip logs folder)
5. Screenshots of error messages
6. Steps to reproduce issue

### Contact Options

- **GitHub Issues:** [Report Bug](https://github.com/yourorg/pitchtracker/issues)
- **Email:** support@pitchtracker.example.com
- **Forum:** forum.pitchtracker.example.com
- **Discord:** discord.gg/pitchtracker

### Include in Bug Report

```
**Environment:**
- OS: Windows 10/11 version XXXX
- PitchTracker Version: 1.2.0
- Cameras: [Model names]
- CPU/RAM: [Specs]

**Issue:**
[Describe problem]

**Steps to Reproduce:**
1. [Step 1]
2. [Step 2]
3. [Error occurs]

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Logs:**
[Attach relevant log sections]

**Screenshots:**
[If applicable]
```

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**For Version:** PitchTracker 1.2.0

