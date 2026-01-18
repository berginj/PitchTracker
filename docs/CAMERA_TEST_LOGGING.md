# Camera Capability Test Logging Guide

## Overview

The camera capability test script now includes comprehensive logging to help diagnose camera issues and analyze test results.

## Running the Test

```bash
python test_camera_capabilities.py
```

## Output Files

After running the test, you'll find two files in the `camera_tests/` directory:

### 1. `capability_report.txt` - Human-Readable Report
- Summary of all cameras detected
- Supported resolutions and frame rates
- Memory usage statistics
- Dual-camera test results
- **Format**: Plain text, formatted for readability

### 2. `capability_test.log` - Detailed Debug Log
- Complete diagnostic information with timestamps
- Step-by-step execution trace
- Error messages with stack traces
- Backend switching events
- System information (Python version, OpenCV version)
- **Format**: Timestamped log entries with severity levels

## What Gets Logged

### System Information
- Python version
- OpenCV version
- Test parameters (number of cameras, resolutions tested)

### Camera Enumeration
```
2026-01-18 14:23:15 - __main__ - INFO - Enumerating cameras 0-5
2026-01-18 14:23:15 - __main__ - DEBUG - Probing UVC devices...
2026-01-18 14:23:16 - __main__ - INFO - Found 2 UVC devices
2026-01-18 14:23:16 - __main__ - DEBUG -   UVC 0: ArduCam UC-396 Rev. B (SN: 12345678)
2026-01-18 14:23:16 - __main__ - DEBUG -   UVC 1: ArduCam UC-396 Rev. B (SN: 87654321)
```

### Resolution Testing
```
2026-01-18 14:23:20 - __main__ - INFO - Testing Camera 0 (ArduCam UC-396 Rev. B) with DSHOW backend
2026-01-18 14:23:20 - __main__ - INFO - Testing 10 resolution/FPS combinations
2026-01-18 14:23:20 - __main__ - DEBUG - Testing 640x480@15fps...
2026-01-18 14:23:21 - __main__ - INFO - ✅ 640x480@15fps - SUPPORTED
2026-01-18 14:23:21 - __main__ - DEBUG - Testing 640x480@30fps...
2026-01-18 14:23:22 - __main__ - INFO - ✅ 640x480@30fps - SUPPORTED
```

### Memory Testing
```
2026-01-18 14:25:30 - __main__ - INFO - Memory test: 1280x720@30fps for 5s
2026-01-18 14:25:30 - __main__ - DEBUG - Baseline memory: 156.3 MB
2026-01-18 14:25:35 - __main__ - INFO - Memory test SUCCESS: 150 frames in 5.0s, 30.0 fps, 245.2 MB used
```

### Dual-Camera Testing
```
2026-01-18 14:26:00 - __main__ - INFO - Dual camera test: 1280x720@30fps for 10s
2026-01-18 14:26:10 - __main__ - INFO - Dual camera test SUCCESS: Left=29.8fps, Right=29.9fps, Errors=0
```

### Error Logging
When errors occur, full stack traces are captured:
```
2026-01-18 14:27:00 - __main__ - ERROR - Error testing camera 5: [Errno 2] No such device
Traceback (most recent call last):
  File "test_camera_capabilities.py", line 219, in test_camera_modes
    cap = cv2.VideoCapture(camera_index, backend)
...
```

## Log Levels

The log file includes different severity levels:

- **DEBUG**: Detailed diagnostic information (only in log file)
- **INFO**: General informational messages (console + log file)
- **WARNING**: Something unexpected happened (console + log file)
- **ERROR**: A serious problem occurred (console + log file)

## Console vs Log File

### Console Output
- Shows INFO, WARNING, and ERROR messages
- User-friendly formatting
- Progress indicators (✅/❌)
- Less verbose for readability

### Log File Output
- Shows ALL messages (DEBUG through ERROR)
- Detailed timestamps
- Complete exception stack traces
- Backend operations
- Camera probing details

## Analyzing Test Results

### For Normal Usage
1. Look at `capability_report.txt` for supported resolutions
2. Check for ArduCam devices in the enumeration
3. Note which resolutions passed memory and dual-camera tests

### For Troubleshooting
1. Open `capability_test.log` in a text editor
2. Search for "ERROR" to find failures
3. Check timestamps to see where the test slowed down or hung
4. Look at stack traces for error details
5. Share the log file with support/development team

## Sharing Logs for Analysis

To get help with camera issues:

1. Run the test on your system
2. Locate these files in `camera_tests/`:
   - `capability_test.log`
   - `capability_report.txt`
3. Share both files (you can attach them or paste their contents)

**Note**: The logs contain camera serial numbers and system information, but no sensitive data.

## Example: Reading a Log File

Here's how to find key information in the log:

### Check if cameras were detected:
```bash
grep "Found.*camera" camera_tests/capability_test.log
```

### Check for errors:
```bash
grep "ERROR" camera_tests/capability_test.log
```

### Check ArduCam devices:
```bash
grep "ArduCam" camera_tests/capability_test.log
```

### Check supported resolutions:
```bash
grep "SUPPORTED" camera_tests/capability_test.log
```

## Tips

1. **Run test with clean state**: Close other applications that might use cameras before testing
2. **Test multiple times**: If results are inconsistent, run the test 2-3 times and compare logs
3. **Check timestamps**: Large gaps between log entries indicate where the test is slow
4. **Note USB ports**: If you swap USB ports, run the test again and note differences in logs
5. **Compare backends**: The test runs both DirectShow and Media Foundation - compare their results in the log

## Automated Analysis

You can use standard log analysis tools on the log file:

```bash
# Count errors
grep -c "ERROR" camera_tests/capability_test.log

# See all supported modes
grep "SUPPORTED" camera_tests/capability_test.log | wc -l

# Extract timing information
grep "Memory test SUCCESS" camera_tests/capability_test.log

# Find slow operations (more than 2 seconds between logs)
awk '{print $1, $2, $NF}' camera_tests/capability_test.log | uniq
```

## Next Steps

After reviewing the logs:

1. **If all tests pass**: Your cameras support higher resolutions!
   - Update coaching app settings to use better resolution
   - See `INVESTIGATION_SUMMARY.md` for recommendations

2. **If some tests fail**: Identify the bottleneck
   - USB 2.0 limitation? Try lower resolution or USB 3.0
   - Backend issue? Compare DSHOW vs MSMF results
   - Camera limitation? Check camera specifications

3. **If cameras not detected**: Enumeration issue
   - Check USB connections
   - Close other camera applications
   - Try different USB ports
   - Check Device Manager (Windows)

## Support

If you need help interpreting the logs, share them along with:
- Camera model(s)
- USB version (2.0 or 3.0)
- Operating system
- What you're trying to achieve (e.g., "want to use 1080p for coaching sessions")
