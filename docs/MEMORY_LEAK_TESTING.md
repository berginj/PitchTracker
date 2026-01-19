# Memory Leak Testing Guide

**Date Created:** 2026-01-18
**Status:** Complete testing suite

---

## Overview

This document describes the comprehensive memory leak testing suite for PitchTracker. Memory leaks can cause the application to consume increasing amounts of RAM over time, eventually leading to performance degradation or crashes during long recording sessions.

---

## Test Suite Structure

### 1. Basic Resource Leak Tests

**File:** `tests/test_resource_leak_verification.py`

**Purpose:** Quick validation of basic resource management

**Tests:**
- ✅ `test_timeout_utils_no_thread_leak` - Timeout operations don't leak threads
- ✅ `test_timeout_utils_handles_timeouts_without_leak` - Timeout handling is clean
- ✅ `test_detection_pool_no_thread_leak` - Detection pool start/stop cleanup (10 cycles)
- ✅ `test_detection_pool_extended_operation` - Extended operation doesn't leak (1000 frames)
- ✅ `test_memory_stability_during_detection` - Short-term memory stability (2000 frames)

**Duration:** ~30 seconds
**When to run:** During development, CI/CD

**Usage:**
```bash
python -m pytest tests/test_resource_leak_verification.py -v
```

---

### 2. Extended Stress Tests

**File:** `tests/test_memory_stress.py`

**Purpose:** Long-duration tests to detect slow leaks

**Tests:**
- ✅ `test_detection_pipeline_extended_operation` - 5 minutes continuous operation
- ✅ `test_session_recorder_multiple_sessions` - 20 recording sessions
- ✅ `test_stereo_manager_extended_operation` - 5000 frame pairs
- ✅ `test_pitch_state_machine_multiple_pitches` - 100 complete pitches
- ✅ `test_rapid_start_stop_cycles` - 100 rapid start/stop cycles

**Duration:** ~10-15 minutes
**When to run:** Before releases, after major changes

**Requirements:**
```bash
pip install psutil
```

**Usage:**
```bash
# Run all stress tests
python -m pytest tests/test_memory_stress.py -v

# Run single test
python -m pytest tests/test_memory_stress.py::TestMemoryStressTests::test_detection_pipeline_extended_operation -v
```

---

### 3. Video Writer Leak Tests

**File:** `tests/test_video_writer_leaks.py`

**Purpose:** Detect leaks in video writing and camera lifecycle

**Tests:**
- ✅ `test_video_writer_create_destroy_cycles` - 50 video writer cycles (MJPG + XVID)
- ✅ `test_video_writer_large_file_cycles` - 10 large files (300 frames @ 1280x720)
- ✅ `test_simulated_camera_lifecycle` - 30 camera start/stop cycles
- ✅ `test_frame_buffer_management` - 10,000 frame create/destroy
- ✅ `test_concurrent_video_writers` - 20 concurrent writers (4 batches of 5)

**Duration:** ~5-8 minutes
**When to run:** After video/camera code changes

**Requirements:**
```bash
pip install psutil
```

**Usage:**
```bash
# Run all video writer tests
python -m pytest tests/test_video_writer_leaks.py -v

# Run specific test
python -m pytest tests/test_video_writer_leaks.py::TestVideoWriterLeaks::test_video_writer_create_destroy_cycles -v
```

---

## Memory Growth Thresholds

### Acceptable Memory Growth

| Test Duration | Acceptable Growth | Warning Threshold | Critical Threshold |
|---------------|-------------------|-------------------|-------------------|
| <1 minute | <5% | 5-10% | >10% |
| 5 minutes | <10% | 10-15% | >15% |
| 10+ minutes | <15% | 15-20% | >20% |

### Why Some Growth is Normal

**Expected memory growth:**
1. **Caching:** Detection results, frame buffers may be cached
2. **Python GC:** Objects waiting for garbage collection
3. **OS buffers:** System-level I/O buffering
4. **Library internals:** OpenCV, NumPy internal state

**Growth patterns indicating leaks:**
- **Linear growth:** Memory increases steadily over time
- **No stabilization:** Growth continues without plateau
- **Cycle correlation:** Growth per operation cycle
- **No GC recovery:** Memory doesn't drop after garbage collection

---

## Running the Complete Suite

### Quick Validation

**For CI/CD and rapid development:**
```bash
# Basic tests only (~30 seconds)
python -m pytest tests/test_resource_leak_verification.py -v
```

### Pre-Release Validation

**Before releasing a new version:**
```bash
# All leak tests (~15-20 minutes)
python -m pytest tests/test_resource_leak_verification.py tests/test_memory_stress.py tests/test_video_writer_leaks.py -v
```

### Comprehensive Testing

**After major architectural changes:**
```bash
# All tests + performance benchmarks (~25-30 minutes)
python -m pytest tests/test_resource_leak_verification.py tests/test_memory_stress.py tests/test_video_writer_leaks.py -v
python -m benchmarks.run_all
```

---

## Interpreting Test Results

### Test Passes (✅)

```
test_detection_pipeline_extended_operation PASSED
Initial memory: 145.3 MB
  [  60s]   148.1 MB (+  2.8 MB, + 1.9%)
  [ 120s]   149.7 MB (+  4.4 MB, + 3.0%)
  [ 180s]   150.2 MB (+  4.9 MB, + 3.4%)
  [ 240s]   151.1 MB (+  5.8 MB, + 4.0%)
  [ 300s]   152.8 MB (+  7.5 MB, + 5.2%)

Final: 145.3 MB → 152.8 MB (+7.5 MB, +5.2%)
✅ PASS: Memory stable over extended operation
```

**Interpretation:**
- Memory growth is 5.2% over 5 minutes
- Growth is gradual and stabilizing
- Well below 10% threshold
- **Verdict:** No leak detected

### Test Warning (⚠️)

```
test_session_recorder_multiple_sessions WARNING
Initial memory: 134.5 MB
  Session  5:   142.3 MB (+  7.8 MB, + 5.8%)
  Session 10:   148.1 MB (+ 13.6 MB, +10.1%)
  Session 15:   152.7 MB (+ 18.2 MB, +13.5%)
  Session 20:   156.4 MB (+ 21.9 MB, +16.3%)

Final: 134.5 MB → 156.4 MB (+21.9 MB, +16.3%)
```

**Interpretation:**
- Memory growth is 16.3% over 20 sessions
- Growth appears linear (not stabilizing)
- Above 15% warning threshold but below 20% critical
- **Verdict:** Possible slow leak, investigate

**Actions:**
1. Review SessionRecorder cleanup code
2. Check for unreleased video writers
3. Verify frame references are released
4. Run extended test (50+ sessions) to confirm trend

### Test Failure (❌)

```
test_rapid_start_stop_cycles FAILED
Initial: 128.3 MB, 12 threads
  Cycle  20:   145.7 MB (+ 17.4 MB, +13.6%), 14 threads (+2)
  Cycle  40:   162.8 MB (+ 34.5 MB, +26.9%), 16 threads (+4)
  Cycle  60:   179.3 MB (+ 51.0 MB, +39.8%), 18 threads (+6)
  Cycle  80:   195.1 MB (+ 66.8 MB, +52.1%), 20 threads (+8)
  Cycle 100:   210.4 MB (+ 82.1 MB, +64.0%), 22 threads (+10)

Final: 128.3 MB → 210.4 MB (+82.1 MB, +64.0%)
Threads: 12 → 22 (+10 threads)

AssertionError: Memory grew 64.0% after 100 cycles. Possible leak.
❌ FAIL
```

**Interpretation:**
- Severe memory leak: 64% growth
- Thread leak: 10 threads not cleaned up
- Linear growth per cycle
- **Verdict:** Critical leak, must fix before release

**Actions:**
1. Check ThreadPoolExecutor.shutdown() is called
2. Verify all threads are properly joined
3. Review frame buffer cleanup
4. Use memory profiler to find leak source

---

## Debugging Memory Leaks

### Step 1: Identify the Leak

**Use memory profiler:**
```bash
pip install memory-profiler
python -m memory_profiler tests/test_memory_stress.py
```

**Or use tracemalloc:**
```python
import tracemalloc

tracemalloc.start()

# Run leaky code
for i in range(1000):
    create_and_process_frame()

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

### Step 2: Common Leak Sources

**1. Unreleased Video Writers**
```python
# BAD: Writer not released
writer = cv2.VideoWriter(...)
writer.write(frame)
# Missing: writer.release()

# GOOD: Proper cleanup
writer = cv2.VideoWriter(...)
try:
    writer.write(frame)
finally:
    writer.release()
```

**2. Circular References**
```python
# BAD: Circular reference
class Pipeline:
    def __init__(self):
        self.callback = lambda: self.process()  # Captures self

# GOOD: Break the cycle
class Pipeline:
    def __init__(self):
        self.callback = None

    def cleanup(self):
        self.callback = None  # Break reference
```

**3. Frame References in Callbacks**
```python
# BAD: Frame captured in closure
frames = []
def process_frame(frame):
    frames.append(frame)  # Accumulates forever

# GOOD: Don't store references
def process_frame(frame):
    result = detect(frame)
    # Frame goes out of scope
    return result
```

**4. Thread-Local Storage**
```python
# BAD: Thread-local accumulation
thread_local = threading.local()
thread_local.frames = []  # Never cleared

# GOOD: Clear thread-local data
def cleanup_thread():
    if hasattr(thread_local, 'frames'):
        thread_local.frames.clear()
```

### Step 3: Verify the Fix

**After fixing:**
1. Run the failing test again
2. Run extended stress test
3. Monitor memory during manual testing
4. Commit with clear description of fix

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Memory Leak Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  leak-tests:
    runs-on: windows-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install psutil pytest

      - name: Run basic leak tests
        run: |
          python -m pytest tests/test_resource_leak_verification.py -v

      - name: Run stress tests (on main branch only)
        if: github.ref == 'refs/heads/main'
        run: |
          python -m pytest tests/test_memory_stress.py -v
          python -m pytest tests/test_video_writer_leaks.py -v
```

### Pre-Commit Hook

**Create `.git/hooks/pre-commit`:**
```bash
#!/bin/bash
echo "Running memory leak checks..."
python -m pytest tests/test_resource_leak_verification.py -q

if [ $? -ne 0 ]; then
    echo "Memory leak tests failed. Commit aborted."
    exit 1
fi

echo "Memory leak checks passed."
exit 0
```

---

## Real-World Testing

### Manual Long-Duration Test

**Procedure:**
1. Launch PitchTracker application
2. Start camera capture
3. Record multiple sessions (1 hour+)
4. Monitor Task Manager / Activity Monitor
5. Look for steady RAM increase

**What to monitor:**
- **Working Set:** Active memory usage
- **Private Bytes:** Memory owned by process
- **Handles:** Should remain stable

**Expected behavior:**
- Initial spike (warmup, caching)
- Stabilization after ~5 minutes
- Slight growth during recording
- Return to baseline after stopping

**Red flags:**
- Linear growth over time
- No stabilization
- Growth continues when idle
- Memory doesn't drop after stopping

### Production Monitoring

**Add telemetry to track memory:**
```python
import psutil
import logging

class MemoryMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = self.get_memory_mb()
        self.peak_memory = self.initial_memory

    def get_memory_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def check(self):
        current = self.get_memory_mb()
        if current > self.peak_memory:
            self.peak_memory = current

        growth = current - self.initial_memory
        growth_pct = (growth / self.initial_memory) * 100

        if growth_pct > 30:
            logging.warning(
                f"High memory growth: {growth_pct:.1f}% "
                f"({self.initial_memory:.1f} MB → {current:.1f} MB)"
            )

# Use in application
monitor = MemoryMonitor()
# Check every 60 seconds
QTimer.singleShot(60000, monitor.check)
```

---

## Troubleshooting Test Failures

### "psutil not available" Error

**Solution:**
```bash
pip install psutil
```

### Tests Time Out

**Possible causes:**
- System under heavy load
- Detection taking too long
- Deadlock in threading

**Solutions:**
1. Close other applications
2. Increase timeout thresholds
3. Check for thread deadlocks

### Inconsistent Results

**Causes:**
- Background processes consuming memory
- Antivirus scanning
- Windows Update
- Python GC timing

**Solutions:**
1. Run multiple times and average
2. Disable background tasks
3. Use dedicated test machine
4. Explicitly trigger GC: `gc.collect()`

### Test Passes Locally, Fails in CI

**Possible reasons:**
- Different Python version
- Different dependency versions
- Different available memory
- Timing-sensitive race conditions

**Solutions:**
1. Match CI environment locally (use Docker)
2. Check dependency versions
3. Add retry logic for timing-sensitive tests
4. Increase thresholds slightly for CI

---

## Memory Optimization Tips

### 1. Minimize Frame Copies

```python
# BAD: Unnecessary copy
frame_copy = frame.image.copy()
process(frame_copy)

# GOOD: Process in-place or reference
process(frame.image)
```

### 2. Release Large Objects Early

```python
# BAD: Keep frame reference
def process_batch(frames):
    results = [detect(f) for f in frames]
    return results  # frames still referenced

# GOOD: Release frames ASAP
def process_batch(frames):
    results = []
    for frame in frames:
        results.append(detect(frame))
        del frame  # Explicit release
    return results
```

### 3. Limit Cache Sizes

```python
# BAD: Unbounded cache
cache = {}
def get_processed(key):
    if key not in cache:
        cache[key] = expensive_operation(key)
    return cache[key]

# GOOD: LRU cache with size limit
from functools import lru_cache

@lru_cache(maxsize=128)
def get_processed(key):
    return expensive_operation(key)
```

### 4. Clear Collections Periodically

```python
# In long-running loops
if len(results_buffer) > 1000:
    results_buffer.clear()
    gc.collect()
```

---

## Summary

**Memory Leak Testing Suite:** ✅ Complete

**Test Coverage:**
- ✅ Thread leak detection
- ✅ Short-term memory stability (30s-2min)
- ✅ Long-term memory stability (5-10min)
- ✅ Video writer lifecycle
- ✅ Camera capture lifecycle
- ✅ Frame buffer management
- ✅ Concurrent operation
- ✅ Rapid start/stop cycles

**Total Tests:** 15 memory leak tests

**Running Time:**
- Quick validation: ~30 seconds
- Complete suite: ~15-20 minutes

**Usage:**
```bash
# Quick check during development
python -m pytest tests/test_resource_leak_verification.py -v

# Pre-release validation
python -m pytest tests/test_resource_leak_verification.py tests/test_memory_stress.py tests/test_video_writer_leaks.py -v
```

**Memory Growth Limits:**
- Short-term (<1 min): <5%
- Medium-term (5 min): <10%
- Long-term (10+ min): <15%

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Next Review:** After any memory-related changes
