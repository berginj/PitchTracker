# UI Role-Based Redesign

## Problem Statement

**Current:** Single monolithic UI (1,813 lines) combining setup/calibration with coaching workflows
**Issue:** Overwhelming for day-to-day users, cluttered interface, conflicting workflows

## Proposed Solution: Two Role-Based UIs

Split into focused applications with distinct purposes and workflows.

---

## Role 1: Setup Application (Technician/Installer)

### Purpose
**One-time or infrequent system configuration and calibration**

Used by: Technical staff, system installers, advanced users during initial setup or when relocating equipment

### Workflow
```
Launch Setup App
  ↓
Camera Discovery & Selection
  ↓
Stereo Calibration (Checkerboard)
  ↓
ROI Configuration (Lane Gates, Plate Region)
  ↓
Detector Tuning (Classical HSV or ML Model)
  ↓
System Validation & Testing
  ↓
Export Calibration Package
  ↓
Mark as "Ready for Coaching"
```

### Features

#### 1. Camera Setup
- **Device Discovery:** Scan for UVC/OpenCV cameras
- **Preview:** Live preview from both cameras
- **Configuration:** Resolution, FPS, exposure, gain
- **Validation:** Verify both cameras operational
- **Serial Assignment:** Label cameras as "left" and "right"

#### 2. Stereo Calibration
- **Guided Wizard:** Step-by-step checkerboard capture
  - Show target overlay on preview
  - Capture 20-30 image pairs
  - Automatic corner detection
  - Real-time calibration quality feedback
- **Manual Upload:** Upload pre-captured images
- **Validation:** Reprojection error, epipolar geometry check
- **Export:** Save calibration to `stereo_calibration.json`

#### 3. ROI Configuration
- **Lane Gate (Left):** Click-and-drag rectangle for pitch detection zone
- **Lane Gate (Right):** Separate rectangle for right camera
- **Plate Region:** Rectangle around strike zone area
- **Live Testing:** Show detection activity within ROIs
- **Validation:** Verify detections trigger in correct regions
- **Templates:** Save/load ROI templates for different installations

#### 4. Detector Tuning
- **Classical Detector:**
  - Mode selection (A/B)
  - HSV threshold sliders with live preview
  - Blob filter parameters (area, circularity)
  - Frame diff, background diff, edge thresholds
  - Test with sample pitches
- **ML Detector:**
  - Model selection (upload .onnx file)
  - Confidence threshold tuning
  - Test inference on sample frames
  - Performance metrics (FPS, latency)

#### 5. System Validation
- **Test Pitch Capture:** Record test pitches
- **Detection Quality:** Verify consistent ball tracking
- **Stereo Matching:** Check triangulation accuracy
- **Timing Accuracy:** Verify pre-roll/post-roll work
- **Performance:** Check FPS, dropped frames, latency

#### 6. Export & Deployment
- **Calibration Package:** Export complete setup
  - Stereo calibration
  - ROI definitions
  - Detector configuration
  - Camera assignments
- **Validation Report:** PDF with setup quality metrics
- **Config File:** Ready-to-use YAML for coaching app

### UI Design (Setup Application)

```
┌─────────────────────────────────────────────────────────────────┐
│  PitchTracker - Setup & Calibration                       [×]   │
├─────────────────────────────────────────────────────────────────┤
│  Step: [1. Cameras] [2. Calibration] [3. ROI] [4. Detector] [5. Validate] [6. Export] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐            │
│  │   Left Camera       │  │   Right Camera      │            │
│  │                     │  │                     │            │
│  │   [Live Preview]    │  │   [Live Preview]    │            │
│  │                     │  │                     │            │
│  └─────────────────────┘  └─────────────────────┘            │
│                                                                 │
│  Current Step: Stereo Calibration                              │
│  ┌───────────────────────────────────────────────────────────┐│
│  │ Progress: 15 / 30 image pairs captured                    ││
│  │ Quality: Good (reprojection error: 0.8px)                 ││
│  │                                                            ││
│  │ Instructions:                                              ││
│  │ • Hold checkerboard pattern at various angles             ││
│  │ • Ensure all corners are visible in both cameras          ││
│  │ • Press SPACE to capture                                  ││
│  │                                                            ││
│  │ [Capture Image Pair]  [Undo Last]  [Recalculate]         ││
│  └───────────────────────────────────────────────────────────┘│
│                                                                 │
│  [< Back]                        [Skip Step]    [Next >]       │
└─────────────────────────────────────────────────────────────────┘
```

### Key UI Elements (Setup App)

**Layout:** Wizard-based, step-by-step progression
**Navigation:** Back/Next buttons, skip allowed for optional steps
**Validation:** Each step validates before allowing next
**Help:** Contextual help for each step
**Save State:** Can pause and resume setup

---

## Role 2: Coaching Application (Day-to-Day Sessions)

### Purpose
**Fast, focused interface for running pitching sessions**

Used by: Coaches, pitchers, trainers during practice and training sessions

### Workflow
```
Launch Coaching App (pre-calibrated)
  ↓
Select Pitcher & Session
  ↓
Quick Start Capture (automatic)
  ↓
Live Pitch Tracking & Visualization
  ↓
Real-time Metrics Display
  ↓
Stop Session & Review Summary
  ↓
Export for Player Review
```

### Features

#### 1. Quick Start
- **Pre-configured:** Uses saved calibration from setup app
- **Pitcher Selection:** Choose from saved pitcher list
- **Session Name:** Auto-generated or custom
- **One-Click Start:** Capture and tracking start immediately
- **Status Indicators:** Camera health, detection active, recording ready

#### 2. Live Pitch Tracking
- **Dual Camera View:** Side-by-side left/right cameras
- **Strike Zone Overlay:** 3x3 grid on plate view
- **Live Trail:** Show ball trajectory in real-time
- **Pitch Count:** Running count of pitches
- **Latest Metrics:** Speed, break, location displayed after each pitch

#### 3. Strike Zone Adjustments
- **Batter Height:** Quick slider (60-84 inches)
- **Ball Type:** Baseball / Softball toggle
- **Zone Ratios:** Top/bottom percentage adjustments
- **Visual Feedback:** Immediate zone overlay update

#### 4. Session Management
- **Pause/Resume:** Pause between batters or drills
- **Pitch Annotations:** Mark pitch as "good" or "bad"
- **Manual Speed:** Override speed from radar gun
- **Session Notes:** Add text notes during session

#### 5. Replay & Review
- **Last Pitch Replay:** Instant replay of most recent pitch
- **Pitch History:** Scroll through recent pitches (last 12)
- **Trajectory View:** 3D visualization of pitch path
- **Frame-by-Frame:** Step through pitch video

#### 6. Session Summary
- **Statistics:**
  - Total pitches
  - Strike percentage
  - Average velocity
  - Break averages (horizontal, vertical)
- **Heat Map:** Location plot (3x3 grid)
- **Pitch Table:** Sortable list of all pitches
- **Export Options:**
  - Share with player (videos + summary)
  - Upload to cloud
  - Save to USB drive

### UI Design (Coaching Application)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PitchTracker - Coaching Session                    [○ Recording]  [×] │
├─────────────────────────────────────────────────────────────────────────┤
│  Session: Practice-2026-01-16  │  Pitcher: John Doe  │  Pitches: 23    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────┐ ┌───────────────────┐ ┌──────────────────────┐ │
│  │ Left Camera       │ │ Strike Zone       │ │ Latest Pitch         │ │
│  │                   │ │  ┌─────────────┐  │ │                      │ │
│  │                   │ │  │  ⚫ │   │   │  │ │  Speed: 87.3 mph     │ │
│  │  [Live]           │ │  │────┼───┼───│  │ │  H-Break: +2.1 in    │ │
│  │                   │ │  │    │   │ ⚫ │  │ │  V-Break: -0.8 in    │ │
│  │                   │ │  └─────────────┘  │ │                      │ │
│  └───────────────────┘ └───────────────────┘ │  Result: STRIKE      │ │
│                                               │                      │ │
│  ┌───────────────────┐ ┌───────────────────┐ │  [Replay Last]       │ │
│  │ Right Camera      │ │ Heat Map          │ │  [View Trail]        │ │
│  │                   │ │  3   2   1        │ └──────────────────────┘ │
│  │                   │ │  2   5   3                                   │ │
│  │  [Live]           │ │  1   4   2        ┌──────────────────────┐ │ │
│  │                   │ │                   │ Recent Pitches       │ │ │
│  │                   │ │                   │ 1. 87.3 mph STRIKE   │ │ │
│  └───────────────────┘ └───────────────────┘ │ 2. 85.1 mph BALL     │ │ │
│                                               │ 3. 88.9 mph STRIKE   │ │ │
│  ┌──────────────────────────────────────────┐│ ...                  │ │ │
│  │ Strike Zone: Batter 72" [━━━━━●━━━━━━] 84"│└──────────────────────┘ │ │
│  └──────────────────────────────────────────┘                         │ │
│                                                                          │
│  [⏸ Pause Session]  [⏹ End Session]  [⚙ Settings]  [❓ Help]          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key UI Elements (Coaching App)

**Layout:** Dashboard-style, all key info visible
**Navigation:** Minimal - focus on live tracking
**Quick Access:** Large buttons for common actions
**Real-time Updates:** Metrics update automatically
**Minimal Distraction:** Hide technical details

---

## Architecture Changes

### File Structure

```
ui/
├── __init__.py
├── qt_app.py                    # Entry point - role selector
├── setup/                        # Setup Application
│   ├── __init__.py
│   ├── setup_window.py          # Main setup window (wizard)
│   ├── steps/                   # Wizard steps
│   │   ├── __init__.py
│   │   ├── camera_step.py       # Camera discovery & config
│   │   ├── calibration_step.py  # Stereo calibration
│   │   ├── roi_step.py          # ROI configuration
│   │   ├── detector_step.py     # Detector tuning
│   │   ├── validation_step.py   # System testing
│   │   └── export_step.py       # Package export
│   ├── widgets/
│   │   ├── calibration_capture.py  # Checkerboard capture widget
│   │   ├── roi_editor.py           # ROI drawing widget
│   │   └── detector_tuner.py       # Threshold tuning widget
│   └── validation/
│       └── test_runner.py       # Automated system tests
│
├── coaching/                     # Coaching Application
│   ├── __init__.py
│   ├── coach_window.py          # Main coaching window
│   ├── widgets/
│   │   ├── pitch_monitor.py     # Live pitch tracking display
│   │   ├── strike_zone_view.py  # Strike zone visualization
│   │   ├── heat_map.py          # Location heat map
│   │   ├── pitch_history.py     # Recent pitches list
│   │   └── metrics_panel.py     # Real-time metrics display
│   ├── dialogs/
│   │   ├── session_start.py     # Session startup dialog
│   │   ├── session_summary.py   # End-of-session summary
│   │   └── replay_viewer.py     # Pitch replay dialog
│   └── export/
│       └── player_package.py    # Export for player review
│
├── shared/                       # Shared components
│   ├── __init__.py
│   ├── device_utils.py          # Camera discovery (existing)
│   ├── drawing.py               # Rendering functions (existing)
│   ├── geometry.py              # Geometry helpers (existing)
│   └── widgets/
│       └── roi_label.py         # ROI drawing widget (existing)
│
└── dialogs/                      # Shared dialogs
    └── ...existing dialogs...
```

### Entry Point: Role Selector

```python
# ui/qt_app.py
def main():
    """Entry point with role selection."""
    app = QtWidgets.QApplication(sys.argv)

    # Check if system is calibrated
    if not is_system_calibrated():
        # Force setup mode
        from ui.setup import SetupWindow
        window = SetupWindow()
    else:
        # Show role selector
        role = select_role()  # Dialog: "Setup" or "Coaching"

        if role == "setup":
            from ui.setup import SetupWindow
            window = SetupWindow()
        else:
            from ui.coaching import CoachWindow
            window = CoachWindow()

    window.show()
    sys.exit(app.exec())
```

---

## Implementation Plan

### Phase 1: Extract Setup Functionality (2 days)
1. Create `ui/setup/` directory structure
2. Build wizard framework with step navigation
3. Extract camera setup step
4. Extract calibration step
5. Extract ROI configuration step
6. Extract detector tuning step
7. Add validation step
8. Add export functionality

### Phase 2: Extract Coaching Functionality (2 days)
1. Create `ui/coaching/` directory structure
2. Build coaching window with dashboard layout
3. Create pitch monitor widget
4. Create strike zone visualization
5. Create heat map widget
6. Create metrics panel
7. Add session management
8. Add replay functionality

### Phase 3: Shared Components (1 day)
1. Identify truly shared components
2. Move to `ui/shared/`
3. Update imports in both apps
4. Test both applications

### Phase 4: Role Selector & Integration (1 day)
1. Build role selection dialog
2. Add calibration status detection
3. Update entry point
4. Add role switching (advanced feature)
5. Integration testing

### Phase 5: Polish & Documentation (1 day)
1. Add contextual help to both apps
2. Create user guides for each role
3. Add keyboard shortcuts
4. Performance optimization
5. Final testing

**Total Estimate:** 7 days (1 week of focused work)

---

## Benefits

### For Technicians/Installers
✅ Guided workflow ensures nothing is missed
✅ Clear validation at each step
✅ Easier to train new installers
✅ Export package documents setup quality

### For Coaches
✅ Fast session startup (<10 seconds)
✅ Focused interface - no clutter
✅ Real-time feedback during practice
✅ Easy session review and export
✅ No risk of accidentally changing calibration

### For Codebase
✅ Separation of concerns
✅ Each UI focused on specific workflow
✅ Easier to test independently
✅ Easier to add features to each role
✅ Reduced complexity per UI (~800 lines each vs 1,813)

### For Users
✅ Less overwhelming for new users
✅ Appropriate tools for each role
✅ Faster common operations
✅ Reduced training time

---

## Migration Strategy

### Backward Compatibility

**Option 1: Parallel UIs (Recommended)**
- Keep existing `main_window.py` as "Legacy Mode"
- Add new setup/coaching apps
- Let users choose in launch dialog
- Deprecate legacy after 6 months

**Option 2: Hard Cutover**
- Replace existing UI completely
- Provide migration guide
- May cause disruption for existing users

### Data Compatibility

Both UIs use same data formats:
- ✅ Same config files (YAML)
- ✅ Same ROI files (JSON)
- ✅ Same calibration format
- ✅ Same recording format
- ✅ Same pipeline service

No data migration needed!

---

## Open Questions

1. **Should setup app allow "quick recalibration" of single components?**
   - E.g., re-tune detector without full wizard
   - Answer: Yes, add "Advanced" menu with direct access

2. **Should coaching app have emergency access to setup features?**
   - E.g., ROI adjustment if camera shifts
   - Answer: Yes, "Settings" menu with password-protected advanced options

3. **How to handle camera disconnection during coaching session?**
   - Answer: Pause session, show reconnection dialog, resume when ready

4. **Should coaching app support multiple simultaneous sessions?**
   - E.g., two pitchers, two camera rigs
   - Answer: Future feature, not in v1

5. **Export format for player packages?**
   - Answer: ZIP with videos, PDF summary, shareable link

---

## Success Metrics

**Setup App:**
- Time to complete setup: <20 minutes (vs ~45 minutes currently)
- Setup success rate: >95% without technical support
- Calibration quality: Reprojection error <1.0px

**Coaching App:**
- Session start time: <10 seconds
- Pitches tracked per minute: >6
- Coach satisfaction: "Easy to use" rating >4.5/5

**Overall:**
- Code maintainability: Cyclomatic complexity <10 per module
- Test coverage: >80% for both apps
- User support tickets: Reduce by 50%

---

## Next Steps

1. **Review this design** with stakeholders
2. **Prototype setup wizard** (Phase 1, steps 1-3)
3. **Prototype coaching dashboard** (Phase 2, steps 1-4)
4. **User testing** with both prototypes
5. **Iterate** based on feedback
6. **Full implementation** following plan

---

## Appendix: Detailed Feature Mapping

### Current Features → New Homes

| Feature | Current Location | Setup App | Coaching App | Notes |
|---------|-----------------|-----------|--------------|-------|
| Camera selection | Main | ✓ Step 1 | Auto-loaded | |
| Device refresh | Main | ✓ Step 1 | - | Not needed in coaching |
| Start/Stop capture | Main | ✓ Testing | Auto | Automatic in coaching |
| ROI editing | Main | ✓ Step 3 | Settings (locked) | |
| Strike zone config | Main | - | ✓ Quick adjust | Simplified for coaches |
| Detector settings | Main | ✓ Step 4 | - | Not exposed in coaching |
| Calibration wizard | Main | ✓ Step 2 | - | Core of setup app |
| Quick calibrate | Main | ✓ Step 2 | - | Part of wizard |
| Plate plane | Main | ✓ Step 2 | - | Part of wizard |
| Recording | Main | ✓ Testing | ✓ Primary | Auto-start in coaching |
| Replay | Main | - | ✓ Primary | Essential for review |
| Session summary | Main | - | ✓ Primary | End of session |
| Profile management | Main | ✓ Export | ✓ Load | Setup creates, coaching loads |
| Pitcher management | Main | - | ✓ Primary | Coach selects pitcher |
| Health panel | Main | ✓ Validation | ✓ Status bar | Different detail levels |
| Export/Upload | Main | ✓ Package | ✓ Player share | Different formats |

---

**Document Status:** Proposal - Awaiting Review
**Created:** 2026-01-16
**Author:** Claude (AI Assistant)
**Version:** 1.0
