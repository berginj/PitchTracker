# Pre-Field Test Checklist - 100 Pitch Recording Session

## CRITICAL Issues Found (Must Address Before Test)

### 🔴 Issue 1: No Disk Space Monitoring
**Severity: CRITICAL - Could lose all data silently**

**Problem:**
- No check before starting recording
- If disk fills during recording, `cv2.VideoWriter.write()` fails silently
- Results in corrupted video files with NO warning

**Impact:** You could record 80 pitches, disk fills, last 20 pitches corrupted with no alert

**Quick Fix Needed:**
```python
# Before starting session, add to session_recorder.py:
import shutil

def check_disk_space(output_dir: Path, required_gb: float = 50.0) -> bool:
    """Verify sufficient disk space before recording."""
    usage = shutil.disk_usage(output_dir)
    free_gb = usage.free / (1024**3)

    if free_gb < required_gb:
        raise RuntimeError(
            f"Insufficient disk space: {free_gb:.1f}GB free, need {required_gb}GB"
        )

    logger.info(f"Disk space check: {free_gb:.1f}GB available")
    return True
```

**Estimated:** 100 pitches with dual camera video ≈ 20-30GB (estimate 300MB per pitch)

---

### 🔴 Issue 2: VideoWriter Failures Are Silent
**Severity: HIGH - Corrupted videos with no indication**

**Problem:**
- `cv2.VideoWriter.write()` returns False on failure but this is ignored
- Failed writes produce corrupted partial videos
- No way to know which pitches are corrupted until later

**Quick Fix Needed:**
```python
# In session_recorder.py and pitch_recorder.py:
success_left = self._left_writer.write(image)
success_right = self._right_writer.write(image)

if not success_left or not success_right:
    failed_camera = "left" if not success_left else "right"
    logger.error(f"VideoWriter failed on {failed_camera} camera, frame {frame_index}")
    raise IOError(f"Video write failed: {failed_camera} camera")
```

---

### 🔴 Issue 3: Single Camera Failure Kills Entire Session
**Severity: HIGH - Lose all remaining pitches**

**Problem:**
- If one camera fails mid-session, entire capture stops
- Can't continue with remaining camera
- No recovery mechanism

**What happens:** Camera fails at pitch 47/100 → session ends → lose pitches 48-100

**Workaround for test:**
- Monitor camera connections visually
- If camera disconnects, restart immediately
- Keep manual log of last successful pitch number

---

### 🔴 Issue 4: No Crash Recovery
**Severity: HIGH - No way to resume interrupted session**

**Problem:**
- If app crashes, no state saved to disk
- Can't resume session
- Don't know which pitches were recorded
- Must manually review logs to find last successful pitch

**Workaround for test:**
- Screenshot session summary every 20 pitches
- Keep manual log: pitch number, time, result
- Backup recordings folder every 25 pitches

---

## RECOMMENDED: Quick Safety Implementations

### Priority 1: Disk Space Check (15 minutes)
**DO THIS BEFORE TEST**

Add to `app/pipeline/recording/session_recorder.py`:
```python
def _check_disk_space_before_start(self) -> None:
    """Verify sufficient disk space before starting session."""
    import shutil

    usage = shutil.disk_usage(self._session_dir.parent)
    free_gb = usage.free / (1024**3)
    required_gb = 50.0  # 100 pitches @ ~300MB each ≈ 30GB + buffer

    if free_gb < required_gb:
        raise RuntimeError(
            f"Insufficient disk space!\n"
            f"Available: {free_gb:.1f}GB\n"
            f"Required: {required_gb}GB\n"
            f"Please free up space before recording."
        )

    logger.info(f"✓ Disk space check passed: {free_gb:.1f}GB available")
```

### Priority 2: VideoWriter Error Handling (10 minutes)
**DO THIS BEFORE TEST**

Wrap all `.write()` calls with error checking:
```python
def _write_frame_safe(self, writer, image, camera_label: str, frame_idx: int):
    """Write frame with error detection."""
    success = writer.write(image)
    if not success:
        error_msg = f"Video write failed: {camera_label} camera, frame {frame_idx}"
        logger.error(error_msg)
        # For field test: Log and continue (don't crash entire session)
        # TODO: Implement proper recovery later
    return success
```

### Priority 3: Real-Time Session Monitor (20 minutes)
**RECOMMENDED FOR TEST**

Add to UI: Real-time status display
```python
# Show during recording:
Pitch: 47/100
Disk: 42.3 GB free
FPS: L=59.2 R=59.1
Dropped: L=0 R=1
Status: ✓ Recording

# Update every second
```

---

## Field Test Procedure (Mandatory)

### Pre-Test Setup (30 minutes before)

1. **Check Available Disk Space**
   ```bash
   # Windows
   dir C:\ | findstr "bytes free"

   # Verify > 50GB free
   ```

2. **Verify Calibration Quality**
   ```bash
   # Run quick calibration check
   python run_setup_wizard.py

   # Confirm calibration rating is GOOD or EXCELLENT
   # Check RMS error < 1.0 px
   ```

3. **Test Camera Capture (5 test pitches)**
   ```bash
   python test_coaching_app.py

   # Record 5 test pitches
   # Verify:
   # - Both cameras capturing at 30 FPS
   # - Video files created
   # - File sizes reasonable (~300MB per pitch)
   # - No errors in logs
   ```

4. **Create Backup Location**
   ```bash
   # Set up secondary storage
   mkdir D:\pitchtracker_backup

   # or external drive
   mkdir E:\pitchtracker_backup
   ```

5. **Prepare Manual Log**
   ```
   Create spreadsheet or notepad:

   Pitch# | Time | Result | Notes
   1      | 2:15 | Strike | Good detection
   2      | 2:16 | Ball   |
   ...
   ```

### During Test (Every 10-25 Pitches)

**Every 10 pitches:**
- [ ] Check FPS stable (both cameras >58 FPS)
- [ ] Check disk space remaining
- [ ] Review last pitch video quality
- [ ] Note any warnings in logs

**Every 25 pitches:**
- [ ] BACKUP recordings folder to secondary storage
- [ ] Screenshot session summary
- [ ] Update manual log
- [ ] Verify session continuity (no gaps in pitch numbers)

**If ANY issue occurs:**
1. STOP immediately
2. Note pitch number
3. Backup current recordings
4. Review logs
5. Decide: Continue, restart, or troubleshoot

### Post-Test Validation (Critical!)

1. **Count Files**
   ```bash
   # Should have exactly 100 pitch folders
   dir /s recordings\session_YYYYMMDD\pitches
   ```

2. **Check File Sizes**
   ```python
   # All videos should be similar size (~200-400MB)
   # Flag any < 50MB (likely corrupted)
   import os
   from pathlib import Path

   session = Path("recordings/session_20260117")
   for pitch_dir in sorted(session.glob("pitch_*")):
       left_vid = pitch_dir / "left.avi"
       right_vid = pitch_dir / "right.avi"

       if left_vid.exists():
           size_mb = left_vid.stat().st_size / (1024**2)
           if size_mb < 50:
               print(f"⚠️ {pitch_dir.name}: left.avi only {size_mb:.1f}MB (may be corrupt)")
   ```

3. **Verify Video Playback**
   ```bash
   # Spot check 10 random pitches
   # Open in VLC or Windows Media Player
   # Confirm:
   # - Video plays smoothly
   # - No frozen frames
   # - Audio/video in sync (if audio captured)
   # - Ball visible throughout
   ```

4. **Check Timestamps**
   ```python
   # Verify no time gaps between pitches
   # Check manifest.json for each pitch
   ```

---

## Backup Strategy

### Option 1: Manual Backup (MINIMUM)
- Every 25 pitches: Copy `recordings/session_YYYYMMDD` to external drive
- Use `xcopy /s /i recordings\session_YYYYMMDD E:\backup\session_YYYYMMDD`

### Option 2: Real-Time Backup (BETTER)
- Run robocopy in background during session
- `robocopy recordings D:\backup\recordings /mir /mon:1 /mot:1`
- Mirrors changes every minute

### Option 3: Redundant Recording (BEST - needs code change)
- Modify session recorder to write to two directories simultaneously
- Primary: SSD for speed
- Secondary: External HD for backup

---

## Emergency Procedures

### If App Crashes Mid-Session

1. **Don't panic** - recordings up to crash point are likely safe
2. **Immediately backup** recordings folder
3. **Review logs** to find last successful pitch
   ```bash
   type logs\pitchtracker.log | findstr "Recording pitch"
   ```
4. **Manual count** pitch folders in session directory
5. **Resume:** Start NEW session for remaining pitches
6. **Document:** Note pitch range for each session

### If Camera Disconnects

1. **Stop session** immediately (don't let it timeout)
2. **Backup** current recordings
3. **Reconnect** camera (check USB cable, swap ports)
4. **Verify** both cameras detected:
   ```python
   from ui.device_utils import probe_uvc_devices
   print(probe_uvc_devices())
   ```
5. **Restart** coaching app
6. **Resume** with new session

### If Disk Fills Up

1. **STOP** recording immediately
2. **Check** `recordings/` folder size
3. **Move** old sessions to external drive
4. **Delete** test recordings if needed
5. **Verify** >50GB free
6. **Resume** with new session

### If FPS Drops Below 30

1. **Check** USB bandwidth (close other apps using cameras)
2. **Reduce** resolution if necessary (640x480 → 320x240)
3. **Check** CPU usage (Task Manager)
4. **Verify** SSD write speed (not HDD)
5. **Consider** reducing FPS target to 25 if 30 unstable

---

## Success Criteria

After 100 pitches, you should have:

- [ ] 100 pitch folders (`pitch_0001` through `pitch_0100`)
- [ ] Each folder contains:
  - [ ] `left.avi` (200-400MB)
  - [ ] `right.avi` (200-400MB)
  - [ ] `manifest.json` (metadata)
  - [ ] `observations.csv` (ball positions)
- [ ] Session summary with:
  - [ ] Total pitches: 100
  - [ ] Strikes/balls breakdown
  - [ ] Velocity distribution
  - [ ] Detection rate >90%
- [ ] No corrupted videos (all playable)
- [ ] Complete manual log matches recorded pitches
- [ ] Backup copy on external storage

---

## Risk Mitigation Summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Disk fills mid-session | CRITICAL | Check space before, monitor during, backup every 25 pitches |
| Video write fails silently | HIGH | Spot-check video sizes during test, validate post-test |
| Camera fails mid-session | HIGH | Monitor camera LEDs, restart immediately if failure, manual log |
| App crashes | HIGH | Backup every 25 pitches, manual log, screenshot summaries |
| Can't resume after crash | HIGH | Manual log tracks progress, can identify last pitch |
| Corrupted videos | MEDIUM | Validate file sizes post-test, backup prevents total loss |
| Poor calibration | MEDIUM | Verify calibration quality before test, re-check every 50 pitches |
| Timestamp desync | LOW | Monitoring added, frame-index pairing available |

---

## Final Pre-Test Checklist

**24 Hours Before:**
- [ ] Run camera validation tests (all 51 tests pass)
- [ ] Complete calibration, verify GOOD or EXCELLENT rating
- [ ] Test record 10 pitches, verify all systems working
- [ ] Prepare backup storage (50GB+ free)
- [ ] Charge laptop/ensure power supply

**1 Hour Before:**
- [ ] Check disk space (>50GB free)
- [ ] Verify cameras detected and capturing at 30 FPS
- [ ] Check calibration still valid
- [ ] Close all unnecessary apps
- [ ] Set up manual log (spreadsheet or notepad)
- [ ] Position backup drive

**Immediately Before:**
- [ ] Record 2-3 test pitches
- [ ] Verify videos created and playable
- [ ] Check timestamp sync stats (mean <10ms)
- [ ] Note starting disk space
- [ ] Start backup script (if using)

**GO/NO-GO Decision:**
- ✅ GO if: Disk >50GB, cameras 30 FPS, calibration GOOD, test pitches successful
- ❌ NO-GO if: Disk <30GB, cameras <28 FPS, calibration POOR, test pitches failed

---

## Contact Info

If major issues during test:
1. Stop recording immediately
2. Backup what you have
3. Document the issue (screenshot, log excerpt)
4. Don't panic - recordings up to failure point are likely recoverable

**Remember:** It's better to stop at pitch 50 with 50 good recordings than continue to pitch 100 with 30 corrupted ones.
