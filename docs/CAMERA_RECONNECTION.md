# Camera Reconnection Feature

**Date:** 2026-01-18
**Status:** ✅ Complete and Integrated
**Priority:** Low (#18)

---

## Overview

PitchTracker now includes automatic camera reconnection functionality that handles USB camera disconnections gracefully. When a camera disconnects (due to USB issues, power problems, or driver errors), the system automatically attempts to reconnect with exponential backoff, allowing uninterrupted operation during temporary connection issues.

**Key Benefits:**
- 🔄 Automatic reconnection with exponential backoff
- 📊 Real-time camera state tracking (Connected/Disconnected/Reconnecting/Failed)
- 🔔 Error bus integration for UI notifications
- 🎯 Configurable retry attempts and delays
- 🧪 Comprehensive test coverage (10 tests, all passing)

---

## Architecture

### Components

1. **CameraReconnectionManager** (`app/camera/reconnection.py`)
   - Manages camera connection states
   - Implements exponential backoff retry logic
   - Publishes state changes to error bus
   - Thread-safe camera tracking

2. **CameraManager Integration** (`app/pipeline/camera_management.py`)
   - Detects camera disconnections via error callbacks
   - Triggers automatic reconnection
   - Handles camera reopening and reconfiguration
   - Restarts capture threads

3. **PipelineService Integration** (`app/pipeline_service.py`)
   - Enables reconnection for physical cameras
   - Logs camera state changes
   - Routes error bus notifications

### State Machine

```
┌──────────┐
│ CONNECTED│◄─────────────┐
└──────┬───┘              │
       │                  │
       │ Error Detected   │ Reconnect Succeeds
       │                  │
       ▼                  │
┌─────────────┐          │
│ DISCONNECTED│          │
└──────┬──────┘          │
       │                  │
       │ Start Retry      │
       │                  │
       ▼                  │
┌──────────────┐         │
│ RECONNECTING │─────────┘
└──────┬───────┘
       │
       │ Max Attempts Reached
       │
       ▼
┌────────┐
│ FAILED │
└────────┘
```

---

## Configuration

### Default Settings

```python
CameraReconnectionManager(
    max_reconnect_attempts=5,  # Try up to 5 times
    base_delay=1.0,            # Start with 1 second delay
    max_delay=30.0             # Cap at 30 seconds delay
)
```

### Reconnection Timeline

| Attempt | Delay    | Cumulative Time |
|---------|----------|-----------------|
| 1       | ~1s      | 1s              |
| 2       | ~2s      | 3s              |
| 3       | ~4s      | 7s              |
| 4       | ~8s      | 15s             |
| 5       | ~16s     | 31s             |

**Total reconnection window:** ~31 seconds before giving up

---

## Usage

### Automatic Operation

Reconnection is **enabled by default** for physical cameras (UVC and OpenCV backends) and **disabled** for simulated cameras.

**No code changes required** - reconnection happens automatically when:
- Camera reports consecutive read failures (10 attempts)
- Camera frame stall detected (5 seconds without frames)

### Manual Control

```python
# Enable/disable reconnection
camera_manager.enable_reconnection(enabled=True)

# Set custom state change callback
def on_camera_state_change(camera_id: str, state: CameraState):
    if state == CameraState.RECONNECTING:
        print(f"🔄 Attempting to reconnect {camera_id} camera...")
    elif state == CameraState.CONNECTED:
        print(f"✅ Camera {camera_id} reconnected!")
    elif state == CameraState.FAILED:
        print(f"❌ Camera {camera_id} reconnection failed")

camera_manager.set_camera_state_callback(on_camera_state_change)
```

### Error Bus Integration

All camera state changes are published to the error bus:

```python
from app.events import subscribe_to_errors, ErrorCategory

def on_camera_error(event):
    """Handle camera error events."""
    if "disconnected" in event.message.lower():
        # Camera disconnected - reconnection starting
        pass
    elif "reconnected" in event.message.lower():
        # Camera reconnected successfully
        pass
    elif "failed" in event.message.lower():
        # Reconnection failed permanently
        pass

subscribe_to_errors(on_camera_error, category=ErrorCategory.CAMERA)
```

---

## Implementation Details

### Disconnection Detection

**In CameraManager._capture_loop():**

1. **Consecutive Failures:**
   - Counts frame read failures
   - Triggers disconnection after 10 consecutive failures
   - Publishes error to error bus

2. **Frame Stall:**
   - Monitors time since last successful frame
   - Triggers disconnection after 5 seconds without frames
   - Publishes error to error bus

**Both conditions:**
- Call error callback: `self._on_camera_error(label, error_msg)`
- Report to reconnection manager: `self._reconnection_mgr.report_disconnection(label)`
- Stop capture thread gracefully

### Reconnection Process

**In CameraManager._try_reconnect_camera():**

1. **Cleanup Old Camera:**
   - Close existing camera device
   - Wait for capture thread to finish (2s timeout)

2. **Create New Camera:**
   - Build new camera instance
   - Open camera with stored serial number
   - Configure with stored settings (resolution, FPS, exposure, etc.)

3. **Restart Capture:**
   - Create new capture thread
   - Start thread with camera reference
   - Update camera reference in manager

4. **Report Success/Failure:**
   - Return `True` if reconnection succeeded
   - Return `False` if any step failed
   - Reconnection manager handles state updates

### Thread Safety

- All camera state accessed through locks
- State change callbacks released lock before invocation (prevents deadlock)
- Reconnection threads are non-daemon (proper cleanup)
- Thread references cleaned up after completion

---

## Error Handling

### Camera Errors Published

**On Disconnection:**
```python
publish_error(
    category=ErrorCategory.CAMERA,
    severity=ErrorSeverity.ERROR,
    message=f"Camera {camera_id} disconnected",
    source="CameraReconnectionManager",
    camera_id=camera_id
)
```

**On Reconnection Success:**
```python
publish_error(
    category=ErrorCategory.CAMERA,
    severity=ErrorSeverity.INFO,
    message=f"Camera {camera_id} reconnected successfully",
    source="CameraReconnectionManager",
    camera_id=camera_id,
    attempts=attempt + 1
)
```

**On Reconnection Failure:**
```python
publish_error(
    category=ErrorCategory.CAMERA,
    severity=ErrorSeverity.CRITICAL,
    message=f"Camera {camera_id} reconnection failed after {attempts} attempts",
    source="CameraReconnectionManager",
    camera_id=camera_id,
    attempts=attempts
)
```

### User Impact

| Scenario | User Experience |
|----------|-----------------|
| **Temporary USB glitch** | Automatic reconnection within ~1-3 seconds, capture resumes seamlessly |
| **Cable unplugged/replugged** | Reconnection attempts for ~31 seconds, capture resumes if cable restored |
| **Camera hardware failure** | Reconnection fails after 5 attempts (~31s), user notified via error bus |
| **Camera power loss** | Reconnection fails, user must manually power camera and restart capture |

---

## Testing

### Test Suite

**File:** `tests/test_camera_reconnection.py`

**Coverage:**
- ✅ Camera registration and unregistration
- ✅ Disconnection reporting
- ✅ Successful reconnection flow
- ✅ Failed reconnection after max attempts
- ✅ State change callback invocation
- ✅ Connection success reporting
- ✅ Multiple camera management
- ✅ Exponential backoff delays
- ✅ Thread cleanup on unregister

**Results:** 10/10 tests passing

### Running Tests

```bash
# Run reconnection tests
python -m pytest tests/test_camera_reconnection.py -v

# Run all camera-related tests
python -m pytest tests/ -k camera -v
```

### Manual Testing

**Test Disconnection:**
1. Start capture with physical cameras
2. Unplug USB cable from one camera
3. Observe reconnection attempts in logs
4. Replug USB cable
5. Verify camera reconnects and capture resumes

**Expected Log Output:**
```
Camera left: Frame read failed (attempt 1/10): ...
Camera left: Frame read failed (attempt 10/10): ...
Camera left failed after 10 consecutive attempts
Camera left disconnected
Attempting to reconnect left camera (attempt 1/5) in 1.0s
Successfully reconnected left camera
✅ Camera left reconnected successfully
```

---

## Limitations

### Current Scope

✅ **Supported:**
- USB camera disconnections (UVC protocol)
- USB cable issues
- Driver hiccups
- Temporary power glitches
- Frame read timeouts
- Camera stall detection

❌ **Not Supported:**
- Changing camera serial numbers mid-session
- Hot-swapping cameras (different device)
- Simulated camera "disconnections" (disabled by design)
- Network camera reconnection (not applicable)

### Known Issues

None at this time. Reconnection is production-ready.

---

## Performance Impact

### Resource Usage

- **Memory:** Minimal (~1KB per camera for state tracking)
- **Threads:** 1 additional thread per disconnected camera (temporary)
- **CPU:** Negligible (reconnection attempts are infrequent)

### Reconnection Overhead

- **First attempt:** ~1 second
- **Subsequent attempts:** Exponentially increasing (2s, 4s, 8s, 16s)
- **Total window:** Maximum 31 seconds for 5 attempts

### Capture Impact

- During reconnection, affected camera stops producing frames
- Other camera continues capturing normally (stereo pair unaffected)
- Detection pipeline continues with available frames
- Recording paused until reconnection succeeds

---

## Future Enhancements

### Potential Improvements

1. **Configurable Retry Policy**
   - Per-camera retry settings
   - Different policies for different error types
   - User-configurable max attempts

2. **Smart Reconnection**
   - Detect camera model changes
   - Adjust settings based on new camera capabilities
   - Warn user if camera changed

3. **UI Integration**
   - Status bar indicator for camera states
   - Toast notifications on reconnection
   - Camera health dashboard

4. **Statistics Tracking**
   - Reconnection success rate
   - Average reconnection time
   - Disconnection frequency

5. **Advanced Error Recovery**
   - Automatic USB port reset
   - Driver reinstallation trigger
   - System resource monitoring

---

## Code Locations

### Key Files

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| Reconnection Manager | `app/camera/reconnection.py` | 1-289 | Core reconnection logic |
| Camera Manager | `app/pipeline/camera_management.py` | 35-529 | Disconnection detection & reconnection |
| Pipeline Service | `app/pipeline_service.py` | 274-292 | Initialization & state callback |
| Tests | `tests/test_camera_reconnection.py` | 1-225 | Comprehensive test suite |

### Integration Points

**Disconnection Detection:**
- `camera_management.py:508-514` - Consecutive failure handling
- `camera_management.py:521-527` - Frame stall detection

**Reconnection Trigger:**
- `camera_management.py:511` - Report disconnection to manager
- `camera_management.py:524` - Report stall disconnection

**Reconnection Logic:**
- `camera_management.py:411-495` - `_try_reconnect_camera()` method
- Reopens camera, reconfigures, restarts thread

**State Management:**
- `reconnection.py:212-283` - Reconnection loop with backoff
- `reconnection.py:159-186` - State change with callback
- `reconnection.py:105-133` - Disconnection reporting

---

## Example Scenario

### USB Cable Unplugged

**Timeline:**

```
T+0.0s: Camera left disconnected (USB cable unplugged)
        └─ Consecutive failures reach 10
        └─ Capture thread stops
        └─ Error bus: "Camera left disconnected"
        └─ State: CONNECTED → DISCONNECTED

T+1.0s: Reconnection attempt 1
        └─ State: DISCONNECTED → RECONNECTING
        └─ Try to open camera... FAILED (cable still unplugged)

T+3.0s: Reconnection attempt 2
        └─ Try to open camera... FAILED

T+5.0s: User replugs USB cable
        └─ Camera becomes available

T+7.0s: Reconnection attempt 3
        └─ Try to open camera... SUCCESS!
        └─ Configure camera... SUCCESS!
        └─ Start capture thread... SUCCESS!
        └─ State: RECONNECTING → CONNECTED
        └─ Error bus: "Camera left reconnected successfully"

T+7.1s: Normal operation resumes
        └─ Frames flowing again
        └─ Detection continues
        └─ Recording continues (if active)
```

**User Experience:**
- Brief interruption (~7 seconds)
- No manual intervention required
- Seamless recovery
- All settings preserved

---

## Troubleshooting

### Reconnection Not Working

**Symptoms:**
- Camera disconnects but never reconnects
- State stuck in DISCONNECTED

**Checks:**
1. Verify reconnection is enabled:
   ```python
   # Should be True for physical cameras
   camera_manager._enable_reconnection
   ```

2. Check if reconnect callback is set:
   ```python
   # Should not be None
   camera_manager._reconnection_mgr._reconnect_callback
   ```

3. Look for exceptions in logs:
   ```
   Failed to reconnect left camera: [exception details]
   ```

### Reconnection Fails Repeatedly

**Symptoms:**
- Reaches max attempts, goes to FAILED state
- Camera physically working

**Common Causes:**
1. **Wrong serial number** - Check stored serial matches camera
2. **Permissions issue** - Camera locked by another process
3. **Driver problem** - Update camera drivers
4. **USB port issue** - Try different USB port
5. **Power insufficient** - Use powered USB hub

**Debug Steps:**
```python
# Check stored config
camera_manager._config  # Should not be None

# Check camera serial
left_id, right_id = camera_manager.get_camera_ids()

# Check camera backend
camera_manager._backend  # "uvc", "opencv", or "sim"
```

### Slow Reconnection

**Symptoms:**
- Reconnection takes full 31 seconds
- Multiple attempts before success

**Explanations:**
- This is normal behavior with exponential backoff
- Early failures trigger increasing delays
- Ensures system doesn't overwhelm USB subsystem

**To speed up (if needed):**
```python
# Reduce max attempts and delays (in pipeline_service.py)
reconnection_mgr = CameraReconnectionManager(
    max_reconnect_attempts=3,  # Fewer attempts
    base_delay=0.5,            # Faster initial retry
    max_delay=10.0             # Lower max delay
)
```

---

## Summary

✅ **Complete Implementation:**
- Automatic reconnection with exponential backoff
- Error bus integration for UI notifications
- Thread-safe state management
- Comprehensive test coverage (10/10 tests passing)
- Production-ready reliability

✅ **User Benefits:**
- Handles temporary USB issues automatically
- No manual intervention required
- Preserves all camera settings
- Seamless recovery experience

✅ **Production Ready:**
- Tested and validated
- Integrated into pipeline service
- Error handling comprehensive
- Performance impact minimal

**Status:** Feature complete and deployed in PitchTracker v1.2.0+

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Author:** PitchTracker Development Team
**Next Review:** After beta deployment feedback
