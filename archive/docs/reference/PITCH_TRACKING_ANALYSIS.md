# Critical Analysis: Pitch Tracking Logic

## Executive Summary

The pitch tracking implementation has **12 critical issues** that affect accuracy, timing, data loss, and thread safety. Most critical is the complete failure of pre-roll buffering and loss of observations at pitch boundaries.

**Severity:**
- 🔴 **CRITICAL** (3 issues): Data loss, timing errors
- 🟠 **HIGH** (5 issues): Race conditions, missing observations
- 🟡 **MEDIUM** (4 issues): Edge cases, error handling

---

## 🔴 CRITICAL ISSUES

### 1. Pre-roll Buffer is Always Empty (CRITICAL BUG)

**Location:** `pipeline_service.py:773-774`

```python
if self._pitch_recorder:
    self._pitch_recorder.buffer_pre_roll(label, frame)  # ❌ WRONG
```

**Problem:**
- Pre-roll is only buffered AFTER `_pitch_recorder` is created
- But `_pitch_recorder` is created in `_on_pitch_start()` callback
- By that time, there's no buffered pre-roll data!
- Result: **All pitch videos are missing pre-roll frames**

**Flow:**
```
Frame 1-99:  No pitch_recorder → pre-roll NOT buffered
Frame 100:   Triggers pitch start → creates pitch_recorder → pre-roll buffer is EMPTY
Frame 101+:  Records normally, but missed critical pre-roll data
```

**Fix:**
```python
# Buffer pre-roll ALWAYS (not just when pitch_recorder exists)
if self._session_active:
    # Need persistent pre-roll buffers in pipeline_service
    self._pre_roll_buffers[label].append(frame)
    # Pass to pitch_recorder when it's created
```

---

### 2. Wrong Start Time Calculation

**Location:** `pipeline_service.py:383`

```python
start_ns=observations[0].t_ns if observations else end_ns  # ❌ WRONG
```

**Problems:**
1. Uses `end_ns` as `start_ns` when no observations (nonsensical)
2. Uses first observation's timestamp, not actual pitch start time
3. Actual pitch started `min_active_frames` earlier

**Impact:**
- Trajectory analysis uses wrong time window
- Speed calculations are inaccurate
- Timestamps in manifest are misleading

**Fix:**
```python
# PitchStateMachine needs to track actual start_ns
def _start_pitch(self, frame_ns: int):
    self._actual_start_ns = frame_ns - (self._active_frames * self._frame_period_ns)
    # Pass actual_start_ns in callback
    if self._on_pitch_start:
        self._on_pitch_start(self._pitch_index, self._actual_start_ns)

# In _on_pitch_end:
start_ns = self._pitch_start_ns  # Use tracked start time, not observation time
```

---

### 3. Observations Lost at Pitch Boundary

**Location:** `pipeline_service.py:344-350`, `pitch_tracking.py:111-118`

```python
# Observations added BEFORE state update
for obs in observations:
    self._pitch_tracker.add_observation(obs)  # ❌ Pitch not active yet!

# State machine update (might trigger start)
self._pitch_tracker.update(frame_ns, lane_count, plate_count, obs_count)
```

**Problem:**
- Observations added before `update()` is called
- `add_observation()` only stores if `self._active == True`
- But `update()` hasn't run yet to set `_active = True`
- **Critical frame that triggers pitch start loses its observations**

**Timeline:**
```
Frame 100: Has 3 observations
  1. add_observation() called 3x → _active=False → observations DROPPED
  2. update() called → _active_frames reaches threshold → _active=True
  Result: Lost 3 observations from the triggering frame!
```

**Fix:**
```python
# Option 1: Update state BEFORE adding observations
self._pitch_tracker.update(frame_ns, lane_count, plate_count, obs_count)
for obs in observations:
    self._pitch_tracker.add_observation(obs)

# Option 2: Store pending observations and retroactively add them
# Option 3: Make state machine track "ramp up" observations
```

---

## 🟠 HIGH SEVERITY ISSUES

### 4. No Thread Safety in PitchStateMachine

**Location:** `pitch_tracking.py` (entire class)

**Problem:**
- No locks protecting state variables
- `update()` and `add_observation()` can be called concurrently
- `_observations` list is not thread-safe
- Stereo pair processing happens in separate thread

**Race Condition Example:**
```python
Thread 1: update() → checks _active (False) → about to set _active=True
Thread 2: add_observation() → checks _active (False) → skips observation
Thread 1: sets _active=True
Result: Observation lost due to race
```

**Fix:**
```python
class PitchStateMachine:
    def __init__(self):
        self._lock = threading.Lock()

    def update(self, ...):
        with self._lock:
            # ... state logic

    def add_observation(self, obs):
        with self._lock:
            if self._active:
                self._observations.append(obs)
```

---

### 5. Missing Ramp-Up Observations

**Location:** `pitch_tracking.py:90-98`

```python
if active:
    self._active_frames += 1
    if not self._active and self._active_frames >= self._min_active_frames:
        self._start_pitch(frame_ns)
```

**Problem:**
- Pitch starts after `min_active_frames` (e.g., 5 frames)
- Observations during those 5 frames are LOST
- These are critical early ball detections

**Example:**
```
Frame 96: Detection, _active_frames=1, _active=False → observation LOST
Frame 97: Detection, _active_frames=2, _active=False → observation LOST
Frame 98: Detection, _active_frames=3, _active=False → observation LOST
Frame 99: Detection, _active_frames=4, _active=False → observation LOST
Frame 100: Detection, _active_frames=5, triggers start → observation LOST (see issue #3)
Frame 101: Detection, _active=True → FIRST observation captured
Result: Lost 5 critical observations at pitch start!
```

**Fix:**
```python
# Store observations during ramp-up
self._pending_observations = []

def add_observation(self, obs):
    if self._active:
        self._observations.append(obs)
    elif self._active_frames > 0:
        # Store during ramp-up
        self._pending_observations.append(obs)

def _start_pitch(self, frame_ns):
    # Promote pending observations
    self._observations.extend(self._pending_observations)
    self._pending_observations.clear()
```

---

### 6. Incorrect End Time Calculation

**Location:** `pitch_tracking.py:104-106`

```python
if self._gap_frames >= self._end_gap_frames:
    self._finalize_pitch(frame_ns)  # ❌ Uses current frame_ns
```

**Problem:**
- Pitch ends after `end_gap_frames` with no detections (e.g., 10 frames)
- But `frame_ns` is the CURRENT frame, not when ball disappeared
- Actual end was ~10 frames ago

**Example:**
```
Frame 200: Last detection, ball visible
Frame 201-210: No detections, counting gap
Frame 211: gap_frames=10, pitch ends with frame_ns=211
Reality: Ball disappeared at frame 200, not 211
Error: 10 frames * 33ms = 330ms timing error!
```

**Fix:**
```python
def update(self, frame_ns, ...):
    if active:
        self._gap_frames = 0
        self._last_detection_ns = frame_ns  # Track last detection
    else:
        if self._active:
            self._gap_frames += 1
            if self._gap_frames >= self._end_gap_frames:
                # Use last detection time, not current time
                self._finalize_pitch(self._last_detection_ns)
```

---

### 7. No Callback Error Handling

**Location:** `pitch_tracking.py:175-176, 190-191`

```python
if self._on_pitch_start:
    self._on_pitch_start(self._pitch_index, frame_ns)  # ❌ No try/except
```

**Problem:**
- If callback throws exception, state machine is corrupted
- `_active` is set to True, but callback failed
- Pitch recorder might not be created
- Observations accumulate with nowhere to go

**Fix:**
```python
def _start_pitch(self, frame_ns):
    self._active = True
    self._start_ns = frame_ns
    self._pitch_index += 1
    self._observations = []

    if self._on_pitch_start:
        try:
            self._on_pitch_start(self._pitch_index, frame_ns)
        except Exception as e:
            logger.error(f"Pitch start callback failed: {e}", exc_info=True)
            # Revert state to prevent corruption
            self._active = False
            self._pitch_index -= 1
```

---

### 8. Empty Pitch Detection Missing

**Location:** `pitch_tracking.py:178-194`

```python
def _finalize_pitch(self, frame_ns):
    # No check for minimum observations
    if self._on_pitch_end:
        self._on_pitch_end(frame_ns, self._pitch_index, list(self._observations))
```

**Problem:**
- False triggers create empty pitch records
- Wastes disk space, creates junk data
- Example: Someone walks in front of camera

**Fix:**
```python
def _finalize_pitch(self, frame_ns):
    self._active = False
    self._active_frames = 0
    self._gap_frames = 0
    self._end_ns = frame_ns

    # Only finalize if we have meaningful data
    MIN_OBSERVATIONS = 3
    if len(self._observations) < MIN_OBSERVATIONS:
        logger.warning(f"Pitch {self._pitch_index} has only {len(self._observations)} observations, discarding")
        self._observations = []
        return

    if self._on_pitch_end:
        self._on_pitch_end(frame_ns, self._pitch_index, list(self._observations))
```

---

## 🟡 MEDIUM SEVERITY ISSUES

### 9. force_end() Uses Stale Timestamp

**Location:** `pitch_tracking.py:146-149`

```python
def force_end(self):
    if self._active:
        self._finalize_pitch(self._end_ns or 0)  # ❌ Might be stale
```

**Problem:**
- `_end_ns` is only updated when detections occur
- If called during gap period, timestamp is old
- Should use current time

**Fix:**
```python
def force_end(self, current_ns: Optional[int] = None):
    if self._active:
        end_time = current_ns if current_ns is not None else self._end_ns
        self._finalize_pitch(end_time)
```

---

### 10. Configuration Update Mid-Pitch

**Location:** `pitch_tracking.py:151-161`

```python
def update_config(self, ...):
    self._min_active_frames = min_active_frames  # ❌ No safety check
    self._end_gap_frames = end_gap_frames
```

**Problem:**
- Changing thresholds during active pitch causes inconsistent behavior
- Could immediately trigger/prevent end condition

**Fix:**
```python
def update_config(self, ...):
    if self._active:
        logger.warning("Cannot update config during active pitch")
        return False
    self._min_active_frames = min_active_frames
    self._end_gap_frames = end_gap_frames
    return True
```

---

### 11. No Minimum Pitch Duration

**Location:** `pitch_tracking.py:90-98`

**Problem:**
- Could trigger on very brief false positives
- Need minimum time duration, not just frame count

**Fix:**
```python
MIN_PITCH_DURATION_NS = 100_000_000  # 100ms

def _start_pitch(self, frame_ns):
    # Check duration of ramp-up
    if self._active_frames > 0:
        duration = frame_ns - self._first_detection_ns
        if duration < MIN_PITCH_DURATION_NS:
            logger.debug("Suppressing short detection burst")
            return
```

---

### 12. Post-Roll Timing Inconsistency

**Location:** `pipeline_service.py:777-779`

```python
if self._pitch_recorder.should_close():
    self._pitch_recorder.close()
    self._pitch_recorder = None
```

**Problem:**
- Post-roll checks after EVERY frame write
- PitchRecorder keeps accepting frames after it should close
- Creates race with next pitch start

**Fix:**
```python
# In PitchRecorder, make closing atomic
def write_frame(self, label, frame):
    if self.should_close():
        return  # Stop accepting frames
    # ... write logic
```

---

## Impact Assessment

### Data Loss Severity

| Issue | Frames Lost | Data Impact |
|-------|-------------|-------------|
| Pre-roll failure | ~10-30 frames | 🔴 High - Early ball motion missing |
| Ramp-up observations | ~5 frames | 🔴 High - Critical release point |
| Boundary race condition | 1-2 frames | 🟠 Medium - Potential missing frames |
| End timing error | ~10 frames | 🟡 Low - Post-pitch, less critical |

### Timing Accuracy Errors

| Issue | Error Magnitude | Affects |
|-------|----------------|---------|
| Wrong start time | 100-300ms | Speed calculations, trajectory |
| End timing error | 100-300ms | Trajectory end point |
| No frame period | N/A | Can't calculate accurate times |

---

## Recommended Fixes Priority

### Immediate (Before Next Release)

1. **Fix pre-roll buffering** - Move buffers to pipeline_service, always buffer
2. **Add thread safety** - Add locks to PitchStateMachine
3. **Fix observation ordering** - Update state before adding observations
4. **Track actual start time** - Calculate real pitch start, not trigger frame

### High Priority (Next Sprint)

5. **Capture ramp-up observations** - Store pending observations during ramp-up
6. **Fix end timing** - Use last detection time, not current frame
7. **Add error handling** - Wrap callbacks in try/except
8. **Filter empty pitches** - Require minimum observations

### Medium Priority (Future Enhancement)

9. **Add minimum duration check** - Prevent false triggers
10. **Protect config updates** - Prevent mid-pitch changes
11. **Fix force_end timing** - Pass current time
12. **Atomic post-roll closing** - Prevent race conditions

---

## Testing Recommendations

### Unit Tests Needed

```python
def test_pre_roll_buffering():
    # Verify pre-roll is captured before pitch starts
    pass

def test_observation_at_boundary():
    # Verify observations at exact trigger frame are captured
    pass

def test_concurrent_updates():
    # Verify thread safety under concurrent access
    pass

def test_ramp_up_observations():
    # Verify observations during ramp-up are captured
    pass
```

### Integration Tests

1. Record real pitch with high-speed camera, verify pre-roll exists
2. Measure timing accuracy against ground truth
3. Test rapid start/stop scenarios
4. Test concurrent recording and configuration updates

---

## Architecture Recommendations

### Consider State Pattern Refactoring

```python
class PitchState(ABC):
    @abstractmethod
    def update(self, frame_ns, detections): ...

class InactiveState(PitchState):
    def update(self, frame_ns, detections):
        if detections > threshold:
            return RampUpState()
        return self

class RampUpState(PitchState):
    # Captures observations during ramp-up

class ActiveState(PitchState):
    # Main pitch recording

class EndingState(PitchState):
    # Post-roll management
```

### Consider Event Sourcing

Track all state changes as events for debugging:

```python
@dataclass
class PitchEvent:
    timestamp_ns: int
    event_type: str  # "detection", "start", "end"
    data: dict

# Allows replay and analysis of pitch detection logic
```

---

## Conclusion

The pitch tracking implementation has fundamental issues with:
1. **Data Loss** - Pre-roll and ramp-up observations are lost
2. **Timing** - Start/end times are incorrectly calculated
3. **Thread Safety** - No synchronization protection
4. **Error Handling** - Callbacks can corrupt state

**Estimated effort to fix critical issues:** 2-3 days
**Estimated effort for full fix:** 1 week

These issues significantly impact the accuracy and reliability of pitch analysis. Recommend prioritizing fixes before production use.
