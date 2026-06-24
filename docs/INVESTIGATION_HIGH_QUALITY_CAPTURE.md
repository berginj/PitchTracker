# Investigation: High-Quality Video Capture

**Branch**: `investigate/high-quality-capture`
**Version**: Based on v1.0.1
**Date**: 2026-01-18

## Problem Statement

The current system defaults to **640x480 @ 30fps** for coaching sessions, but the configuration specifies **1920x1080 @ 60fps**. When attempting to use the higher resolution, a `bad allocation` error occurs.

### Why This Matters

- **Detection accuracy** - Higher resolution provides more pixels for ball detection
- **Tracking precision** - Better frame rate captures more positions for trajectory
- **Analysis quality** - Higher quality video for review and debugging
- **Professional output** - Better recordings for coaching analysis

## Current State Analysis

### Configuration Intent (default.yaml)
```yaml
camera:
  width: 1920
  height: 1080
  fps: 60
  pixfmt: GRAY8
```

### Actual Usage
- **Coaching App**: 640x480 @ 30fps (overridden due to errors)
- **Calibration**: 640x480 @ 30fps
- **Validator**: 640x480 @ 30fps

### Known Issues

1. **Memory Allocation Failure**
   - Error: `bad allocation` when trying 1920x1080@60fps
   - Occurs with OpenCV backend using cv2.VideoCapture
   - Happens during camera initialization

2. **Backend Limitations**
   - Both OpenCV and UVC backends use cv2.VideoCapture + CAP_DSHOW
   - DirectShow on Windows has known memory and performance issues
   - No direct control over buffer allocation

3. **Hardware Constraints**
   - Typical webcams may not support 1920x1080@60fps
   - USB bandwidth limitations (especially USB 2.0)
   - Buffer allocation in OpenCV/DirectShow

## Investigation Goals

1. **Identify root cause** of allocation failure
2. **Determine maximum supported resolution/framerate** for target cameras
3. **Evaluate alternative approaches** for high-quality capture
4. **Provide actionable recommendations** with trade-offs

---

## Test Plan

### Phase 1: Hardware Capability Testing

**Objective**: Determine what your cameras actually support

#### Test 1.1: Query Supported Modes
```python
# Use capture validator with mode detection
# Add to ui/capture_validator.py

def _query_camera_modes(self, camera_index: str):
    """Query all supported camera modes."""
    cap = cv2.VideoCapture(int(camera_index), cv2.CAP_DSHOW)

    test_modes = [
        (640, 480, 30),
        (800, 600, 30),
        (1280, 720, 30),
        (1920, 1080, 30),
        (1280, 720, 60),
        (1920, 1080, 60),
    ]

    supported = []
    for width, height, fps in test_modes:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

        if actual_w == width and actual_h == height and actual_fps == fps:
            supported.append((width, height, fps))

    cap.release()
    return supported
```

**Expected Output**: List of actually supported resolutions/framerates

#### Test 1.2: Memory Allocation Test
```python
# Test memory allocation at different resolutions
# Run in isolation to measure actual memory usage

import psutil
import cv2

def test_memory_allocation(width, height, fps, duration_sec=5):
    """Test memory usage for specific camera mode."""
    process = psutil.Process()

    # Baseline memory
    baseline_mb = process.memory_info().rss / 1024 / 1024

    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        # Capture frames for duration
        start = time.time()
        frames_captured = 0
        while time.time() - start < duration_sec:
            ret, frame = cap.read()
            if ret:
                frames_captured += 1

        # Peak memory
        peak_mb = process.memory_info().rss / 1024 / 1024
        delta_mb = peak_mb - baseline_mb

        cap.release()

        return {
            'resolution': f'{width}x{height}@{fps}fps',
            'frames_captured': frames_captured,
            'baseline_mb': baseline_mb,
            'peak_mb': peak_mb,
            'delta_mb': delta_mb,
            'success': True
        }

    except Exception as e:
        return {
            'resolution': f'{width}x{height}@{fps}fps',
            'error': str(e),
            'success': False
        }
```

**Expected Output**: Memory usage profile per resolution

### Phase 2: Alternative Backend Investigation

**Objective**: Evaluate if alternative capture methods work better

#### Option A: Use CAP_MSMF Instead of CAP_DSHOW
```python
# Microsoft Media Foundation instead of DirectShow
cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
```

**Pros**:
- More modern Windows API
- Better memory management
- Better performance at high resolutions

**Cons**:
- Less device control
- May have compatibility issues with older cameras

#### Option B: Use PyCapture2 (FLIR/Point Grey SDK)
Only if using Point Grey/FLIR cameras.

**Pros**:
- Direct hardware access
- Best performance
- Full camera control

**Cons**:
- Requires specific camera hardware
- More complex setup
- Not general-purpose

#### Option C: Use Windows Media Foundation directly via Python
```python
# Use pymf or similar library for direct WMF access
```

**Pros**:
- More control than OpenCV wrapper
- Better high-res support

**Cons**:
- More complex implementation
- Dependency on Windows-specific library

#### Option D: Reduce Buffer Queue Depth
```python
# In config
camera:
  queue_depth: 2  # Instead of 6
```

**Pros**:
- Lower memory usage
- May allow higher resolutions

**Cons**:
- Higher chance of frame drops
- Less buffering for processing spikes

### Phase 3: Progressive Resolution Testing

**Objective**: Find the sweet spot between quality and reliability

#### Test 3.1: Incremental Resolution Test
Test in this order with BOTH backends (DSHOW and MSMF):

1. 640x480 @ 30fps (baseline - known working)
2. 800x600 @ 30fps
3. 1280x720 @ 30fps (720p)
4. 1280x720 @ 60fps
5. 1920x1080 @ 30fps (1080p)
6. 1920x1080 @ 60fps (target)

For each test:
- Measure memory usage
- Measure actual frame rate achieved
- Run for 60 seconds
- Record any errors or warnings
- Test with BOTH cameras simultaneously

#### Test 3.2: Dual-Camera Stress Test
```python
# Test both cameras at target resolution simultaneously
# This is the actual use case

def test_dual_camera(width, height, fps, duration_sec=60):
    """Test both cameras at same resolution."""
    left_cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    right_cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    for cap in [left_cap, right_cap]:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

    # Capture simultaneously for duration
    start = time.time()
    frames_left = 0
    frames_right = 0
    errors = 0

    while time.time() - start < duration_sec:
        ret_left, frame_left = left_cap.read()
        ret_right, frame_right = right_cap.read()

        if ret_left:
            frames_left += 1
        else:
            errors += 1

        if ret_right:
            frames_right += 1
        else:
            errors += 1

    left_cap.release()
    right_cap.release()

    return {
        'frames_left': frames_left,
        'frames_right': frames_right,
        'errors': errors,
        'effective_fps_left': frames_left / duration_sec,
        'effective_fps_right': frames_right / duration_sec,
    }
```

### Phase 4: USB Bandwidth Analysis

**Objective**: Understand USB bandwidth constraints

#### Calculations

**USB 2.0** (480 Mbps theoretical, ~400 Mbps practical)
- 1920x1080 grayscale @ 30fps = 1920×1080×1×30×8 = ~497 Mbps ❌ Exceeds USB 2.0
- 1280x720 grayscale @ 60fps = 1280×720×1×60×8 = ~442 Mbps ⚠️ Borderline
- 1280x720 grayscale @ 30fps = 1280×720×1×30×8 = ~221 Mbps ✅ Safe
- 640x480 grayscale @ 60fps = 640×480×1×60×8 = ~147 Mbps ✅ Safe

**USB 3.0** (5 Gbps theoretical, ~4 Gbps practical)
- 1920x1080 grayscale @ 60fps = 1920×1080×1×60×8 = ~994 Mbps ✅ Safe
- Both cameras @ 1920x1080@60fps = ~1988 Mbps ✅ Safe (on different USB 3.0 ports)

#### Test 4.1: USB Port Identification
```bash
# Windows: Use Device Manager to identify USB controller versions
# Look for "USB 3.0" or "xHCI" in device names
```

#### Test 4.2: Single Camera vs Dual Camera
Test if moving cameras to different USB controllers helps.

---

## Options & Recommendations

### Option 1: Stay with Current (640x480@30fps)
**Status**: ✅ Known working

**Pros**:
- Reliable and tested
- Works on all hardware
- Low memory footprint
- Compatible with USB 2.0

**Cons**:
- Lower detection accuracy
- Lower tracking precision
- Not using camera's full capability

**Recommendation**: Good for initial development and testing

### Option 2: Upgrade to 1280x720@30fps (720p)
**Status**: ⚠️ Needs testing

**Pros**:
- 2.25x more pixels than 640x480
- Still USB 2.0 compatible
- Better detection accuracy
- Reasonable memory usage

**Cons**:
- Needs validation on target hardware
- May need buffer tuning

**Recommendation**: **BEST COMPROMISE** - test this first

### Option 3: Use 1920x1080@30fps (1080p)
**Status**: ⚠️ Needs USB 3.0

**Pros**:
- 6x more pixels than 640x480
- Significantly better detection
- Professional quality recordings

**Cons**:
- **Requires USB 3.0**
- Higher memory usage (~2GB for both cameras)
- May need MSMF backend

**Recommendation**: Good target if USB 3.0 available

### Option 4: Use 1920x1080@60fps (Full Target)
**Status**: ⚠️ Needs USB 3.0 + Testing

**Pros**:
- Maximum quality
- Best tracking (more samples)
- Matches config intent

**Cons**:
- **Requires USB 3.0 on separate controllers**
- Highest memory usage (~4GB)
- May need MSMF backend
- May need camera hardware upgrades

**Recommendation**: Ultimate goal, requires hardware validation

### Option 5: Hybrid Approach
**Status**: 💡 Novel solution

**Strategy**: Use different resolutions for different purposes
- **Live preview**: 640x480@30fps (low latency, responsive UI)
- **Detection pipeline**: 1280x720@30fps (good accuracy, reasonable performance)
- **Recording**: 1920x1080@30fps (high quality for later analysis)

**Implementation**: Would require multi-stream capture or downsampling

**Pros**:
- Optimized for each use case
- Best user experience
- Best archive quality

**Cons**:
- More complex implementation
- May not be supported by all cameras

---

## Recommended Testing Sequence

### Week 1: Basic Validation
1. Run Test 1.1 on your actual cameras (query supported modes)
2. Run Test 1.2 for memory profiling
3. Identify USB controller versions (USB 2.0 vs 3.0)
4. Document camera hardware capabilities

### Week 2: Progressive Testing
1. Test 1280x720@30fps with CAP_DSHOW (dual cameras)
2. Test 1280x720@30fps with CAP_MSMF (dual cameras)
3. If successful, proceed to 1920x1080@30fps
4. Document which mode works reliably

### Week 3: Optimization
1. Tune buffer queue_depth for chosen resolution
2. Test detection pipeline performance at new resolution
3. Benchmark full coaching session at new resolution
4. Stress test for 30+ minutes continuous operation

### Week 4: Integration
1. Add resolution auto-detection to settings dialog
2. Add warning if resolution not supported
3. Add fallback logic (try high res, fall back to 640x480)
4. Update documentation

---

## Decision Matrix

| Resolution | USB | Memory | Detect Quality | Recommendation |
|-----------|-----|--------|----------------|----------------|
| 640x480@30 | 2.0 ✅ | Low | Baseline | Current |
| 1280x720@30 | 2.0 ✅ | Medium | +125% | **RECOMMENDED** |
| 1920x1080@30 | 3.0 ⚠️ | High | +500% | If USB 3.0 |
| 1920x1080@60 | 3.0 ⚠️ | Very High | +1000% | Future goal |

---

## Implementation Plan (If 720p Works)

### Step 1: Add Auto-Detection
```python
def detect_best_resolution(camera_index):
    """Auto-detect best supported resolution."""
    preferences = [
        (1920, 1080, 30),  # Try highest first
        (1280, 720, 30),   # Fallback to 720p
        (640, 480, 30),    # Safe fallback
    ]

    cap = cv2.VideoCapture(int(camera_index), cv2.CAP_DSHOW)
    for width, height, fps in preferences:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if actual_w == width and actual_h == height:
            cap.release()
            return (width, height, fps)

    cap.release()
    return (640, 480, 30)  # Ultimate fallback
```

### Step 2: Update Settings Dialog
Add "Auto-Detect Resolution" button that runs the detection and sets the best option.

### Step 3: Update Documentation
Document minimum hardware requirements for each quality tier.

---

## Questions to Answer

1. **What cameras are you using?**
   - Manufacturer and model
   - USB version (2.0 or 3.0)
   - Max resolution specification

2. **What USB ports are cameras connected to?**
   - Same USB controller or different?
   - USB 2.0 or USB 3.0 ports?

3. **What's your target quality?**
   - Acceptable: Fast and reliable (640x480)
   - Better: Good balance (1280x720) ← **Recommended**
   - Best: Professional (1920x1080)
   - Ultimate: Research-grade (1920x1080@60fps)

4. **What's your use case priority?**
   - Real-time coaching (lower latency preferred)
   - Later analysis (higher quality preferred)
   - Both (hybrid approach needed)

---

## Next Steps

1. **Run hardware capability tests** (Test 1.1 and 1.2)
2. **Document results** in this file
3. **Test 1280x720@30fps** as first upgrade target
4. **Decide on approach** based on results
5. **Implement auto-detection** if multiple resolutions needed
6. **Update coaching app** with new resolution support

---

## Test Results (To Be Filled)

### Hardware Information
```
Camera Model: _________________
USB Version: _________________
Max Resolution: _________________
USB Controller: _________________
```

### Supported Modes (Test 1.1)
```
Left Camera:
- [ ] 640x480@30fps
- [ ] 1280x720@30fps
- [ ] 1920x1080@30fps
- [ ] 1920x1080@60fps

Right Camera:
- [ ] 640x480@30fps
- [ ] 1280x720@30fps
- [ ] 1920x1080@30fps
- [ ] 1920x1080@60fps
```

### Memory Usage (Test 1.2)
```
640x480@30fps:   _____ MB
1280x720@30fps:  _____ MB
1920x1080@30fps: _____ MB
1920x1080@60fps: _____ MB
```

### Dual-Camera Test (Test 3.2)
```
Resolution: _________________
Effective FPS Left:  _____
Effective FPS Right: _____
Errors: _____
Success: [ ] Yes [ ] No
```

---

## Conclusion (To Be Determined)

Based on testing results, the recommended configuration is:

**Resolution**: _________________
**Backend**: _________________
**Rationale**: _________________

