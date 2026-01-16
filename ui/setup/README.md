# Setup Application Prototype

## Overview

Wizard-based setup application for PitchTracker system configuration and calibration.

**Status:** Prototype - Camera Setup Step Complete

## Running the Prototype

```powershell
# From project root
python test_setup_wizard.py
```

Or with backend selection:
```powershell
# UVC cameras (default)
python test_setup_wizard.py

# OpenCV cameras
python -c "from ui.setup import SetupWindow; from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); w = SetupWindow('opencv'); w.show(); sys.exit(app.exec())"
```

## Current Features

### ✅ Wizard Framework
- Step indicator with progress visualization
- Navigation buttons (Back/Next/Skip)
- Step validation before proceeding
- Optional step support

### ✅ Step 1: Camera Setup
- Camera discovery (UVC or OpenCV backends)
- Left/right camera selection
- Validation (prevents same camera for both sides)
- Auto-refresh on entry
- Preview placeholders (preview implementation pending)

### 🚧 Pending Steps

**Step 2: Stereo Calibration**
- Checkerboard capture widget
- Corner detection
- Calibration calculation
- Quality validation

**Step 3: ROI Configuration**
- Lane gate (left) editing
- Lane gate (right) editing
- Plate region editing
- Live detection testing

**Step 4: Detector Tuning**
- Classical detector threshold sliders
- ML model upload
- Detection preview
- Test pitch capture

**Step 5: System Validation**
- Automated test runner
- Detection quality tests
- Stereo matching tests
- Performance tests
- Validation report generation

**Step 6: Export Package**
- Calibration package creation
- PDF report generation
- "Ready for coaching" marker

## Architecture

```
ui/setup/
├── setup_window.py           # Wizard framework & navigation
├── steps/
│   ├── base_step.py          # Abstract base class for steps
│   └── camera_step.py        # Step 1: Camera setup
├── widgets/                   # Reusable widgets
└── validation/                # Automated test runners
```

### BaseStep Interface

All wizard steps inherit from `BaseStep` and must implement:

```python
def get_title(self) -> str:
    """Return step title for step indicator."""

def get_description(self) -> str:
    """Return instructions shown to user."""

def validate(self) -> tuple[bool, str]:
    """Validate step completion.
    Returns: (is_valid, error_message)
    """

def on_enter(self) -> None:
    """Called when step becomes active."""

def on_exit(self) -> None:
    """Called when leaving step."""

def is_optional(self) -> bool:
    """Return True if step can be skipped."""
```

## UI Flow

```
┌─────────────────────────────────────────────────────────┐
│ [1. Cameras] [2. Calibration] [3. ROI] [4. Detector] ...│  ← Step Indicator
├─────────────────────────────────────────────────────────┤
│                                                          │
│              Current Step Content Here                   │  ← Step Widget
│                                                          │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ [< Back]              [Skip Step]    [Next >]           │  ← Navigation
└─────────────────────────────────────────────────────────┘
```

## Testing Checklist

### Camera Step Tests
- [ ] Launch wizard, verify step indicator shows Camera step active
- [ ] Click "Refresh Devices" - should discover cameras
- [ ] Select same camera for both sides - validation should fail
- [ ] Select different cameras - should allow Next
- [ ] Click Back (should be disabled on first step)
- [ ] Complete step and go to next (will show error since step 2 not implemented)

## Next Steps

1. **Add Calibration Step** (2-3 hours)
   - Create `calibration_step.py`
   - Build checkerboard capture widget
   - Integrate `calib.quick_calibrate`
   - Add quality validation

2. **Add ROI Step** (2 hours)
   - Create `roi_step.py`
   - Reuse existing `RoiLabel` widget
   - Add detection testing

3. **Add Detector Step** (2 hours)
   - Create `detector_step.py`
   - Build threshold tuning widget
   - Add live detection preview

4. **Add Validation Step** (2 hours)
   - Create `validation_step.py`
   - Build automated test runner
   - Generate validation report

5. **Add Export Step** (1 hour)
   - Create `export_step.py`
   - Package calibration files
   - Generate PDF report

## Design Decisions

### Why Wizard Pattern?
- ✅ Enforces proper setup sequence
- ✅ Clear progress indication
- ✅ Prevents skipping critical steps
- ✅ Easy to add/reorder steps
- ✅ Validation at each step

### Why Separate from Main UI?
- ✅ Focused workflow for setup tasks
- ✅ Doesn't clutter coaching interface
- ✅ Easier to train new installers
- ✅ Can validate entire setup before deployment

### Why Not ABC for BaseStep?
- Qt's QWidget metaclass conflicts with ABC metaclass
- Solution: Use `raise NotImplementedError` instead of `@abstractmethod`
- Still enforces implementation through runtime errors
- Cleaner without metaclass complexity

## Known Issues

1. Camera preview not yet implemented (shows placeholder)
2. Only Step 1 (Camera) currently functional
3. Backend parameter not fully tested with OpenCV
4. No save/resume wizard state yet

## Future Enhancements

- Live camera preview in Step 1
- Save/resume wizard progress
- Export wizard log for troubleshooting
- Remote assistance mode (share screen)
- Calibration templates by venue type
