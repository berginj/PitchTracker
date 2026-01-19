# Camera Reliability Validation Guide

This guide walks through validating all camera reliability improvements with your actual hardware.

## Phase 1: Run Automated Tests ✓

**What:** Verify all unit tests pass
**Why:** Ensures core logic is correct
**How:**
```bash
python -m pytest tests/test_timeout_utils.py tests/test_device_discovery.py tests/test_camera_manager.py -v
```

**Expected:** All 51 tests pass in ~10 seconds
**Status:** ✅ Already validated - all tests passing

## Phase 2: Test Camera Discovery

**What:** Verify cameras are found quickly and reliably
**Why:** Fast discovery prevents UI delays

### Test 2.1: Basic Discovery
```bash
# Test UVC device enumeration
python -c "from ui.device_utils import probe_uvc_devices; print(probe_uvc_devices())"
```

**Expected Output:**
```
[{'serial': 'YOUR_SERIAL_1', 'friendly_name': 'Camera Name 1'},
 {'serial': 'YOUR_SERIAL_2', 'friendly_name': 'Camera Name 2'}]
```

**Success Criteria:**
- ✅ Both cameras appear in list
- ✅ Completes in < 500ms
- ✅ Serial numbers are unique

### Test 2.2: Discovery Caching
```bash
# Run discovery twice - second should be instant
python -c "
import time
from ui.device_utils import probe_uvc_devices, clear_device_cache

# First probe (uncached)
clear_device_cache()
start = time.monotonic()
devices1 = probe_uvc_devices()
time1 = time.monotonic() - start

# Second probe (cached)
start = time.monotonic()
devices2 = probe_uvc_devices()
time2 = time.monotonic() - start

print(f'First probe: {time1*1000:.1f}ms')
print(f'Second probe (cached): {time2*1000:.1f}ms')
print(f'Speedup: {time1/time2:.0f}x faster')
"
```

**Success Criteria:**
- ✅ First probe < 500ms
- ✅ Cached probe < 5ms
- ✅ 100x+ speedup

### Test 2.3: Parallel OpenCV Probing (Fallback)
```bash
# Test OpenCV fallback (only runs if no UVC devices)
python -c "
import time
from ui.device_utils import probe_opencv_indices

start = time.monotonic()
indices = probe_opencv_indices(max_index=4, parallel=True, use_cache=False)
elapsed = time.monotonic() - start

print(f'Found cameras at indices: {indices}')
print(f'Time: {elapsed:.2f}s')
print(f'Time per camera: {elapsed/4:.2f}s')
"
```

**Success Criteria:**
- ✅ Completes in < 2 seconds for 4 cameras
- ✅ Doesn't hang on non-existent cameras

## Phase 3: Test Setup Wizard

**What:** Verify calibration workflow works end-to-end
**Why:** Setup must work reliably for new users

### Test 3.1: Run Setup Wizard
```bash
python run_setup_wizard.py
```

**Steps:**
1. Launch wizard
2. Select your two cameras
3. Verify video preview appears quickly
4. Complete checkerboard calibration
5. Set ROI zones
6. Save configuration

**Success Criteria:**
- ✅ Camera selection dialog appears instantly (< 100ms)
- ✅ Video preview starts within 2 seconds
- ✅ No freezing or hanging
- ✅ Checkerboard detection works
- ✅ Configuration saves successfully

**Watch For:**
- ❌ UI freezing during camera open
- ❌ "Camera not found" errors
- ❌ Black video frames
- ❌ Timeouts or hangs

## Phase 4: Test Coaching App

**What:** Verify coaching session starts and captures frames
**Why:** This is where you were having issues

### Test 4.1: Launch Coaching App
```bash
python test_coaching_app.py
```

**Steps:**
1. Click "Start Session"
2. Select cameras in dialog
3. Verify both camera feeds appear
4. Wait 30 seconds
5. Check stats panel updates

**Success Criteria:**
- ✅ Session starts within 2 seconds
- ✅ Both camera views render
- ✅ Frame rate shows ~30 FPS
- ✅ No "AttributeError" or crashes
- ✅ Stats update continuously

**Watch For:**
- ❌ "is_capturing" AttributeError
- ❌ Buttons not responding
- ❌ Blank camera views
- ❌ Low/unstable frame rate

### Test 4.2: Check Logs
After running coaching app, check logs for errors:

```bash
# Look for ERROR or CRITICAL messages
type logs\pitchtracker.log | findstr /i "ERROR CRITICAL"
```

**Success Criteria:**
- ✅ No ERROR messages (except intentional test failures)
- ✅ No CRITICAL messages
- ✅ INFO messages show successful camera open
- ✅ Frame capture statistics logged

## Phase 5: Stress Testing

**What:** Try to break the camera system
**Why:** Validate error handling works

### Test 5.1: Disconnect Camera During Capture
1. Start coaching session
2. Unplug one camera USB cable
3. Wait 10 seconds
4. Check app behavior

**Success Criteria:**
- ✅ Error callback fires (check logs)
- ✅ UI shows error message
- ✅ App doesn't crash
- ✅ Other camera continues working

### Test 5.2: Reconnect Camera
1. Plug camera back in
2. Clear device cache: `python -c "from ui.device_utils import clear_device_cache; clear_device_cache()"`
3. Try to start new session

**Success Criteria:**
- ✅ Camera appears in selection dialog
- ✅ Can start new session successfully

### Test 5.3: Rapid Start/Stop
1. Start session
2. Immediately stop
3. Repeat 5 times quickly

**Success Criteria:**
- ✅ No crashes or hangs
- ✅ Resources properly cleaned up
- ✅ Can start new session after stops

### Test 5.4: Camera Already In Use
1. Open camera in another app (e.g., Windows Camera app)
2. Try to start PitchTracker session

**Success Criteria:**
- ✅ Clear error message about camera in use
- ✅ Retry logic attempts 3 times
- ✅ App doesn't hang

## Phase 6: Performance Validation

**What:** Measure actual startup times
**Why:** Ensure we hit < 2 second target

### Test 6.1: Measure Session Start Time
```bash
python -c "
import time
from app.pipeline_service import InProcessPipelineService
from configs.settings import AppConfig

config = AppConfig.load()
service = InProcessPipelineService(config)

# Measure start time
start = time.monotonic()
service.start_capture('YOUR_LEFT_SERIAL', 'YOUR_RIGHT_SERIAL')
elapsed = time.monotonic() - start

print(f'Session start time: {elapsed:.2f}s')

# Wait for first frames
time.sleep(0.5)

# Stop
service.stop_capture()

if elapsed < 2.0:
    print('✅ PASS: Under 2 second target')
else:
    print(f'❌ FAIL: Exceeds 2 second target by {elapsed - 2.0:.2f}s')
"
```

**Success Criteria:**
- ✅ Complete in < 2 seconds
- ✅ Consistent across multiple runs
- ✅ No timeout errors

## Phase 7: Regression Testing

**What:** Verify nothing broke
**Why:** Ensure changes don't affect other features

### Test 7.1: Run Full Test Suite
```bash
python -m pytest tests/ -v --tb=short
```

**Success Criteria:**
- ✅ All existing tests still pass
- ✅ No new test failures
- ✅ Camera setup tests pass

### Test 7.2: Test Ball Detection
1. Start coaching session
2. Throw a pitch
3. Verify detection works

**Success Criteria:**
- ✅ Ball detected in both cameras
- ✅ Trajectory calculated
- ✅ Stats updated

## Validation Checklist

Complete this checklist as you validate:

### Discovery & Setup
- [ ] Camera discovery finds both cameras
- [ ] Discovery completes quickly (< 500ms)
- [ ] Caching works (< 5ms on second probe)
- [ ] Setup wizard completes successfully
- [ ] Video preview appears within 2 seconds

### Coaching App
- [ ] Session starts without errors
- [ ] Both camera feeds render
- [ ] Frame rate is stable (~30 FPS)
- [ ] Stats update continuously
- [ ] No AttributeError exceptions

### Error Handling
- [ ] Disconnected camera triggers error callback
- [ ] Error message appears in logs
- [ ] App doesn't crash on camera failure
- [ ] Can recover after reconnecting camera
- [ ] "Camera in use" error is clear

### Performance
- [ ] Session starts in < 2 seconds
- [ ] No UI freezing during camera operations
- [ ] Rapid start/stop works reliably
- [ ] Frame capture is consistent

### Regression
- [ ] All automated tests pass (51/51)
- [ ] Ball detection still works
- [ ] Calibration data loads correctly
- [ ] ROI zones work properly

## Troubleshooting

### Issue: Cameras not found
**Check:**
- Are cameras plugged in?
- Do they appear in Device Manager?
- Run: `python -c "from capture.uvc_backend import list_uvc_devices; print(list_uvc_devices())"`

### Issue: Session start hangs
**Check:**
- Check logs for timeout messages
- Verify cameras not in use by another app
- Try with `backend="opencv"` instead of `backend="uvc"`

### Issue: Black frames
**Check:**
- Camera lens caps removed?
- Lighting sufficient?
- Check frame validation logs
- Try adjusting exposure settings

### Issue: Low frame rate
**Check:**
- USB 3.0 ports being used?
- Other USB devices causing bandwidth issues?
- Check stats: `camera_manager.get_stats()`

## Next Steps After Validation

Once validation is complete:

### If All Tests Pass ✅
1. Update project documentation
2. Create release notes
3. Consider adding metrics dashboard
4. Plan next features

### If Issues Found ❌
1. Document specific failure
2. Check relevant logs
3. Add regression test
4. Create bug report with:
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant log snippets
   - Camera hardware details

## Contact

If you encounter issues during validation:
- Check logs in `logs/pitchtracker.log`
- Review error messages carefully
- Note exact steps to reproduce
- Include camera hardware details (model, serial)

## Success Metrics

Your camera system is production-ready when:
- ✅ All 51 automated tests pass
- ✅ Session starts in < 2 seconds consistently
- ✅ No crashes or hangs during normal use
- ✅ Error messages are clear and actionable
- ✅ Can recover from camera disconnects
- ✅ Performance is consistent across runs
