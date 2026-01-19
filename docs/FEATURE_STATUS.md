# Feature Implementation Status

**Date:** 2026-01-18
**Commit:** cfee207

---

## Completed Features ✅

### 1. Color Video Capture Option
**Status:** ✅ Complete

- Added `color_mode` boolean field to `CameraConfig` (defaults to `true`)
- When enabled, camera uses YUYV format for color video
- When disabled, uses GRAY8 format for grayscale
- Implemented in `app/pipeline/initialization.py:configure_camera()`
- Settings persist in app_state
- **Default changed to color video for better user experience**

**Usage:**
```yaml
# configs/default.yaml
camera:
  color_mode: true  # Enable color video (default)
```

### 2. Resolution Settings in UI
**Status:** ✅ Complete (Partially)

- Added resolution presets to settings dialog:
  - 640x480 @ 30fps (Low)
  - 1280x720 @ 30fps (Medium)
  - 1280x720 @ 60fps (High) - **NEW**
  - 1920x1080 @ 30fps (Very High)
  - 1920x1080 @ 60fps (Ultra)

- Color mode checkbox added to settings dialog
- Default resolution changed to 1280x720 @ 60fps

**Location:** `ui/coaching/dialogs/settings_dialog.py`

### 3. Default Batter Height Updated
**Status:** ✅ Complete

- Changed from 72.0 inches (6'0") to 66.0 inches (5'6")
- Updated in `configs/default.yaml`

**Configuration:**
```yaml
strike_zone:
  batter_height_in: 66.0  # 5'6" default
```

---

## Pending Features 🚧

### 4. Wire Color Mode Through Coach Window
**Status:** ✅ Complete

**Completed Work:**
1. ✅ Added `_camera_color_mode` member variable to `CoachWindow.__init__()`
2. ✅ Load color mode from app_state: `state.get("coaching_color_mode", False)`
3. ✅ Pass `current_color_mode` parameter to `SettingsDialog`
4. ✅ Apply `dialog.color_mode` when settings change
5. ✅ Update coaching_config to use color_mode setting

**Files Modified:**
- `ui/coaching/coach_window.py` (lines 63, 600, 613, 391, 646)

**Implementation:**
```python
# In __init__ (line 63):
self._camera_color_mode = state.get("coaching_color_mode", False)

# In SettingsDialog call (line 600):
dialog = SettingsDialog(
    ...
    current_color_mode=self._camera_color_mode,
    ...
)

# When applying settings (line 613):
self._camera_color_mode = dialog.color_mode

# In coaching_config (lines 391, 646):
coaching_camera_config = CameraConfig(
    ...
    color_mode=self._camera_color_mode,
)
```

### 5. Ensure OpenCV Video in All Preview Windows
**Status:** ✅ Complete

**Verification Results:**
✅ All preview windows properly handle both grayscale and color video
✅ Color pipeline verified: YUYV (camera) → BGR (OpenCV) → RGB (Qt display)
✅ No code changes needed - existing code already compatible

**Files Verified:**
- `ui/coaching/coach_window.py` - BGR→RGB conversion (lines 806-829)
- `ui/drawing.py` - Shared frame_to_pixmap utility (lines 58)
- `ui/coaching/dialogs/lane_adjust_dialog.py` - BGR→RGB conversion (lines 194)
- `ui/setup/steps/calibration_step.py` - BGR→RGB conversion (lines 655)
- `ui/setup/steps/roi_step.py` - BGR→RGB conversion (lines 252)

**Technical Details:**
- Camera backends automatically convert YUYV→BGR via OpenCV
- Preview windows use `cv2.cvtColor(image, cv2.COLOR_BGR2RGB)` for Qt display
- Both grayscale and color formats fully supported in all preview contexts

### 6. Review/Training Mode for Prior Sessions
**Status:** ❌ Not Started

**Requirements:**
- New workflow mode: "Review & Train"
- Load recorded sessions as input
- Re-run detection/tracking with different parameters
- Compare results to improve identification
- Ability to score/annotate pitches

**Design Approach:**
1. Add third option to main window or coach window:
   ```
   [ Live Capture ]  [ Review Session ]  [ Playback ]
   ```

2. Review mode features:
   - Load session directory
   - Play back video files (session_left.avi, session_right.avi)
   - Run detection with adjustable parameters
   - Display side-by-side: original detections vs new detections
   - Score/annotate individual pitches
   - Export improved annotations

**Files to Create:**
- `ui/review_window.py` - Review mode UI
- `app/review_service.py` - Service for loading and re-processing sessions
- `app/pipeline/session_loader.py` - Load recorded sessions

**Files to Modify:**
- Main window to add "Review" option
- Coach window to add "Review Session" button

**Implementation Steps:**
1. Create session loader (reads videos + manifests)
2. Create review service (playback with detection)
3. Create review UI (video player + detection controls)
4. Add parameter tuning panel
5. Add annotation/scoring interface
6. Add export functionality

---

## Summary

**Completed (5/6 features):**
- ✅ Color video capture option
- ✅ Resolution settings in UI
- ✅ Default batter height to 5'6"
- ✅ Wire color mode through coach window
- ✅ OpenCV video in preview windows

**Not Started (1/6):**
- ❌ Review/training mode

**Next Steps:**
1. Design and implement review/training mode (see docs/REVIEW_TRAINING_MODE_DESIGN.md)

---

**Document Version:** 1.1
**Last Updated:** 2026-01-19
**Status:** 83% Complete (5/6 features)
