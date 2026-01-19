# PitchTracker System Brittleness Analysis

**Date:** 2026-01-18
**Status:** Comprehensive analysis completed
**Purpose:** Identify and prioritize brittleness, error handling gaps, and performance issues

## Executive Summary

The PitchTracker video processing pipeline has **significant brittleness** in critical areas:

- **21 HIGH severity issues** that cause crashes or silent failures
- **1 CRITICAL issue** (exception swallowing in threads) causing invisible failures
- **8 MEDIUM severity issues** that cause resource leaks or performance degradation

**Key Finding:** The system lacks proper error handling in worker threads, leading to silent failures where the UI appears to work but no data is being captured.

## Critical Issues (Fix Immediately)

### 1. Silent Thread Failures ⚠️ CRITICAL
**Location:** Detection thread pool, capture threads
**Problem:** Exceptions swallowed; threads die silently
**Impact:** Ball detection stops but UI shows no error
**Fix Priority:** #1

### 2. No Backpressure Mechanism ⚠️ HIGH
**Location:** Camera capture → detection pipeline
**Problem:** Frames drop silently when detection is slow
**Impact:** Missing data; no warning to user
**Fix Priority:** #2

### 3. Disk Space Not Monitored ⚠️ HIGH
**Location:** Session/pitch recorders
**Problem:** Checks space once at start, not during recording
**Impact:** Disk fills mid-session → silent data loss
**Fix Priority:** #3

### 4. Video Codec Fallback Broken ⚠️ HIGH
**Location:** session_recorder.py:257-298
**Problem:** Doesn't close writer before retrying; inconsistent codecs
**Impact:** Video files corrupted or empty
**Fix Priority:** #4

### 5. Resource Leaks on Timeout ⚠️ HIGH
**Location:** timeout_utils.py, uvc_backend.py
**Problem:** Daemon threads continue running after timeout
**Impact:** Memory/CPU leak; 10+ ghost threads
**Fix Priority:** #5

## Category Breakdown

### Video Capture Pipeline
| Issue | Severity | File | Line | Impact |
|-------|----------|------|------|--------|
| Timeout threads leak | HIGH | timeout_utils.py | 50-64 | Resource exhaustion |
| Frame validation incomplete | HIGH | camera_management.py | 370-372 | Pipeline crashes |
| Callback errors swallowed | HIGH | camera_management.py | 383-389 | Silent failures |
| No backpressure | MEDIUM | camera_management.py | - | Queue overflow |
| Race condition on stop flag | MEDIUM | camera_management.py | 57, 195 | Unclean shutdown |

### Video Writing Pipeline
| Issue | Severity | File | Line | Impact |
|-------|----------|------|------|--------|
| Codec fallback broken | HIGH | session_recorder.py | 257-298 | Video corruption |
| Disk space not monitored | HIGH | session_recorder.py | 155-212 | Silent data loss |
| Write failures ignored | HIGH | pitch_recorder.py | 127, 134 | Corrupted recordings |
| File descriptor leaks | MEDIUM | session_recorder.py | 304-311 | Resource exhaustion |

### Detection Pipeline
| Issue | Severity | File | Line | Impact |
|-------|----------|------|------|--------|
| Frame drops silent | HIGH | threading_pool.py | 174-198 | No visibility |
| Worker pool race condition | HIGH | threading_pool.py | 244-254 | Frame processed twice |
| Callback no timeout | HIGH | threading_pool.py | 277-289 | Deadlock risk |
| No memory monitoring | MEDIUM | processor.py | - | OOM risk |

### Error Handling
| Issue | Severity | File | Line | Impact |
|-------|----------|------|------|--------|
| Exception in threads swallowed | **CRITICAL** | threading_pool.py | 213-216 | Silent failures |
| No error propagation | HIGH | camera_management.py | - | User doesn't know |
| State corruption on error | HIGH | pitch_tracking_v2.py | 394-404 | Undefined behavior |

## Detailed Issue Analysis

### 1. Silent Thread Failures (CRITICAL)

**Current Code:**
```python
# threading_pool.py:213-216
try:
    return self._detect_callback(label, frame)
except Exception:
    return []  # Silent failure, no logging!
```

**Problem:**
- Detection fails completely
- Returns empty list as if no balls detected
- No log message, no error notification
- User thinks system is working

**Fix:**
```python
try:
    return self._detect_callback(label, frame)
except Exception as e:
    logger.error(f"Detection failed for {label}: {e}", exc_info=True)
    self._detection_errors += 1
    if self._detection_errors > 10:
        self._on_fatal_error("detection", e)
    return []
```

### 2. No Backpressure Mechanism (HIGH)

**Current Code:**
```python
# camera_management.py:383-389
if self._on_frame_captured:
    try:
        self._on_frame_captured(label, frame)
    except Exception as e:
        logger.error(...)  # Continues capturing regardless!
```

**Problem:**
- Capture doesn't know if detection is overloaded
- Frames queue up until memory exhausted
- Oldest frames silently dropped
- No feedback loop to slow down

**Fix:**
```python
if self._on_frame_captured:
    try:
        accepted = self._on_frame_captured(label, frame)
        if not accepted:  # Detection overloaded
            logger.warning(f"{label} detection overloaded, skipping frames")
            time.sleep(0.1)  # Give pipeline time
            return
    except Exception as e:
        logger.error(...)
```

### 3. Disk Space Not Monitored (HIGH)

**Current Code:**
```python
# session_recorder.py:59-92
def _check_disk_space(self, required_gb=50.0):
    usage = shutil.disk_usage(self._record_dir)
    free_gb = usage.free / (1024**3)

    if free_gb < required_gb:
        return False, warning_message
    return True, ""

# Only called at session start!
```

**Problem:**
- Checks disk once at start
- 30-minute session can fill disk
- Write failures logged but recording continues
- User loses data silently

**Fix:**
```python
def _monitor_disk_space(self):
    """Background thread to monitor disk space."""
    while self._recording:
        free_gb = shutil.disk_usage(self._record_dir).free / (1024**3)

        if free_gb < 5.0:  # Critical
            logger.error("CRITICAL: Disk space < 5GB")
            self._trigger_emergency_stop()
            break
        elif free_gb < 20.0:  # Warning
            logger.warning(f"Low disk space: {free_gb:.1f}GB")

        time.sleep(5.0)

# Start monitoring thread in start_session()
self._disk_monitor_thread = threading.Thread(
    target=self._monitor_disk_space,
    daemon=False
)
self._disk_monitor_thread.start()
```

### 4. Video Codec Fallback Broken (HIGH)

**Current Code:**
```python
# session_recorder.py:257-298
fourcc = cv2.VideoWriter_fourcc(*"MJPG")
self._left_writer = cv2.VideoWriter(...)

if not self._left_writer.isOpened():
    logger.warning("MJPG codec failed...")
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    self._left_writer = cv2.VideoWriter(...)  # Old not closed!

# Right camera uses variable fourcc (could be wrong)
self._right_writer = cv2.VideoWriter(..., fourcc)  # Might be MJPG or XVID
```

**Problems:**
1. First writer never closed → resource leak
2. Right camera uses inconsistent codec if left failed
3. No validation after fallback

**Fix:**
```python
def _open_writer(self, path: Path, width: int, height: int, fps: int) -> cv2.VideoWriter:
    """Open video writer with codec fallback."""
    codec_list = ["MJPG", "XVID", "H264"]

    for codec_name in codec_list:
        fourcc = cv2.VideoWriter_fourcc(*codec_name)
        writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height), True)

        if writer.isOpened():
            logger.info(f"Video writer opened with {codec_name} codec")
            return writer
        else:
            writer.release()  # Clean up failed attempt

    raise CodecError(f"No working codec found in {codec_list}")

# Usage:
try:
    self._left_writer = self._open_writer(left_path, width, height, fps)
    self._right_writer = self._open_writer(right_path, width, height, fps)
except CodecError as e:
    logger.error(f"Failed to open video writers: {e}")
    raise
```

### 5. Resource Leaks on Timeout (HIGH)

**Current Code:**
```python
# timeout_utils.py:50-64
def wrapper():
    try:
        result_container[0] = func(*args, **kwargs)
    except Exception as e:
        exception_container[0] = e

thread = threading.Thread(target=wrapper, daemon=True)
thread.start()
thread.join(timeout_seconds)

if thread.is_alive():
    logger.error(...)
    raise CameraConnectionError(...)
    # Thread still running! Never cleaned up
```

**Problem:**
- Daemon threads can't be killed
- After 10 timeouts, 10 ghost threads running
- Each holds memory, possibly camera handle
- Accumulates over time

**Fix:**
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

def run_with_timeout(func, timeout_seconds, error_message, *args, **kwargs):
    """Execute function with timeout using ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            logger.error(f"{error_message} (timed out after {timeout_seconds}s)")
            raise CameraConnectionError(error_message)
        except Exception as e:
            logger.error(f"{error_message}: {e}")
            raise
    # Executor automatically cleans up thread on exit
```

## Performance Concerns

### Memory Usage
- **Pre-roll frame buffers**: 100 frames × 2 cameras × ~2MB = 400MB
- **Detection queues**: 6 frames × 2 cameras × ~2MB = 24MB
- **Observation history**: 12 observations × minimal = <1MB
- **Total baseline**: ~500MB

**Risks:**
- No memory limit enforcement
- Memory can grow unbounded if pipeline stalls
- No adaptive behavior on low memory

### CPU Usage
- **Detection threads**: 100% of 2 cores (expected)
- **Capture threads**: <5% per camera
- **UI thread**: <10%
- **Total**: ~200% CPU usage (2 cores)

**Risks:**
- Busy-waiting in some loops (5ms sleeps)
- Frame validation on every frame (expensive)
- No adaptive quality reduction under load

### Disk I/O
- **Write rate**: 1920x1080 @ 60fps × 2 cameras = ~250 MB/s
- **Expected**: ~900 GB/hour for dual camera
- **Codec**: MJPG (fast) or XVID (smaller)

**Risks:**
- No write buffering (synchronous writes)
- No fsync for durability
- SSD wear from continuous writes

## Recommended Architecture Changes

### 1. Error Event System

Replace ad-hoc error handling with centralized event system:

```python
@dataclass
class ErrorEvent:
    severity: Literal["info", "warning", "error", "fatal"]
    source: str  # "camera_left", "detection", "disk"
    code: str    # "USB_DISCONNECTED", "CODEC_FAILED"
    message: str
    timestamp_ns: int
    recovery_actions: List[str]  # ["restart_camera", "restart_app"]

class ErrorManager:
    def __init__(self):
        self._event_queue = queue.Queue()
        self._handlers = []

    def emit(self, event: ErrorEvent):
        logger.log(self._severity_to_level(event.severity), event.message)
        self._event_queue.put(event)

        for handler in self._handlers:
            handler(event)

    def register_handler(self, handler: Callable[[ErrorEvent], None]):
        self._handlers.append(handler)
```

### 2. Resource Manager

Track and enforce resource limits:

```python
class ResourceManager:
    def __init__(self):
        self._resources = {}  # name -> resource
        self._limits = {
            "memory_mb": 2000,
            "file_descriptors": 100,
            "threads": 10,
        }

    def register(self, name: str, resource: Any, cleanup: Callable):
        self._resources[name] = (resource, cleanup)
        self._check_limits()

    def cleanup_all(self):
        for name, (resource, cleanup) in self._resources.items():
            try:
                cleanup(resource)
            except Exception as e:
                logger.error(f"Cleanup failed for {name}: {e}")
```

### 3. Health Monitor

Continuous health checks:

```python
class HealthMonitor:
    def __init__(self):
        self._components = {}
        self._monitoring = False

    def register_component(self, name: str, check: Callable[[], bool]):
        self._components[name] = check

    def start_monitoring(self):
        self._monitoring = True
        threading.Thread(target=self._monitor_loop, daemon=False).start()

    def _monitor_loop(self):
        while self._monitoring:
            for name, check in self._components.items():
                try:
                    if not check():
                        logger.error(f"Health check failed: {name}")
                        # Trigger recovery
                except Exception as e:
                    logger.error(f"Health check error for {name}: {e}")

            time.sleep(5.0)
```

## Implementation Priority

### Phase 1: Critical Fixes (1-2 days)
1. Fix exception swallowing in detection threads
2. Add disk space monitoring
3. Fix codec fallback logic
4. Replace timeout daemon threads with ThreadPoolExecutor

### Phase 2: Error Handling (2-3 days)
5. Implement error event system
6. Add error propagation from threads
7. Add health monitoring
8. Implement recovery mechanisms

### Phase 3: Resource Management (2-3 days)
9. Implement resource manager
10. Add backpressure mechanism
11. Fix file descriptor leaks
12. Add cleanup guarantees

### Phase 4: Observability (1-2 days)
13. Add comprehensive metrics
14. Add performance monitoring
15. Add memory profiling
16. Create diagnostics dashboard

## Testing Strategy

### Unit Tests
- Test error handling in all worker threads
- Test timeout behavior with ThreadPoolExecutor
- Test codec fallback logic
- Test disk space monitoring

### Integration Tests
- Test full capture → detection → recording pipeline
- Test error recovery (camera disconnect/reconnect)
- Test disk full scenario
- Test memory limits

### Stress Tests
- Run 1-hour session and check for leaks
- Test with slow disk (simulated)
- Test with detection pipeline overload
- Test with high frame rate (120fps)

## Metrics to Track

### Operational Metrics
- Frames captured per camera per second
- Frames dropped (with reason: queue full, detection slow, etc.)
- Detection latency (p50, p95, p99)
- Write latency (p50, p95, p99)
- Disk space remaining
- Memory usage (RSS, heap)
- Thread count
- File descriptor count

### Error Metrics
- Error count by type (camera, detection, disk, etc.)
- Error rate per minute
- Time to recovery
- Silent failure detection rate

## Conclusion

The PitchTracker system has **significant brittleness** that must be addressed before production deployment:

1. **Silent failures**: System appears to work but data not captured
2. **Resource leaks**: Memory/file descriptor/thread leaks accumulate
3. **No monitoring**: Operators don't see problems until too late
4. **No recovery**: Transient errors become permanent failures

**Recommended Action:** Implement Phase 1 critical fixes immediately, then proceed with error handling and resource management improvements.

**Estimated Total Effort:** 6-10 days for complete hardening

**Risk if Not Fixed:** Data loss, user frustration, support burden, reputation damage
