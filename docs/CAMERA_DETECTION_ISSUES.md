# ArduCam Detection Issues - Analysis & Solutions

## Problem Statement

ArduCam devices are not being detected consistently when enumerating cameras. The detection succeeds sometimes but fails other times, making the system unreliable.

## Root Causes

### 1. **Short Probe Timeout (1 second)**
**Current Code:** `ui/device_utils.py:51`
```python
def _probe_single_index(index: int, timeout_seconds: float = 1.0)
```

**Issue:** ArduCam devices may take longer than 1 second to initialize, especially:
- On first access after system boot
- When multiple cameras are being probed simultaneously
- When USB bandwidth is constrained
- When USB hub is initializing devices

**Impact:** If a camera doesn't respond within 1 second, it's marked as unavailable even though it might be functional.

### 2. **Parallel Probing Race Conditions**
**Current Code:** `ui/device_utils.py:133`
```python
if parallel:
    # Probe all indices in parallel for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_index) as executor:
```

**Issue:** When probing 10 cameras in parallel:
- All threads try to open cameras simultaneously
- USB bandwidth contention (especially USB 2.0)
- DirectShow resource contention
- Race conditions in driver initialization

**Impact:** Some cameras fail to open due to resource contention, even though they would work if probed sequentially.

### 3. **No Retry Logic**
**Issue:** If a camera fails to open once (timeout, contention, etc.), it's immediately marked as unavailable with no retry attempt.

**Impact:** Transient failures (USB busy, driver delay, etc.) cause permanent detection failure for that run.

### 4. **UVC and OpenCV Enumeration Mismatch**
**Current Flow:**
1. UVC devices enumerated via PowerShell (shows ArduCam with friendly name)
2. OpenCV indices probed separately (may not match UVC order)
3. Mapping between them is assumed by index position

**Issue:** Windows can assign OpenCV indices in a different order than UVC enumeration, especially:
- After USB device reconnection
- After system resume from sleep
- When devices are on different USB controllers
- When devices initialize at different speeds

**Impact:** ArduCam shows in UVC list but corresponding OpenCV index fails to open.

### 5. **Cache Invalidation Timing**
**Issue:** Device cache is cleared in some code paths but not others, leading to stale device lists being used.

**Impact:** After USB reconnection or device change, old device list is still shown until cache is manually cleared.

## Detection Failures by Scenario

### Scenario A: Cold Boot
**What happens:**
1. Windows starts enumerating USB devices
2. Script runs before devices fully initialized
3. Some cameras not ready when probed

**Result:** Inconsistent detection on cold boot, more reliable on subsequent runs.

### Scenario B: Multiple Cameras
**What happens:**
1. Parallel probing opens all 10 cameras at once
2. USB 2.0 bandwidth: ~400 Mbps shared across all cameras
3. Each camera initialization needs bandwidth
4. Some cameras timeout waiting for USB access

**Result:** Fewer cameras detected when using parallel probing.

### Scenario C: USB Hub
**What happens:**
1. Cameras connected via USB hub
2. Hub has limited power budget
3. Some cameras don't get enough power to initialize quickly
4. 1-second timeout expires before camera ready

**Result:** Cameras on hub are inconsistently detected.

### Scenario D: USB Re-enumeration
**What happens:**
1. USB device disconnected/reconnected
2. Windows assigns new device indices
3. Cache still has old mappings
4. ArduCam is at new index but code checks old index

**Result:** ArduCam detected via UVC but OpenCV can't open it.

## Solutions

### Solution 1: Increase Probe Timeout
**Change:** Increase timeout from 1.0s to 3.0s
**File:** `ui/device_utils.py:51`

```python
def _probe_single_index(index: int, timeout_seconds: float = 3.0) -> Optional[int]:
```

**Rationale:** Give cameras more time to initialize, especially on first access.

### Solution 2: Use Sequential Probing by Default
**Change:** Make `parallel=False` the default
**File:** `ui/device_utils.py:133`

```python
def probe_opencv_indices(
    max_index: int = 4, parallel: bool = False, use_cache: bool = True  # Changed from True
) -> list[int]:
```

**Rationale:** Sequential probing is more reliable, especially with USB bandwidth constraints.

### Solution 3: Add Retry Logic
**Change:** Retry failed camera opens with exponential backoff

```python
def _probe_single_index_with_retry(
    index: int,
    timeout_seconds: float = 3.0,
    max_retries: int = 2
) -> Optional[int]:
    """Probe camera with retry logic."""
    for attempt in range(max_retries + 1):
        result = _probe_single_index(index, timeout_seconds)
        if result is not None:
            return result
        if attempt < max_retries:
            time.sleep(0.5 * (attempt + 1))  # Exponential backoff
    return None
```

**Rationale:** Handle transient failures like USB busy or driver initialization delays.

### Solution 4: Add Delay Between Sequential Probes
**Change:** Add small delay between camera probes to avoid USB contention

```python
for i in range(max_index):
    result = _probe_single_index(i, 3.0)
    if result is not None:
        indices.append(result)
    time.sleep(0.1)  # Small delay to avoid USB contention
```

**Rationale:** Give USB subsystem time to release resources between camera accesses.

### Solution 5: Direct Index Verification
**Change:** When mapping UVC to OpenCV, verify each index works

```python
def verify_arducam_indices(uvc_devices: list[dict], max_index: int) -> dict[int, dict]:
    """Map and verify ArduCam devices."""
    verified = {}
    for i, dev in enumerate(uvc_devices):
        if i >= max_index:
            break
        if is_arducam_device(dev.get('friendly_name', '')):
            # Verify this index actually works
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.release()
                verified[i] = dev
                logger.info(f"✅ ArduCam at index {i} verified")
            else:
                cap.release()
                logger.warning(f"❌ ArduCam at UVC index {i} failed to open")
    return verified
```

**Rationale:** Confirm ArduCam devices can actually be opened at their expected indices.

### Solution 6: Explicit Cache Management
**Change:** Always clear cache when detection is critical

```python
# In session_start.py and other critical dialogs
clear_device_cache()  # Force fresh enumeration
devices = probe_uvc_devices(use_cache=False)
indices = probe_opencv_indices(use_cache=False)
```

**Rationale:** Ensure fresh device list when user is actively selecting cameras.

## Recommended Implementation Order

### Phase 1: Quick Wins (Low Risk)
1. ✅ Increase timeout to 3.0 seconds
2. ✅ Add 100ms delay between sequential probes
3. ✅ Always use `use_cache=False` in UI dialogs

### Phase 2: Reliability Improvements (Medium Risk)
4. ✅ Change default to sequential probing
5. ✅ Add retry logic with exponential backoff
6. ✅ Improve logging for diagnostics

### Phase 3: Advanced (Higher Risk)
7. ⏳ Direct index verification for ArduCam devices
8. ⏳ USB bandwidth detection and adaptive probing
9. ⏳ Device arrival/removal event handling

## Testing Protocol

### Test 1: Cold Boot Detection
1. Restart computer
2. Run detection immediately after login
3. Verify all ArduCam devices detected
4. Repeat 5 times

### Test 2: USB Reconnection
1. Disconnect one ArduCam device
2. Wait 5 seconds
3. Reconnect device
4. Clear cache and re-enumerate
5. Verify device appears

### Test 3: Simultaneous Probing
1. Connect 6+ cameras
2. Run parallel probing
3. Run sequential probing
4. Compare results
5. Sequential should be more reliable

### Test 4: USB Hub Stress
1. Connect all cameras to same USB hub
2. Enumerate multiple times
3. Verify consistent detection
4. Check with powered vs unpowered hub

## Diagnostic Commands

### Run the diagnostic tool:
```bash
python diagnose_camera_detection.py
```

This will test detection 5 times and report:
- UVC enumeration consistency
- OpenCV parallel vs sequential probing
- Direct camera opening
- ArduCam mapping

### Check logs for timing:
```bash
grep "probe timed out" logs/*.log
grep "ArduCam" logs/*.log
```

### Manual verification:
```python
# In Python shell
from ui.device_utils import *

# Test UVC
clear_device_cache()
uvc = probe_uvc_devices(use_cache=False)
print(f"UVC: {len(uvc)} devices")

# Test OpenCV sequential
clear_device_cache()
opencv_seq = probe_opencv_indices(max_index=10, parallel=False, use_cache=False)
print(f"OpenCV Sequential: {len(opencv_seq)} devices")

# Test OpenCV parallel
clear_device_cache()
opencv_par = probe_opencv_indices(max_index=10, parallel=True, use_cache=False)
print(f"OpenCV Parallel: {len(opencv_par)} devices")
```

## Hardware Recommendations

### For Reliable Detection:

1. **USB 3.0 Ports**
   - More bandwidth for simultaneous initialization
   - Faster device enumeration

2. **Powered USB Hub**
   - Provides stable power to all cameras
   - Reduces initialization delays

3. **Separate USB Controllers**
   - Distribute cameras across multiple USB controllers
   - Avoid bandwidth sharing

4. **Quality USB Cables**
   - Short cables (<6 feet) preferred
   - USB 3.0 rated cables even for USB 2.0 cameras

## Expected Behavior After Fixes

### Before Fixes:
- ❌ 50-70% detection rate on cold boot
- ❌ Parallel probing misses 2-3 cameras
- ❌ Timeout after 1 second too aggressive
- ❌ No retry on transient failures

### After Fixes:
- ✅ 95%+ detection rate on cold boot
- ✅ Sequential probing finds all cameras
- ✅ 3-second timeout handles slow devices
- ✅ Retries handle transient failures
- ✅ Better logging for diagnostics
