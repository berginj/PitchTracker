# MainWindow Refactoring Plan

## Current State

**Problem**: MainWindow is a god class with:
- 90 methods
- 2,250 lines of code
- Multiple responsibilities mixed together
- 3 huge methods (100+ lines each):
  - `__init__`: 333 lines
  - `_update_preview`: 156 lines
  - `_build_menu`: 131 lines

## Method Distribution

- **Small** (<20 lines): 56 methods
- **Medium** (20-50 lines): 29 methods
- **Large** (50-100 lines): 2 methods
- **Huge** (100+ lines): 3 methods

## Proposed Architecture

Extract logical groups into separate controller/manager classes:

### 1. CaptureController
**Responsibility**: Camera capture lifecycle management

**Methods to extract** (5 methods):
- `_start_capture()`
- `_stop_capture()`
- `_restart_capture()`
- `_pre_capture_check()`
- `_refresh_devices()`

**Benefits**:
- Isolated camera management logic
- Easier to test capture workflows
- Clearer separation of concerns

**Estimated size**: ~150 lines

---

### 2. RecordingController
**Responsibility**: Session recording and output management

**Methods to extract** (7 methods):
- `_start_recording()`
- `_stop_recording()`
- `_start_training_capture()`
- `_browse_output()`
- `_set_output_dir()`
- `_set_manual_speed()`
- `_default_session_name()`

**Benefits**:
- Encapsulated recording state
- Simplified session lifecycle
- Easier to add recording features

**Estimated size**: ~200 lines

---

### 3. ExportManager
**Responsibility**: Session data export and upload

**Methods to extract** (7 methods):
- `_upload_session()`
- `_save_session_export()`
- `_export_session_summary_json()`
- `_export_session_summary_csv()`
- `_write_session_summary_csv()`
- `_export_training_report()`
- `_export_manifests_zip()`

**Benefits**:
- Already has ui/export.py module (can leverage)
- Clear export API
- Easy to add new export formats

**Estimated size**: ~250 lines (or move to ui/export.py)

---

### 4. RoiManager
**Responsibility**: ROI drawing, saving, loading

**Methods to extract** (8 methods):
- `_set_roi_mode()`
- `_clear_lane()`
- `_clear_plate()`
- `_load_rois()`
- `_save_rois()`
- `_on_rect_update()`
- `_on_right_rect_update()`
- `_propose_right_lane()`

**Benefits**:
- Isolated ROI state management
- Easier ROI workflow testing
- Clear ROI API

**Estimated size**: ~180 lines

---

### 5. ReplayController
**Responsibility**: Video replay and frame stepping

**Methods to extract** (6 methods):
- `_start_replay()`
- `_stop_replay()`
- `_toggle_replay_pause()`
- `_step_replay()`
- `_update_replay()`
- `_init_replay_detector()`

**Benefits**:
- Isolated replay state
- Easier to add replay features
- Clear replay API

**Estimated size**: ~200 lines

---

### 6. CalibrationManager
**Responsibility**: Calibration workflows and dialogs

**Methods to extract** (5 methods):
- `_open_calibration_guide()`
- `_open_quick_calibrate()`
- `_open_plate_calibrate()`
- `_run_calibration_wizard()`
- `_update_calib_summary()`

**Benefits**:
- Centralized calibration logic
- Easier to add calibration methods
- Clear calibration API

**Estimated size**: ~150 lines

---

### 7. SettingsManager
**Responsibility**: Application settings and configuration dialogs

**Methods to extract** (9 methods):
- `_open_record_settings()`
- `_open_strike_settings()`
- `_open_detector_settings()`
- `_apply_detector_config()`
- `_load_detector_defaults()`
- `_set_ball_type()`
- `_set_batter_height()`
- `_set_strike_ratios()`
- `_save_strike_zone()`

**Benefits**:
- Centralized settings logic
- Easier settings persistence
- Clear settings API

**Estimated size**: ~250 lines

---

### 8. ProfileManager
**Responsibility**: Location profiles and pitcher management

**Methods to extract** (6 methods):
- `_load_profile()`
- `_save_profile()`
- `_refresh_profiles()`
- `_add_pitcher()`
- `_set_pitcher()`
- `_refresh_pitchers()`

**Benefits**:
- Isolated profile/pitcher state
- Easier to extend profiles
- Clear profile API

**Estimated size**: ~120 lines

---

### 9. GameVisualizer
**Responsibility**: Tic-tac-toe game and plate map visualization

**Methods to extract** (7 methods):
- `_apply_pitch_to_tic_tac_toe()`
- `_mark_tic_tac_toe_ai()`
- `_random_target_cell()`
- `_reset_tic_tac_toe_game()`
- `_update_game_labels()`
- `_update_plate_map()`
- `_update_plate_map_zone()`

**Benefits**:
- Separated game logic
- Optional feature, easier to disable
- Clear visualization API

**Estimated size**: ~150 lines

---

## MainWindow After Refactoring

**Remaining responsibilities**:
- Window lifecycle (init, closeEvent)
- UI building (_build_menu, _build_panels)
- Preview updates (_update_preview)
- Coordinator for controllers (delegate to controllers)
- Menu/button signal connections

**Estimated size**: ~500-700 lines (down from 2,250)

**Remaining methods**: ~35 methods (down from 90)

---

## Implementation Strategy

### Phase 1: Extract Non-UI Controllers (Week 1-2)
1. **ExportManager** (already have ui/export.py, just wire it up)
2. **ProfileManager** (simple, no UI coupling)
3. **CalibrationManager** (straightforward extraction)

**Target**: Reduce MainWindow by ~500 lines

### Phase 2: Extract UI Controllers (Week 2-3)
4. **RoiManager** (moderate UI coupling)
5. **SettingsManager** (dialog management)
6. **GameVisualizer** (self-contained)

**Target**: Reduce MainWindow by ~550 lines

### Phase 3: Extract Core Controllers (Week 3-4)
7. **CaptureController** (tight integration with service)
8. **RecordingController** (session lifecycle)
9. **ReplayController** (detector management)

**Target**: Reduce MainWindow by ~550 lines

### Phase 4: Refactor Huge Methods (Week 4-5)
- Break down `__init__` (333 lines) into smaller initialization methods
- Simplify `_update_preview` (156 lines) with helper methods
- Maintain `_build_menu` (131 lines) as-is (acceptable for menu building)

**Target**: No single method >100 lines

---

## Testing Strategy

### Per-Controller Tests
- Unit tests for each extracted controller
- Mock MainWindow dependencies
- Test controller state management

### Integration Tests
- Test MainWindow → Controller interactions
- Ensure signal/slot connections work
- Verify UI updates correctly

### Regression Tests
- Run existing UI smoke tests
- Run existing integration tests
- Manual UI walkthrough

---

## Benefits Summary

**Code Quality**:
- 75% reduction in MainWindow size (2,250 → ~600 lines)
- 60% reduction in method count (90 → ~35)
- Single Responsibility Principle compliance
- Improved testability

**Maintainability**:
- Clear API boundaries
- Easier to understand code flow
- Simpler debugging
- Reduced cognitive load

**Extensibility**:
- Easy to add features to specific controllers
- Controllers can be reused in other contexts
- Clear separation makes changes safer

---

## Risks & Mitigation

**Risk**: Breaking existing functionality
- **Mitigation**: Comprehensive testing at each phase, small incremental changes

**Risk**: Signal/slot connection issues
- **Mitigation**: Careful review of Qt connections, integration tests

**Risk**: State management complexity
- **Mitigation**: Clear ownership of state, documented APIs

**Risk**: Time investment
- **Mitigation**: Phased approach, deliver value incrementally

---

## Success Criteria

- ✅ MainWindow < 700 lines
- ✅ No method > 100 lines
- ✅ All controllers < 300 lines
- ✅ Test coverage >70% for controllers
- ✅ All existing tests pass
- ✅ No regression in UI functionality

---

**Created**: 2026-02-17
**Status**: Planning
**Priority**: High (technical debt reduction)
