# PitchTracker Production Deployment Checklist

**Last Updated:** 2026-01-18
**System Version:** With Phase 2-4 Hardening Complete

This checklist ensures all system hardening improvements are properly configured and tested before deploying to production.

---

## Pre-Deployment Requirements

### 1. Dependencies Installation

- [ ] Install Python 3.10+ (`python --version`)
- [ ] Install all requirements: `pip install -r requirements.txt`
- [ ] Verify psutil installed: `python -c "import psutil; print(psutil.__version__)"`
- [ ] Verify PySide6 installed: `python -c "import PySide6; print(PySide6.__version__)"`
- [ ] Verify OpenCV installed: `python -c "import cv2; print(cv2.__version__)"`

### 2. Configuration Files

- [ ] Configuration file exists: `configs/default.yaml` or `configs/snapdragon.yaml`
- [ ] ROI file exists: `rois/shared_rois.json` (or acknowledged as optional)
- [ ] Lane ROI file exists: `rois/shared_lane_rois.json` (or acknowledged as optional)
- [ ] Output directory is writable: Check `recording.output_dir` in config
- [ ] Camera settings configured: width, height, fps, exposure, gain

### 3. Hardware Setup

- [ ] Both cameras connected and powered
- [ ] Camera serials identified (use device refresh in UI or `uvc_devices` tool)
- [ ] Camera lenses clean and unobstructed
- [ ] Adequate lighting for ball detection
- [ ] Computer meets minimum specs:
  - [ ] 8GB+ RAM (16GB recommended)
  - [ ] 4+ CPU cores (8+ recommended)
  - [ ] 100GB+ free disk space

---

## System Hardening Verification

### 1. Integration Test

Run the comprehensive integration test:

```bash
python test_integration.py
```

**Expected Result:** `ALL TESTS PASSED OK`

**What it tests:**
- All hardening imports successful
- Error bus initialization
- Recovery manager start/stop
- Resource monitor start/stop with real metrics
- Cleanup manager registration
- Config validator initialization
- Resource limits configuration
- Error publishing end-to-end

**If it fails:**
- Check all Phase 2-4 code is present
- Verify psutil is installed
- Check for import errors in output

### 2. Configuration Validation

Start the application to test config validation:

```bash
python ui/qt_app.py --config configs/default.yaml
```

**Expected Result:**
- If config has errors: Dialog shows errors, application exits
- If config has warnings: Dialog shows warnings, application continues
- If config is valid: Application starts normally

**What to test:**
- [ ] Invalid camera width (e.g., -640) → Error dialog, app exits
- [ ] Unusual resolution (e.g., 123x456) → Warning dialog, app continues
- [ ] Missing required field → Error dialog with field name
- [ ] All valid settings → No dialogs, starts normally

### 3. Error Notification Widget

**Visual Verification:**
- [ ] Error notification widget visible at top of UI (initially empty/hidden)
- [ ] Widget has dismissible banner design
- [ ] Banner colors: Yellow (WARNING), Red (ERROR), Dark Red (CRITICAL)

**Functional Test:**
Trigger an error (camera disconnect, low disk) and verify:
- [ ] Error banner appears automatically
- [ ] Message is clear and actionable
- [ ] Severity color matches error type
- [ ] Can dismiss notification with X button
- [ ] Multiple errors stack vertically

### 4. Resource Monitoring

Check resource monitoring is active:

```python
from app.monitoring import get_resource_monitor

monitor = get_resource_monitor()
metrics = monitor.get_current_metrics()
print(f"CPU: {metrics.cpu_percent}%")
print(f"Memory: {metrics.memory_mb}MB")
print(f"Threads: {metrics.thread_count}")
print(f"Files: {metrics.open_files}")
```

**Expected Result:**
- [ ] Realistic CPU percentage (0-100%)
- [ ] Positive memory value (>50MB for app)
- [ ] Thread count >1 (multiple threads running)
- [ ] File count >0 (at least some files open)

**Verify thresholds:**
- [ ] Warning at 3GB memory (75MB if testing with small workload)
- [ ] Critical at 6GB memory (90MB if testing)
- [ ] Warning at 75% CPU
- [ ] Critical at 90% CPU

### 5. Resource Limits

Check configured limits:

```python
from app.config import get_resource_limits

limits = get_resource_limits()
print(f"Max memory: {limits.max_memory_mb}MB")
print(f"Max CPU: {limits.max_cpu_percent}%")
print(f"Detection queue: {limits.detection_queue_size}")
```

**Expected Values:**
- [ ] max_memory_mb: 6000.0 (6GB)
- [ ] warning_memory_mb: 3000.0 (3GB)
- [ ] max_cpu_percent: 90.0
- [ ] warning_cpu_percent: 75.0
- [ ] detection_queue_size: 10
- [ ] recording_queue_size: 30

**Adjust if needed** in `ui/main_window.py` line 1962-1982.

### 6. Graceful Shutdown

Test shutdown behavior:

**Manual Test:**
1. [ ] Start application
2. [ ] Start capture (with or without cameras)
3. [ ] Close application window
4. [ ] Verify no "force quit" dialog (all cleanup succeeded)
5. [ ] Check no zombie processes: `tasklist | findstr python` (Windows) or `ps aux | grep python` (Linux)
6. [ ] Check no orphan threads in logs

**With Failures:**
1. [ ] Simulate stuck operation (e.g., break cleanup callback)
2. [ ] Close application
3. [ ] Verify "force quit" dialog appears
4. [ ] Choose "No" → Application stays open
5. [ ] Choose "Yes" → Application force quits

### 7. Error Recovery

Test automatic recovery strategies:

**Recovery Manager Test:**
```python
from app.events import publish_error, ErrorCategory, ErrorSeverity
from app.events.recovery import get_recovery_manager

recovery = get_recovery_manager()
recovery.start()

# This should trigger no action (detection errors are ignored)
publish_error(
    category=ErrorCategory.DETECTION,
    severity=ErrorSeverity.ERROR,
    message="Test detection error",
    source="test"
)

# This should trigger stop_session action
publish_error(
    category=ErrorCategory.DISK_SPACE,
    severity=ErrorSeverity.CRITICAL,
    message="Test critical disk error",
    source="test"
)
```

**Expected Behaviors:**
- [ ] Detection errors → No automatic action (logged only)
- [ ] Critical disk space → Stops recording session
- [ ] Critical recording error → Stops session
- [ ] Camera errors → Logged (reconnection available but not auto-wired)

---

## Application Testing

### 1. Application Startup

```bash
python ui/qt_app.py
```

**Checklist:**
- [ ] Application window opens
- [ ] No error dialogs (unless config invalid)
- [ ] Error notification widget visible (empty initially)
- [ ] All UI controls visible and responsive
- [ ] Status label shows "Idle" or similar
- [ ] Device list populates with cameras

**Log Verification:**
Check logs for initialization messages:
- [ ] "Error handling system initialized"
- [ ] "Resource monitoring started"
- [ ] "Resource limits configured"
- [ ] "Cleanup tasks registered"

### 2. Camera Capture

**Start Capture:**
1. [ ] Select left and right cameras
2. [ ] Click "Start Capture"
3. [ ] Verify video preview appears
4. [ ] Check FPS counter shows ~60fps
5. [ ] Verify no error notifications appear

**With Errors:**
1. [ ] Disconnect one camera during capture
2. [ ] Verify error notification appears: "Camera disconnected"
3. [ ] Notification color is red (ERROR or CRITICAL)
4. [ ] Can dismiss notification

### 3. Recording Session

**Start Recording:**
1. [ ] Start capture successfully
2. [ ] Click "Start Recording"
3. [ ] Verify status shows "Recording..."
4. [ ] Record for 30 seconds
5. [ ] Click "Stop Recording"
6. [ ] Verify session summary dialog appears
7. [ ] Check recording files created in output directory

**Disk Space Warnings:**
1. [ ] Verify disk space monitoring active during recording
2. [ ] If disk space < 50GB: Warning logged
3. [ ] If disk space < 10GB: Critical error, recording stops
4. [ ] Error notification appears for disk issues

### 4. Detection Pipeline

**Test Detection:**
1. [ ] Start capture
2. [ ] Hold ball in front of cameras
3. [ ] Verify detections appear (circles on ball)
4. [ ] Check detection FPS in status
5. [ ] Verify no frame drop warnings (or minimal drops <10)

**Frame Drop Handling:**
1. [ ] Overload system (run heavy task)
2. [ ] Check for frame drop warnings in logs
3. [ ] Verify system continues operating
4. [ ] Check error bus receives frame drop events

---

## Performance Benchmarks

### Expected Performance

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| FPS (both cameras) | 60 fps | >55 fps | <50 fps |
| Frame drops | 0 | <10 total | >20 total |
| CPU usage | <50% | <75% | >90% |
| Memory usage | <2GB | <3GB | >6GB |
| Detection latency | <10ms | <20ms | >50ms |
| Startup time | <5s | <10s | >15s |

### Benchmarking Commands

**CPU & Memory:**
```python
from app.monitoring import get_resource_monitor
import time

monitor = get_resource_monitor()
for i in range(10):
    metrics = monitor.get_current_metrics()
    print(f"{i}: CPU={metrics.cpu_percent}% Memory={metrics.memory_mb}MB")
    time.sleep(1)
```

**Frame Rate:**
```python
from app.pipeline_service import InProcessPipelineService

service = InProcessPipelineService(backend="uvc")
# ... start capture ...
stats = service.get_stats()
print(f"Left FPS: {stats['left']['fps_avg']}")
print(f"Right FPS: {stats['right']['fps_avg']}")
print(f"Drops: {stats['left']['dropped_frames']}")
```

### Performance Issues

If performance is below targets:

**High CPU (>75%):**
- [ ] Check detection settings (reduce resolution, increase thresholds)
- [ ] Verify detection threading mode is "per_camera"
- [ ] Check for runaway processes in task manager
- [ ] Review resource monitor logs for spikes

**High Memory (>3GB):**
- [ ] Check queue sizes (detection_queue_size, recording_queue_size)
- [ ] Verify frame buffers are releasing properly
- [ ] Look for memory leaks (memory increasing over time)
- [ ] Check resource monitor triggers warnings

**Frame Drops:**
- [ ] Increase detection queue size (default 10)
- [ ] Reduce camera resolution (1280x720 vs 1920x1080)
- [ ] Lower FPS (30 fps vs 60 fps)
- [ ] Check disk write speed for recording

---

## Error Scenarios Testing

### 1. Camera Disconnection

**Test:**
1. [ ] Start capture with both cameras
2. [ ] Physically disconnect right camera USB
3. [ ] Verify error notification: "Failed to read from camera" or similar
4. [ ] Check error bus logs show camera error
5. [ ] Application continues with left camera
6. [ ] Reconnect camera → Manual restart required (auto-reconnect not wired yet)

### 2. Disk Space Exhaustion

**Test (Caution: Don't actually fill disk!):**
1. [ ] Start recording
2. [ ] Simulate low disk by checking thresholds:
   - [ ] 50GB free → Warning logged
   - [ ] 10GB free → Critical error, stops recording
3. [ ] Verify error notification appears
4. [ ] Verify recording stops automatically

### 3. Configuration Errors

**Test:**
1. [ ] Edit `configs/default.yaml`, set invalid value (e.g., `width: -640`)
2. [ ] Start application
3. [ ] Verify error dialog appears: "Configuration validation failed"
4. [ ] Verify application exits
5. [ ] Fix config
6. [ ] Restart application → Should work

### 4. Detection Failures

**Test:**
1. [ ] Start capture
2. [ ] Monitor detection thread errors (check logs)
3. [ ] Verify consecutive detection failures (>10) trigger error callback
4. [ ] Verify error published to error bus
5. [ ] Application continues despite detection errors

### 5. Recording Failures

**Test:**
1. [ ] Start recording to read-only directory
2. [ ] Verify error notification appears
3. [ ] Check error bus logs show recording error
4. [ ] Verify session stops or fails gracefully

---

## Monitoring & Logging

### Log Files

Check log files exist and contain expected entries:

- [ ] Application startup logs: Initialization messages
- [ ] Error bus logs: Published errors with categories
- [ ] Resource monitor logs: Periodic metric snapshots
- [ ] Recovery manager logs: Recovery actions taken
- [ ] Cleanup manager logs: Shutdown sequence

### Error History

View error history:

```python
from app.events import get_error_bus

error_bus = get_error_bus()
history = error_bus.get_history(limit=20)

for event in history:
    print(f"{event.timestamp}: {event.severity.value} - {event.category.value} - {event.message}")
```

### Error Counts

Check error counts by category:

```python
from app.events import get_error_bus

counts = get_error_bus().get_error_counts()
for category, count in counts.items():
    print(f"{category.value}: {count} errors")
```

---

## Production Configuration Tuning

### High-Performance Systems (8-core, 16GB RAM)

```python
# ui/main_window.py line 1962-1982
limits = ResourceLimits(
    max_memory_mb=10000.0,      # 10GB
    warning_memory_mb=5000.0,   # 5GB
    max_cpu_percent=95.0,       # 95%
    warning_cpu_percent=80.0,   # 80%
    detection_queue_size=15,    # Increased
    recording_queue_size=50,    # Increased
)
```

### Low-Performance Systems (4-core, 8GB RAM)

```python
limits = ResourceLimits(
    max_memory_mb=4000.0,       # 4GB
    warning_memory_mb=2000.0,   # 2GB
    max_cpu_percent=85.0,       # 85%
    warning_cpu_percent=70.0,   # 70%
    detection_queue_size=6,     # Reduced
    recording_queue_size=20,    # Reduced
)
```

### Production Environment

```python
limits = ResourceLimits(
    max_memory_mb=6000.0,       # 6GB (default)
    warning_memory_mb=3000.0,   # 3GB
    max_cpu_percent=90.0,       # 90%
    warning_cpu_percent=75.0,   # 75%
    detection_queue_size=10,    # Default
    recording_queue_size=30,    # Default
    camera_open_timeout=20.0,   # Increase for slow cameras
    shutdown_timeout=90.0,      # Increase for large sessions
)
```

---

## Post-Deployment Monitoring

### First 24 Hours

Monitor these metrics closely:

- [ ] Error notification frequency (should be rare)
- [ ] CPU usage patterns (should be <75% average)
- [ ] Memory usage growth (should be stable, not growing)
- [ ] Frame drop counts (should be <10 per session)
- [ ] Crash/restart frequency (should be zero)

### Weekly Checks

- [ ] Review error history: `get_error_bus().get_history()`
- [ ] Check error counts by category
- [ ] Verify no memory leaks (memory stays stable over time)
- [ ] Check disk space trends
- [ ] Review performance metrics

### Monthly Review

- [ ] Analyze error patterns
- [ ] Tune resource limits based on actual usage
- [ ] Update configuration for better performance
- [ ] Review and update documentation

---

## Rollback Plan

If system hardening causes issues:

### Quick Disable (Not Recommended)

Comment out hardening initialization in `ui/main_window.py`:

```python
# Initialize system hardening (Phase 2-4)
# self._init_error_handling()
# self._init_resource_monitoring()
# self._init_resource_limits()
```

### Proper Rollback

```bash
# Revert to commit before hardening integration
git log --oneline | head -10  # Find commit before integration
git revert <commit-hash>      # Revert integration commit

# Or reset to previous version
git reset --hard <commit-hash>
```

### Known Issues

If you encounter these, they are expected:

1. **2 test failures** - Test throttling expectations, not production bugs
2. **"No recovery strategy" messages** - INFO-level events have no recovery by design
3. **Empty error widget** - Normal when no errors occur
4. **High initial CPU** - Normal during startup, should stabilize

---

## Success Criteria

System is ready for production when:

- ✅ Integration test passes (`test_integration.py`)
- ✅ Application starts without errors
- ✅ Configuration validation works
- ✅ Error notifications appear correctly
- ✅ Resource monitoring shows accurate metrics
- ✅ Graceful shutdown completes successfully
- ✅ Camera capture works reliably
- ✅ Recording sessions complete without errors
- ✅ Performance meets benchmarks (FPS, CPU, memory)
- ✅ Error recovery works as expected

---

## Support & Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'psutil'"**
- Solution: `pip install psutil==7.2.1`

**"Configuration validation failed"**
- Solution: Check config file syntax, fix reported errors

**"Error notification widget not showing errors"**
- Solution: Verify `ErrorNotificationBridge` is created
- Check error severity is WARNING or higher

**"Application hangs on shutdown"**
- Solution: Check cleanup tasks aren't blocking
- Verify timeout values are reasonable
- Check logs for stuck cleanup tasks

**"High memory usage"**
- Solution: Check queue sizes, reduce if needed
- Verify resource limits configured correctly
- Look for memory leaks in logs

### Getting Help

- Check documentation: `docs/INTEGRATION_GUIDE.md`
- Review implementation: `docs/HARDENING_COMPLETE.md`
- Run integration test: `python test_integration.py`
- Check error history: `get_error_bus().get_history()`
- Review logs for error messages

---

## Checklist Summary

### Pre-Deployment
- [ ] All dependencies installed
- [ ] Configuration files present
- [ ] Hardware connected and tested
- [ ] Integration test passes

### System Hardening
- [ ] Config validation works
- [ ] Error notifications visible
- [ ] Resource monitoring active
- [ ] Resource limits configured
- [ ] Graceful shutdown tested
- [ ] Error recovery verified

### Application Testing
- [ ] Startup successful
- [ ] Camera capture works
- [ ] Recording functional
- [ ] Detection pipeline operating
- [ ] Performance acceptable

### Error Scenarios
- [ ] Camera disconnection handled
- [ ] Disk space warnings work
- [ ] Config errors caught
- [ ] Detection failures handled
- [ ] Recording errors handled

### Post-Deployment
- [ ] Monitoring plan in place
- [ ] Rollback plan documented
- [ ] Success criteria met

---

**Deployment Status:** □ Ready  □ Needs Work  □ Blocked

**Notes:**


**Approved By:** ________________  **Date:** __________

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Maintained By:** Development Team
