# PitchTracker Performance Benchmarks

**Date Created:** 2026-01-18
**Status:** Benchmarking suite complete, baseline measurements pending

---

## Overview

This document describes the performance benchmarking suite for PitchTracker and provides baseline performance metrics for the detection pipeline.

The benchmark suite measures three critical performance dimensions:
1. **Throughput** - Frames per second (FPS) through the detection pipeline
2. **Latency** - Time from frame capture to detection result (p50, p95, p99)
3. **Memory Stability** - Memory usage over extended operation (leak detection)

---

## Performance Targets

### Critical Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Throughput** | ≥60 FPS | Real-time video processing (60 Hz cameras) |
| **Latency (p95)** | <20ms | Responsive UI and real-time feedback |
| **Memory Growth** | <10% over 5 min | Stable long-term operation |

### Performance Tiers

**Excellent Performance:**
- Throughput: >120 FPS
- Latency p95: <10ms
- Memory growth: <5% over 5 minutes

**Good Performance:**
- Throughput: 60-120 FPS
- Latency p95: 10-20ms
- Memory growth: 5-10% over 5 minutes

**Acceptable Performance:**
- Throughput: 40-60 FPS (may drop frames under load)
- Latency p95: 20-30ms (noticeable lag)
- Memory growth: 10-20% over 5 minutes (watch for leaks)

**Unacceptable Performance:**
- Throughput: <40 FPS (unable to keep up with video)
- Latency p95: >30ms (significant lag)
- Memory growth: >20% over 5 minutes (likely memory leak)

---

## Benchmark Suite

### 1. Throughput Benchmark

**File:** `benchmarks/throughput.py`

**What it measures:**
- Frames per second through the detection pipeline
- Frame processing time (milliseconds per frame)
- Performance at different resolutions

**Test configurations:**
- 1000 frames at 1280x720 (default)
- Multiple resolutions: VGA (640x480), HD 720p (1280x720), Full HD 1080p (1920x1080)
- Queue size: 6 frames

**Usage:**
```bash
# Single resolution test
python -m benchmarks.throughput --frames 1000 --width 1280 --height 720

# Test all resolutions
python -m benchmarks.throughput --all-resolutions
```

**Output example:**
```
Frame Processing Throughput Benchmark
Configuration:
  Frames: 1000
  Resolution: 1280x720
  Queue Size: 6

Results:
  Frames Processed: 1000
  Total Time: 8.34 seconds
  Throughput: 119.90 FPS
  Frame Time: 8.34 ms/frame
  Target: 60 FPS minimum
  Status: ✅ PASS
```

**Interpretation:**
- **FPS ≥ 60:** System can handle real-time video
- **FPS 40-60:** May drop frames under load
- **FPS < 40:** Performance issue, investigate bottlenecks

---

### 2. Latency Benchmark

**File:** `benchmarks/latency.py`

**What it measures:**
- Detection latency distribution (min, p50, p75, p90, p95, p99, max)
- Latency under sustained high load
- Tail latency (worst-case scenarios)

**Test configurations:**
- 1000 frames with latency measurement per frame
- Latency under load: 500 frames sent as fast as possible
- Resolution: 1280x720

**Usage:**
```bash
# Normal latency test
python -m benchmarks.latency --frames 1000

# Include under-load test
python -m benchmarks.latency --frames 1000 --under-load
```

**Output example:**
```
Detection Latency Benchmark
Results:
  Frames Measured: 1000
  Resolution: 1280x720

  Latency Statistics (milliseconds):
    Min:      3.21 ms
    P50:      8.45 ms (median)
    P75:     11.32 ms
    P90:     14.67 ms
    P95:     16.89 ms
    P99:     22.45 ms
    Max:     28.91 ms
    Mean:     9.12 ms

  Target: <20ms p95 latency
  Status: ✅ PASS
```

**Interpretation:**
- **P50 (median):** Typical latency for most frames
- **P95:** 95% of frames processed within this time (key metric)
- **P99:** Worst-case latency (excluding outliers)
- **Max:** Absolute worst-case (may include GC pauses)

**What to watch for:**
- P95 > 20ms: Users may notice lag
- P99 > 50ms: Significant tail latency issues
- Max > 100ms: Investigate long pauses (GC, I/O blocking)

---

### 3. Memory Stability Benchmark

**File:** `benchmarks/memory.py`

**What it measures:**
- Memory usage over extended operation (5+ minutes)
- Memory growth rate (indicates leaks)
- Memory behavior during rapid start/stop cycles

**Test configurations:**
- **Stability test:** 5 minutes of continuous operation, sampling every 10 seconds
- **Rapid cycling test:** 100 start/stop cycles with memory sampling

**Requirements:**
- Python package: `psutil` (install with `pip install psutil`)

**Usage:**
```bash
# 5-minute stability test
python -m benchmarks.memory --duration 300 --interval 10

# 1-minute quick test
python -m benchmarks.memory --duration 60 --interval 10

# Rapid cycling test
python -m benchmarks.memory --rapid-cycling --cycles 100
```

**Output example:**
```
Memory Stability Benchmark
Configuration:
  Duration: 300 seconds (5.0 minutes)
  Sample Interval: 10 seconds
  Resolution: 1280x720

Initial memory: 145.3 MB
Starting 300s stability test...

  [   10s] Memory:   148.1 MB (+  2.8 MB, + 1.9%)
  [   20s] Memory:   149.7 MB (+  4.4 MB, + 3.0%)
  [   30s] Memory:   150.2 MB (+  4.9 MB, + 3.4%)
  ...
  [  300s] Memory:   152.8 MB (+  7.5 MB, + 5.2%)

Results:
  Duration: 300 seconds
  Frames Processed: 17,854

  Memory Usage:
    Initial:    145.3 MB
    Final:      152.8 MB
    Max:        153.2 MB

  Memory Growth:
    Final:    +   7.5 MB (+ 5.2%)
    Peak:     +   7.9 MB (+ 5.4%)

  Target: <10% growth over test duration
  Status: ✅ PASS (memory stable)
```

**Interpretation:**
- **<5% growth:** Excellent, no memory leak
- **5-10% growth:** Acceptable, likely caching/buffers
- **10-20% growth:** Warning, possible slow leak
- **>20% growth:** Likely memory leak, investigate immediately

**Memory leak indicators:**
- Steady linear growth over time
- Growth continues after warmup period
- Growth in rapid cycling test (start/stop should release memory)

---

## Running All Benchmarks

**File:** `benchmarks/run_all.py`

**What it does:**
- Runs all three benchmark suites
- Generates comprehensive report
- Saves results to JSON for tracking over time

**Usage:**
```bash
# Full benchmark suite (takes ~10-15 minutes)
python -m benchmarks.run_all

# Quick mode (takes ~3-5 minutes, shorter tests)
python -m benchmarks.run_all --quick

# Don't save results to file
python -m benchmarks.run_all --no-save
```

**Output:**
- Console output with detailed results for each benchmark
- Summary report with overall assessment
- JSON results file saved to `benchmarks/results/benchmark_results_YYYYMMDD_HHMMSS.json`

**Interpreting the summary:**
```
OVERALL ASSESSMENT:
✅ ALL BENCHMARKS PASSED

The system meets all performance targets:
  • Throughput: ≥60 FPS
  • Latency: <20ms p95
  • Memory: <10% growth
```

---

## Baseline Performance

**Status:** ⏸️ Pending - Baseline measurements not yet established

**To establish baseline:**
1. Run on reference hardware configuration
2. Document system specifications
3. Run full benchmark suite (not quick mode)
4. Record results in this section

**Reference Hardware (TBD):**
```
CPU: [TBD]
RAM: [TBD]
GPU: [TBD] (if using GPU acceleration)
OS: Windows 10/11
Python: 3.11+
```

**Expected Performance (TBD):**
```
Throughput:
  • 720p: [TBD] FPS
  • 1080p: [TBD] FPS

Latency:
  • P50: [TBD] ms
  • P95: [TBD] ms
  • P99: [TBD] ms

Memory:
  • Initial: [TBD] MB
  • Growth: [TBD]% over 5 minutes
```

---

## Performance Optimization Guide

### If Throughput is Low (<60 FPS)

**Possible causes:**
1. **CPU-bound:** Detection algorithm too slow
2. **I/O-bound:** Disk writes blocking
3. **Thread contention:** Too much locking
4. **Resolution too high:** 1080p may be too demanding

**Optimization strategies:**
1. **Profile the detection pipeline:**
   ```python
   import cProfile
   cProfile.run('detector.detect(frame)', sort='cumtime')
   ```

2. **Reduce detection workload:**
   - Lower resolution (1280x720 instead of 1920x1080)
   - Reduce color space processing
   - Optimize filter chains

3. **Increase thread pool size:**
   - DetectionThreadPool queue_size parameter
   - More worker threads (if CPU has cores available)

4. **Enable hardware acceleration:**
   - GPU-accelerated OpenCV operations
   - Check cv2.cuda availability

### If Latency is High (p95 >20ms)

**Possible causes:**
1. **Detection algorithm too complex**
2. **Queue backlog:** Frames waiting in queue
3. **GC pauses:** Python garbage collection
4. **Thread scheduling delays**

**Optimization strategies:**
1. **Reduce per-frame work:**
   - Simplify detection logic
   - Cache expensive computations
   - Use lookup tables

2. **Optimize queue handling:**
   - Reduce queue_size to minimize buffering
   - Use priority queue for time-critical frames

3. **Tune GC:**
   ```python
   import gc
   gc.set_threshold(700, 10, 10)  # Reduce GC frequency
   ```

4. **Thread priority:**
   - Increase detection thread priority (OS-level)

### If Memory is Growing (>10% over 5 minutes)

**Possible causes:**
1. **Frame references not released**
2. **Circular references in objects**
3. **Global caches growing unbounded**
4. **Thread-local storage accumulating**

**Debugging strategies:**
1. **Use memory profiler:**
   ```bash
   pip install memory-profiler
   python -m memory_profiler benchmarks/memory.py
   ```

2. **Track object counts:**
   ```python
   import gc
   print(gc.get_count())  # Generation counts
   for obj in gc.get_objects():
       print(type(obj))
   ```

3. **Check for circular references:**
   ```python
   import gc
   gc.set_debug(gc.DEBUG_LEAK)
   ```

4. **Review object lifecycle:**
   - Ensure frame objects are released after processing
   - Clear detection result caches periodically
   - Close video writers properly

---

## CI/CD Integration

### Automated Performance Testing

**Recommendation:** Run benchmarks in CI/CD to detect performance regressions

**GitHub Actions example:**
```yaml
name: Performance Benchmarks

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  benchmark:
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
          pip install psutil

      - name: Run benchmarks (quick mode)
        run: |
          python -m benchmarks.run_all --quick

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: benchmarks/results/
```

### Performance Regression Detection

**Store baseline results and compare:**
```python
import json

def check_regression(current_results, baseline_results, tolerance=0.1):
    """Check if performance regressed by more than tolerance (10% default)."""
    current_fps = current_results["benchmarks"]["throughput"]["single_resolution"]["fps"]
    baseline_fps = baseline_results["benchmarks"]["throughput"]["single_resolution"]["fps"]

    regression = (baseline_fps - current_fps) / baseline_fps

    if regression > tolerance:
        raise ValueError(f"Performance regression: {regression*100:.1f}% slower than baseline")
```

---

## Benchmark Results Archive

**Location:** `benchmarks/results/`

**Format:** JSON files named `benchmark_results_YYYYMMDD_HHMMSS.json`

**Retention:** Keep results to track performance over time and detect regressions

**Recommended workflow:**
1. Run benchmarks before and after optimization work
2. Compare results to validate improvements
3. Archive representative results for each release
4. Track performance trends over multiple releases

---

## Troubleshooting Benchmarks

### "psutil not available" Error

**Cause:** Memory benchmarks require psutil package

**Fix:**
```bash
pip install psutil
```

### Benchmark Times Out or Crashes

**Possible causes:**
1. Test duration too long for available memory
2. Detection callback raising exceptions
3. Thread pool not stopping cleanly

**Solutions:**
1. Use `--quick` mode for faster tests
2. Check detector configuration is valid
3. Ensure ThreadPoolExecutor cleanup is working

### Inconsistent Results

**Causes:**
1. System under load from other processes
2. CPU throttling (thermal)
3. Background tasks (Windows Update, antivirus)

**Best practices:**
1. Close other applications before benchmarking
2. Disable background tasks
3. Run multiple times and take average
4. Use dedicated benchmark machine for consistent results

---

## Future Enhancements

### Potential Additions

1. **GPU Benchmark** - Measure GPU utilization and acceleration benefit
2. **Network Latency** - If adding remote processing
3. **Disk I/O Benchmark** - Measure video write performance
4. **Multi-camera Stress Test** - Performance with 3+ camera pairs
5. **Power Consumption** - Battery life impact on laptops

### Benchmark Visualization

**Generate charts from results:**
```python
import matplotlib.pyplot as plt
import json

with open('benchmark_results_20260118_120000.json', 'r') as f:
    results = json.load(f)

# Plot latency distribution
latencies = results['benchmarks']['latency']['normal']
plt.hist(latencies, bins=50)
plt.xlabel('Latency (ms)')
plt.ylabel('Frequency')
plt.title('Detection Latency Distribution')
plt.savefig('latency_distribution.png')
```

---

## Summary

**Benchmark Suite Status:** ✅ Complete

**Components:**
- ✅ Throughput benchmark (`throughput.py`)
- ✅ Latency benchmark (`latency.py`)
- ✅ Memory stability benchmark (`memory.py`)
- ✅ Comprehensive test runner (`run_all.py`)
- ✅ Documentation (this file)

**Next Steps:**
1. Run benchmarks on reference hardware
2. Establish baseline performance metrics
3. Document baseline in this file
4. Set up CI/CD integration for regression detection
5. Run benchmarks after major performance changes

**Performance Targets:**
- Throughput: ≥60 FPS ✅
- Latency: <20ms p95 ✅
- Memory: <10% growth over 5 minutes ✅

**Usage:**
```bash
# Run full benchmark suite
python -m benchmarks.run_all

# Quick validation
python -m benchmarks.run_all --quick
```

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Maintainer:** PitchTracker Development Team
