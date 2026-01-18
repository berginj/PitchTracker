# Investigation Summary: High-Quality Video Capture

**Release Tagged**: v1.0.1 "Camera fixes"
**Investigation Branch**: `investigate/high-quality-capture`
**Date**: 2026-01-18

---

## Quick Start

To test your camera capabilities, run:

```bash
python test_camera_capabilities.py
```

This will generate a report at `camera_tests/capability_report.txt` showing:
- Which resolutions your cameras support
- Memory usage per resolution
- Whether dual-camera capture works at each resolution

---

## What Was Done

### 1. Tagged Current Version as v1.0.1

All camera fixes and workflow improvements have been tagged as **v1.0.1**:
- ✅ Restructured coaching workflow (setup → start recording)
- ✅ Camera detection increased to 10 cameras
- ✅ Mound distance presets (softball/baseball)
- ✅ Lane ROI adjustment dialog
- ✅ Settings dialog (resolution/camera/distance)
- ✅ Camera Capture Validator tool
- ✅ Session end bug fixes
- ✅ Video codec fallback (MJPG → XVID)

### 2. Created Investigation Branch

Branch: `investigate/high-quality-capture`

This branch contains:
- Comprehensive analysis document
- Test plan with 4 phases
- Automated test script
- Options and recommendations

### 3. Analyzed the Problem

**Why We Can't Use Higher Resolution:**

1. **Memory Allocation**
   - Config wants 1920x1080@60fps
   - OpenCV + DirectShow causes `bad allocation` error
   - Current workaround: Override to 640x480@30fps

2. **USB Bandwidth**
   - **USB 2.0**: Max ~400 Mbps practical
   - 1920x1080@60fps needs ~994 Mbps ❌
   - 1920x1080@30fps needs ~497 Mbps ❌
   - 1280x720@30fps needs ~221 Mbps ✅
   - 640x480@30fps needs ~74 Mbps ✅

3. **Backend Issues**
   - DirectShow (CAP_DSHOW) has memory issues at high res
   - Media Foundation (CAP_MSMF) may work better
   - Need to test both backends

---

## The Options

### ✅ Option 1: Stay at 640x480@30fps (Current)
**Status**: Working now

- Pros: Reliable, low memory, USB 2.0 compatible
- Cons: Lower detection accuracy
- **Who**: Use if you have USB 2.0 or want maximum reliability

### ⭐ Option 2: Upgrade to 1280x720@30fps (RECOMMENDED)
**Status**: Needs testing on your hardware

- Pros: **2.25x more pixels**, still USB 2.0 safe, best compromise
- Cons: Needs validation
- **Who**: **BEST FOR MOST USERS** - good quality without hardware requirements

### Option 3: Use 1920x1080@30fps
**Status**: Requires USB 3.0

- Pros: **6x more pixels**, professional quality
- Cons: **Requires USB 3.0**, higher memory
- **Who**: If you have USB 3.0 and want professional quality

### Option 4: Use 1920x1080@60fps (Target)
**Status**: Requires USB 3.0 + hardware upgrades

- Pros: Maximum quality and tracking precision
- Cons: **Requires USB 3.0 on separate controllers**, highest memory
- **Who**: Research-grade tracking, future goal

---

## What You Need to Do

### Step 1: Run the Test Script (15 minutes)

```bash
python test_camera_capabilities.py
```

This will tell you what your cameras can actually support.

### Step 2: Answer These Questions

1. **What cameras are you using?**
   - Manufacturer: _______________
   - Model: _______________
   - Spec sheet max resolution: _______________

2. **What USB ports?**
   - [ ] USB 2.0
   - [ ] USB 3.0
   - [ ] Mixed (some 2.0, some 3.0)
   - [ ] Don't know (check Device Manager → USB Controllers)

3. **What's your priority?**
   - [ ] Reliability (stay at 640x480)
   - [ ] Balanced (try 1280x720) ← **Recommended**
   - [ ] Quality (use 1920x1080 if hardware supports)

### Step 3: Review Test Results

After running the test, check `camera_tests/capability_report.txt`:

```
Common Supported Modes:
  - 640x480@30fps
  - 1280x720@30fps    ← If this appears, you can upgrade!
  - 1920x1080@30fps   ← If this appears, even better!
```

---

## Recommended Path Forward

### If 1280x720@30fps Works (Most Likely)

1. **Update default resolution** in coaching app settings
2. **Add auto-detection** to fallback to 640x480 if it fails
3. **Re-test detection accuracy** at higher resolution
4. **Benchmark performance** for 30-minute session

### If Only 640x480 Works

1. **Check USB version** - might be USB 2.0 bottleneck
2. **Try Media Foundation backend** (CAP_MSMF)
3. **Check if cameras support higher res** natively
4. **Consider camera upgrade** if you need better quality

### If 1920x1080 Works

1. **Verify you have USB 3.0**
2. **Test memory usage** for long sessions
3. **Benchmark detection pipeline** performance
4. **Document hardware requirements** for users

---

## Technical Details

### Memory Calculations

| Resolution | USB BW | Memory/Camera | Dual Memory |
|-----------|--------|---------------|-------------|
| 640x480@30 | 74 Mbps | ~50 MB | ~100 MB |
| 1280x720@30 | 221 Mbps | ~150 MB | ~300 MB |
| 1920x1080@30 | 497 Mbps | ~500 MB | ~1000 MB |
| 1920x1080@60 | 994 Mbps | ~1000 MB | ~2000 MB |

### Detection Quality Impact

Higher resolution = more pixels = better detection:
- 640x480 = 307,200 pixels (baseline)
- 1280x720 = 921,600 pixels (**+200%**)
- 1920x1080 = 2,073,600 pixels (**+575%**)

### Code Changes Needed

If testing shows 720p works:

```python
# In ui/coaching/coach_window.py
# Change from:
self._camera_width = state.get("coaching_width", 640)
self._camera_height = state.get("coaching_height", 480)

# To:
self._camera_width = state.get("coaching_width", 1280)
self._camera_height = state.get("coaching_height", 720)
```

---

## Files in Investigation Branch

1. **docs/INVESTIGATION_HIGH_QUALITY_CAPTURE.md** (40+ pages)
   - Complete analysis
   - Test plan (4 phases)
   - Decision matrix
   - Implementation guidance

2. **test_camera_capabilities.py**
   - Automated testing
   - Tests 10 resolution/framerate combinations
   - Tests both DirectShow and Media Foundation
   - Measures memory and effective FPS
   - Generates detailed report

3. **docs/INVESTIGATION_SUMMARY.md** (this file)
   - Quick start guide
   - High-level overview
   - Action items

---

## Next Steps After Testing

### If You Want to Upgrade Resolution

1. **Merge investigation branch** findings back to main
2. **Update default resolution** in coaching app
3. **Add resolution auto-detection** (script provided in investigation doc)
4. **Update documentation** with hardware requirements
5. **Re-test full coaching workflow** at new resolution

### If You Want Help

Reply with:
- Test results from `camera_tests/capability_report.txt`
- Camera model and USB version
- Your quality vs reliability preference

We can then:
- Recommend specific resolution
- Implement auto-detection
- Update coaching app defaults
- Add hardware requirement docs

---

## Summary

✅ **Current code tagged as v1.0.1**
✅ **Investigation branch created with full analysis**
✅ **Test script ready to run**
✅ **Four options documented with trade-offs**
⭐ **Recommended: Test 1280x720@30fps first** (best compromise)

**Next Action**: Run `python test_camera_capabilities.py` and share the results!

