# Camera Capture Validator

A simple tool to test and validate calibrated camera setup without running detection or tracking pipelines.

## Purpose

The Camera Capture Validator is designed for:

- **Testing camera connections** - Verify both cameras are working
- **Validating calibration** - Ensure cameras are configured correctly
- **Recording test footage** - Capture raw video for debugging
- **Pre-session validation** - Check setup before running full coaching sessions

## Usage

### Launch the Validator

```bash
python test_camera_capture.py
```

### Workflow

1. **Start Cameras**
   - Click "▶ Start Cameras" button
   - Uses last selected cameras from coaching app
   - Shows live preview from both cameras

2. **Test Preview**
   - Verify both cameras show clear images
   - Check that left/right assignments are correct
   - Ensure frame rate is smooth (~30 FPS)

3. **Record Test Video** (Optional)
   - Click "⏺ Start Recording" to begin capture
   - Recording indicator (white dot) appears on preview
   - Click "⏹ Stop Recording" when done
   - Video files saved to `camera_tests/test_TIMESTAMP/`

4. **Stop Cameras**
   - Click "⏹ Stop Cameras" to release cameras
   - Ready for next test or to close application

## Output Files

When recording, files are saved to `camera_tests/test_TIMESTAMP/`:

- `left_camera.avi` - Raw video from left camera
- `right_camera.avi` - Raw video from right camera
- `test_info.txt` - Metadata (camera IDs, resolution, timestamp)

## Configuration

The validator uses:
- **Backend**: OpenCV (for compatibility)
- **Resolution**: 640x480 @ 30 FPS
- **Format**: Grayscale (GRAY8)
- **Codec**: MJPG (fallback to XVID)

## Differences from Coaching App

| Feature | Capture Validator | Coaching App |
|---------|------------------|--------------|
| Detection | ❌ No | ✅ Yes |
| Tracking | ❌ No | ✅ Yes |
| Metrics | ❌ No | ✅ Yes |
| Recording | ✅ Raw video | ✅ Session recording |
| Purpose | Testing | Full sessions |

## Troubleshooting

### Cameras Not Found

1. Check physical connections
2. Close other applications using cameras
3. Run `python -m ui.device_utils` to list cameras
4. Update camera assignments in coaching app settings

### Video Recording Fails

1. Check disk space (need ~50GB free)
2. Try XVID codec (automatic fallback)
3. Reduce resolution or frame rate
4. Check write permissions for `camera_tests/` directory

### Preview is Laggy

1. Close other applications
2. Check CPU usage
3. Reduce resolution in validator code if needed
4. Ensure cameras support 30 FPS at 640x480

## When to Use This Tool

**Use the Capture Validator when:**
- Setting up cameras for the first time
- Troubleshooting camera issues
- Verifying calibration is loaded correctly
- Checking if cameras are assigned to correct sides
- Recording test footage for bug reports

**Use the Coaching App when:**
- Running actual coaching sessions
- Tracking pitches and metrics
- Analyzing pitch data
- Recording full session data

## Technical Details

- **No pipeline overhead** - Minimal CPU usage
- **Direct camera access** - No intermediate processing
- **Simple preview** - Just display frames with labels
- **Raw recording** - Unprocessed video from cameras
- **Fast startup** - No detector or model loading

This tool is designed to be lightweight and reliable for validating camera setup before running full sessions.
