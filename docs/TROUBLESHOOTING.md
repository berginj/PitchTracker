# PitchTracker - Troubleshooting Guide

**Last Updated:** 2026-01-19
**Version:** 2.0

This guide covers common issues, error messages, and solutions.

---

## Table of Contents

- [Camera Issues](#camera-issues)
- [Performance Issues](#performance-issues)
- [Recording Issues](#recording-issues)
- [Calibration Issues](#calibration-issues)
- [Installation Issues](#installation-issues)
- [Error Messages](#error-messages)
- [Advanced Troubleshooting](#advanced-troubleshooting)

---

## Camera Issues

### Camera Not Detected

**Symptom:** Camera doesn't appear in camera selection list

**Solutions:**

1. **Check USB Connection**
   ```
   - Use USB 3.0 ports (blue colored)
   - Try different USB port
   - Connect directly to motherboard (not USB hub)
   - Use cable < 3 feet long
   ```

2. **Restart Camera Detection**
   - Close PitchTracker
   - Unplug both cameras
   - Wait 10 seconds
   - Plug cameras back in
   - Launch PitchTracker
   - Click "Refresh" in camera selection

3. **Check Windows Device Manager**
   - Open Device Manager
   - Expand "Imaging devices" or "Cameras"
   - Look for your cameras
   - If yellow warning icon: Update driver
   - If missing: Camera may be faulty

4. **Verify Camera Works Elsewhere**
   - Open Windows Camera app
   - If camera doesn't work: Windows/driver issue
   - If camera works: May be camera permissions

5. **Check Windows Privacy Settings**
   ```
   Settings → Privacy → Camera
   - Enable "Let apps access your camera"
   - Scroll down and enable for Desktop apps
   ```

### Camera Disconnects During Use

**Symptom:** "Camera disconnected" error during recording

**Solutions:**

1. **USB Power Issues**
   - Connect cameras to separate USB controllers
   - Don't use USB hubs (they share power)
   - Try powered USB hub if needed
   - Check camera power requirements

2. **USB Cable Quality**
   - Use USB 3.0 certified cables
   - Replace old/damaged cables
   - Keep cables < 3 feet for best results
   - Secure connections (not loose)

3. **Driver Issues**
   - Update camera drivers in Device Manager
   - Update USB controller drivers
   - Update chipset drivers from motherboard manufacturer

4. **Auto-Reconnection**
   - PitchTracker will try to reconnect automatically
   - Watch status bar for reconnection updates
   - If reconnection fails, restart PitchTracker

### Poor Image Quality

**Symptom:** Blurry, dark, or noisy video

**Solutions:**

1. **Focus Issues**
   - Manual focus cameras: Adjust focus ring
   - Auto-focus cameras: Point at ball zone, let camera focus
   - Clean camera lens

2. **Lighting Issues**
   - Ensure adequate lighting on strike zone
   - Avoid backlighting (bright background, dark subject)
   - Avoid direct sunlight (causes glare)
   - Indirect/diffuse lighting works best

3. **Camera Settings**
   - Settings → Camera → Exposure
   - Auto exposure usually works
   - Manual: Increase exposure if too dark
   - Decrease exposure if washed out

4. **Motion Blur**
   - Increase shutter speed if supported
   - Use 60 FPS instead of 30 FPS
   - Improve lighting (allows faster shutter)

---

## Performance Issues

### Slow Frame Rate / Choppy Video

**Symptom:** Video playback is laggy or stuttering

**Solutions:**

1. **Lower Resolution/Framerate**
   ```
   Settings → Camera:
   - Try 1280x720 @ 30fps (instead of 60fps)
   - Try 640x480 @ 30fps (for older systems)
   ```

2. **Close Other Applications**
   - Close web browsers
   - Close video players
   - Close other camera software (OBS, Zoom, Teams)
   - Check Task Manager for CPU hogs

3. **CPU Usage High**
   - Normal: 40-60% during capture
   - High (>80%): Lower camera settings
   - Background indexing: Disable for recordings folder

4. **Detection Dropping Frames**
   - Status bar shows "Dropping frames" warning
   - Lower resolution or framerate
   - Disable color mode: Settings → Camera → Color Mode: Off
   - Close detection-heavy modes

### High Memory Usage

**Symptom:** Memory usage grows over time, system slows down

**Solutions:**

1. **Check Queue Settings**
   - High queue size = more memory
   - Settings → Detection → Queue Size
   - Default (6) is usually optimal
   - Lower if memory constrained

2. **Restart Application**
   - If memory >2GB after hours of use
   - Close and relaunch PitchTracker
   - Memory resets to ~200-400MB

3. **Check for Memory Leaks**
   - If memory grows continuously (>100MB/hour)
   - Report bug with reproduction steps
   - Include logs from logs/ folder

### Disk Running Out of Space

**Symptom:** "Low disk space" warning during recording

**Solutions:**

1. **Immediate Actions**
   - End current recording session
   - Don't start new sessions until space freed

2. **Free Up Space**
   ```
   - Delete old PitchTracker recordings (recordings/ folder)
   - Use Review Mode to identify bad sessions first
   - Empty Windows Recycle Bin
   - Run Disk Cleanup (Windows tool)
   ```

3. **Change Recording Location**
   - Settings → Recording → Output Directory
   - Choose drive with more space
   - Need 50GB+ free minimum

4. **Long-term Solutions**
   - Add larger hard drive
   - Move old recordings to external drive
   - Archive recordings to cloud storage
   - Delete sessions after analysis

---

## Recording Issues

### Recording Won't Start

**Symptom:** "Start Recording" fails with error

**Possible Causes & Solutions:**

1. **Capture Not Started**
   - Error: "Cannot record without active capture"
   - Solution: Start capture before recording

2. **Insufficient Disk Space**
   - Error: "Low disk space: XX.X GB available"
   - Solution: Free up 50GB+ before recording

3. **Previous Recording Not Stopped**
   - Error: "Recording already in progress"
   - Solution: Stop current recording first

4. **Output Directory Missing**
   - Error: "Recording directory not found"
   - Solution: Check Settings → Recording → Output Directory exists

### Video Files Corrupted

**Symptom:** Video files won't open or play incorrectly

**Solutions:**

1. **Check Disk Space**
   - Recording stopped due to low disk space
   - Partial files may be corrupted
   - Always keep 50GB+ free

2. **Check Codec Support**
   - Videos use MJPG, XVID, H264, or MP4V codec
   - Install VLC Media Player (supports all)
   - Windows Media Player may not support all codecs

3. **Verify File Size**
   - Video files should be > 1MB
   - 0 byte files = recording failed immediately
   - Check logs for error during recording

4. **Recovery (if possible)**
   - Try opening with VLC Media Player
   - Use video repair tools (search "repair AVI file")
   - If corrupted: Delete and re-record

### Recording Stops Automatically

**Symptom:** Recording ends without user action

**Causes:**

1. **Disk Space Critical (< 5GB)**
   - Auto-stop prevents data corruption
   - Warning shown in status bar
   - Free up space before restarting

2. **Camera Disconnected**
   - Recording can't continue without cameras
   - Check USB connections
   - Try auto-reconnection

3. **Internal Error**
   - Check logs/ folder for error messages
   - Report bug if recurring

---

## Calibration Issues

### Checkerboard Not Detected

**Symptom:** "No corners detected" when capturing calibration images

**Solutions:**

1. **Print Quality**
   - Print on rigid surface (cardboard, foam board)
   - Not on paper (bends/curves)
   - High contrast (pure black and white)
   - Sharp edges, no blur

2. **Lighting**
   - Even, diffuse lighting
   - No glare or reflections
   - No shadows across pattern
   - Matte finish (not glossy)

3. **Camera Position**
   - Entire pattern must be visible
   - Pattern should fill 50-75% of frame
   - Not too close (pattern fills screen)
   - Not too far (pattern too small)

4. **Hold Steady**
   - Keep pattern completely still
   - Wait 1-2 seconds before capture
   - Use tripod or place on surface if possible

### High Reprojection Error

**Symptom:** Calibration completes but reports high reprojection error (>2.0 pixels)

**Solutions:**

1. **Take More Images**
   - Need 20+ images minimum
   - 30-40 images recommended
   - More images = better calibration

2. **Cover Full FOV**
   - Take images from all areas of frame
   - Center, corners, edges
   - Close-up and far away
   - Various angles (not just straight-on)

3. **Verify Pattern Quality**
   - Pattern must be perfectly flat
   - No bending, warping, or distortion
   - Check all corners are sharp

4. **Camera Stability**
   - Cameras must not move during calibration
   - Secure camera mounts
   - Don't bump cameras between captures

### Stereo Calibration Fails

**Symptom:** "Stereo calibration failed" after intrinsic calibration succeeds

**Solutions:**

1. **Check Camera Distance**
   - Measure from lens center to lens center
   - Be precise (±0.5 inch accuracy)
   - Re-measure and enter correct distance

2. **Overlapping Field of View**
   - Cameras must see same area
   - Hold pattern where both cameras see it
   - Angle cameras slightly inward if needed

3. **Parallel Alignment**
   - Cameras should be roughly parallel
   - Not angled away from each other
   - Use level or alignment tools

4. **Re-do Intrinsic Calibration**
   - If stereo consistently fails
   - Redo intrinsic for both cameras
   - Ensure high quality images

---

## Installation Issues

### Installer Won't Run

**Symptom:** Double-clicking installer does nothing or shows error

**Solutions:**

1. **Windows SmartScreen**
   - "Windows protected your PC" message
   - Click "More info"
   - Click "Run anyway"
   - This is expected for unsigned software

2. **Antivirus Blocking**
   - Temporarily disable antivirus
   - Run installer
   - Re-enable antivirus
   - Add PitchTracker to whitelist if needed

3. **Corrupted Download**
   - Re-download installer
   - Verify file size matches release page
   - Try different browser

4. **Administrator Rights**
   - Right-click installer
   - "Run as administrator"

### Missing DLL Errors

**Symptom:** "VCRUNTIME140.dll not found" or similar errors

**Solutions:**

1. **Install Visual C++ Redistributable**
   - Download from Microsoft:
     https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Run installer
   - Restart computer
   - Launch PitchTracker

2. **Update Windows**
   - Settings → Update & Security
   - Check for updates
   - Install all updates
   - Restart

### Application Won't Start After Installation

**Symptom:** PitchTracker crashes immediately or shows blank window

**Solutions:**

1. **Check Event Viewer**
   ```
   - Open Event Viewer
   - Windows Logs → Application
   - Look for PitchTracker errors
   - Note error message/code
   ```

2. **Try Safe Mode**
   - Launch with --safe flag
   - Disables hardware acceleration
   - Use if graphics driver issues

3. **Graphics Drivers**
   - Update graphics card drivers
   - From manufacturer (NVIDIA, AMD, Intel)
   - Not Windows generic drivers

4. **Clean Reinstall**
   - Uninstall PitchTracker
   - Delete %APPDATA%\PitchTracker
   - Restart computer
   - Reinstall

---

## Error Messages

### "Detection queue 'left' full, dropping frames"

**Meaning:** Detection can't keep up with camera frame rate

**Impact:** Some frames not analyzed, but recording continues

**Solutions:**
- Lower resolution: 1280x720 or 640x480
- Lower framerate: 30fps instead of 60fps
- Close other applications
- If persistent: Detection may be broken (check logs)

### "Critical disk space: X.X GB remaining"

**Meaning:** Disk almost full, recording will stop

**Impact:** Recording auto-stops to prevent data corruption

**Solutions:**
- Immediately stop recording
- Free up disk space (>50GB)
- Delete old recordings
- Change output directory to larger drive

### "Camera X: Frame read failed"

**Meaning:** Camera communication error

**Impact:** Temporary - if recovers, no action needed. If persistent, recording may stop.

**Solutions:**
- Check USB connection
- Replace USB cable
- Try different USB port
- Update camera drivers

### "Detection failed for X camera"

**Meaning:** Detection algorithm threw exception

**Impact:** Detection temporarily disabled for that camera

**Solutions:**
- Check logs for detailed error
- If recovers automatically: Temporary glitch
- If persistent: Report bug with logs

### "All video codecs failed for session_X.avi"

**Meaning:** Cannot create video file with any codec

**Impact:** Recording fails, no video saved

**Solutions:**
- Install codec pack (K-Lite Codec Pack)
- Update graphics drivers
- Check disk is not read-only
- Ensure sufficient disk space
- Try different output directory

### "Pitch X rejected: Too few observations"

**Meaning:** Pitch detection quality too low for reliable data

**Impact:** Pitch not saved to session

**Solutions:**
- Check detection parameters (Review Mode)
- Improve lighting
- Ensure cameras see ball trajectory
- Check calibration quality

---

## Advanced Troubleshooting

### Enable Debug Logging

1. Edit `configs/default.yaml`
2. Find logging section
3. Change `level: INFO` to `level: DEBUG`
4. Restart PitchTracker
5. Check `logs/` folder for detailed logs

### Check System Resources

Open Task Manager (Ctrl+Shift+Esc):
- **CPU:** Should be 40-60% during capture
- **Memory:** Should be 200-800MB typical, <2GB max
- **Disk:** Write speed should be >50 MB/s
- **USB:** Check USB controller not overloaded

### Test with Simulated Cameras

Launch PitchTracker in simulation mode:
```bash
PitchTracker.exe --backend sim
```
- Uses fake cameras with test patterns
- Helps isolate camera vs software issues
- If works in sim: Hardware/camera problem
- If fails in sim: Software issue

### Examine Log Files

Location: `logs/pitchtracker.log`

Look for:
- **ERROR** or **CRITICAL** messages
- Exception tracebacks (starts with "Traceback")
- Repeated warnings (indicates ongoing issue)
- Timestamps of when problems occur

Include logs when reporting bugs.

### Configuration Reset

If settings corrupted or want to start fresh:

1. Close PitchTracker
2. Delete config files:
   ```
   - %APPDATA%\PitchTracker\settings.json
   - %APPDATA%\PitchTracker\state.json
   ```
3. Restart PitchTracker
4. Run Setup Wizard again

### Performance Profiling

If PitchTracker is slow:

1. Check CPU usage per process (Task Manager → Details)
2. Look for:
   - PitchTracker.exe using >80% CPU: Expected during capture
   - Other processes using high CPU: Close them
   - Antivirus scanning: Exclude recordings/ folder

### Network/Firewall Issues

PitchTracker only needs network for:
- Update checks (optional)
- Downloading updates (optional)

If blocked:
- Updates won't work (download manually instead)
- All core functionality works offline

---

## Getting Help

If you still have issues after trying these solutions:

1. **Gather Information:**
   - PitchTracker version (Help → About)
   - Windows version
   - Camera models
   - Exact error message
   - Log files from logs/ folder

2. **Report Issue:**
   - GitHub: https://github.com/anthropics/claude-code/issues
   - Include all gathered information
   - Steps to reproduce problem

3. **Community:**
   - Check existing GitHub issues
   - Others may have same problem
   - Solutions may be posted

---

**Document Version:** 1.0
**Last Updated:** 2026-01-19
