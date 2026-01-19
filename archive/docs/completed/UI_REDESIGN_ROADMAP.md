# UI Redesign Implementation Roadmap

## Executive Summary

**Goal:** Split monolithic 1,813-line MainWindow into two focused applications
**Timeline:** 7 days focused work
**Risk:** Low - data format compatibility maintained
**Benefit:** 50% reduction in complexity per UI, better user experience for both roles

---

## Week 1: Setup Application

### Day 1: Foundation & Camera Setup

**Morning: Project Structure**
- [ ] Create `ui/setup/` directory
- [ ] Create `ui/setup/steps/` directory
- [ ] Create `ui/setup/widgets/` directory
- [ ] Create base `SetupWindow` class with wizard framework
- [ ] Add step navigation (Back/Next/Skip)
- [ ] Add progress indicator

**Afternoon: Camera Step**
- [ ] Extract camera discovery logic → `camera_step.py`
- [ ] Build camera preview widget
- [ ] Add device selection dropdowns
- [ ] Add refresh button
- [ ] Add validation (both cameras selected and operational)
- [ ] Test: Launch wizard, select cameras, verify preview

**Files Created:**
- `ui/setup/__init__.py`
- `ui/setup/setup_window.py` (~200 lines)
- `ui/setup/steps/__init__.py`
- `ui/setup/steps/camera_step.py` (~150 lines)

### Day 2: Stereo Calibration

**Morning: Calibration Framework**
- [ ] Extract calibration wizard → `calibration_step.py`
- [ ] Build checkerboard capture widget
- [ ] Add target overlay system
- [ ] Add image pair collection (30 pairs)
- [ ] Add progress display

**Afternoon: Calibration Execution**
- [ ] Integrate `calib.quick_calibrate.calibrate_and_write`
- [ ] Add quality metrics display (reprojection error)
- [ ] Add validation (error < 1.0px)
- [ ] Add preview of calibration results
- [ ] Test: Capture images, run calibration

**Files Created:**
- `ui/setup/steps/calibration_step.py` (~250 lines)
- `ui/setup/widgets/calibration_capture.py` (~180 lines)

### Day 3: ROI Configuration

**Morning: ROI Editor**
- [ ] Extract ROI editing → `roi_step.py`
- [ ] Create `ROIEditor` widget (reuse existing `RoiLabel`)
- [ ] Add lane gate left editing
- [ ] Add lane gate right editing
- [ ] Add plate region editing
- [ ] Add visual feedback (colored overlays)

**Afternoon: ROI Validation**
- [ ] Add detection testing within ROIs
- [ ] Show detection activity counters
- [ ] Add templates system (save/load ROI sets)
- [ ] Add validation (all ROIs defined)
- [ ] Test: Draw ROIs, verify detections trigger

**Files Created:**
- `ui/setup/steps/roi_step.py` (~200 lines)
- `ui/setup/widgets/roi_editor.py` (~120 lines)

### Day 4: Detector Tuning & Validation

**Morning: Detector Configuration**
- [ ] Extract detector settings → `detector_step.py`
- [ ] Build threshold tuning widget
- [ ] Add classical detector controls (HSV, blob filters)
- [ ] Add ML detector controls (model upload, confidence)
- [ ] Add live detection preview
- [ ] Add test pitch capture

**Afternoon: System Validation**
- [ ] Create `validation_step.py`
- [ ] Build automated test runner
- [ ] Add detection quality tests
- [ ] Add stereo matching tests
- [ ] Add performance tests (FPS, latency)
- [ ] Generate validation report

**Files Created:**
- `ui/setup/steps/detector_step.py` (~200 lines)
- `ui/setup/steps/validation_step.py` (~150 lines)
- `ui/setup/widgets/detector_tuner.py` (~180 lines)
- `ui/setup/validation/test_runner.py` (~120 lines)

### Day 5: Export & Polish

**Morning: Export Package**
- [ ] Create `export_step.py`
- [ ] Build calibration package exporter
- [ ] Export stereo calibration JSON
- [ ] Export ROI definitions JSON
- [ ] Export detector config YAML
- [ ] Generate PDF validation report
- [ ] Create "ready for coaching" marker file

**Afternoon: Polish & Testing**
- [ ] Add help text for each step
- [ ] Add keyboard shortcuts (Space to capture, Enter to next)
- [ ] Add error recovery (retry failed steps)
- [ ] Add save/resume functionality
- [ ] Full integration test: Complete wizard end-to-end
- [ ] Fix bugs found during testing

**Files Created:**
- `ui/setup/steps/export_step.py` (~150 lines)

**Setup App Complete:** ~1,550 lines across 12 files (vs 1,813 in monolith)

---

## Week 2: Coaching Application

### Day 6: Coaching Dashboard

**Morning: Core Window**
- [ ] Create `ui/coaching/` directory
- [ ] Create `CoachWindow` class with dashboard layout
- [ ] Add dual camera preview (left, right)
- [ ] Add strike zone view
- [ ] Add metrics panel
- [ ] Add pitch history list
- [ ] Add heat map widget

**Afternoon: Session Management**
- [ ] Create session start dialog
- [ ] Add pitcher selection
- [ ] Add session name generation
- [ ] Add one-click capture start
- [ ] Add pause/resume functionality
- [ ] Add session timer

**Files Created:**
- `ui/coaching/__init__.py`
- `ui/coaching/coach_window.py` (~300 lines)
- `ui/coaching/dialogs/session_start.py` (~80 lines)

### Day 7: Live Tracking & Replay

**Morning: Pitch Monitoring**
- [ ] Create `pitch_monitor.py` widget
- [ ] Add real-time pitch count
- [ ] Add latest metrics display (speed, break)
- [ ] Add strike/ball indicator
- [ ] Add trajectory trail visualization
- [ ] Integrate with pitch tracking V2

**Afternoon: Replay & Summary**
- [ ] Create `replay_viewer.py` dialog
- [ ] Add instant replay (last pitch)
- [ ] Add frame-by-frame stepping
- [ ] Create session summary dialog
- [ ] Add heat map generation
- [ ] Add export options (player package)
- [ ] Full integration test: Record session, review summary

**Files Created:**
- `ui/coaching/widgets/pitch_monitor.py` (~180 lines)
- `ui/coaching/widgets/strike_zone_view.py` (~120 lines)
- `ui/coaching/widgets/heat_map.py` (~100 lines)
- `ui/coaching/widgets/pitch_history.py` (~90 lines)
- `ui/coaching/widgets/metrics_panel.py` (~80 lines)
- `ui/coaching/dialogs/replay_viewer.py` (~150 lines)
- `ui/coaching/dialogs/session_summary.py` (~120 lines)

**Coaching App Complete:** ~1,220 lines across 10 files (vs 1,813 in monolith)

---

## Day 8: Integration & Polish

### Morning: Role Selector & Entry Point

- [ ] Update `ui/qt_app.py` with role selector
- [ ] Add calibration status detection
- [ ] Add role selection dialog
- [ ] Add "Launch Setup" / "Launch Coaching" buttons
- [ ] Add role switching (advanced feature)
- [ ] Test both launch paths

### Afternoon: Final Polish

- [ ] Move truly shared components to `ui/shared/`
- [ ] Update all imports
- [ ] Add keyboard shortcuts documentation
- [ ] Create user guides (Setup Guide, Coaching Guide)
- [ ] Performance profiling and optimization
- [ ] Final end-to-end testing (both apps)
- [ ] Fix any remaining bugs

---

## Testing Checklist

### Setup Application Tests

**Camera Step:**
- [ ] Discover UVC cameras
- [ ] Discover OpenCV cameras
- [ ] Preview both cameras simultaneously
- [ ] Handle camera disconnect gracefully
- [ ] Validate both cameras selected

**Calibration Step:**
- [ ] Capture 30 checkerboard image pairs
- [ ] Automatic corner detection
- [ ] Calculate calibration (reprojection error < 1.0px)
- [ ] Save calibration to JSON
- [ ] Handle calibration failure gracefully

**ROI Step:**
- [ ] Draw lane gate (left)
- [ ] Draw lane gate (right)
- [ ] Draw plate region
- [ ] Verify detections within ROIs
- [ ] Save ROIs to JSON

**Detector Step:**
- [ ] Tune classical detector thresholds
- [ ] Upload ML model (optional)
- [ ] Test detection on sample pitches
- [ ] Achieve >90% detection rate

**Validation Step:**
- [ ] Run automated tests
- [ ] Generate validation report
- [ ] Pass all quality checks

**Export Step:**
- [ ] Create calibration package
- [ ] Generate PDF report
- [ ] Mark system as "ready"

### Coaching Application Tests

**Session Start:**
- [ ] Load calibration from setup
- [ ] Select pitcher from list
- [ ] Start capture automatically
- [ ] Display "Recording" indicator

**Live Tracking:**
- [ ] Detect pitches in real-time
- [ ] Update pitch count
- [ ] Display latest metrics (speed, break, location)
- [ ] Update heat map
- [ ] Add pitch to history

**Strike Zone:**
- [ ] Adjust batter height (slider)
- [ ] Toggle ball type
- [ ] Update zone overlay immediately

**Replay:**
- [ ] Replay last pitch
- [ ] Step frame-by-frame
- [ ] View trajectory trail

**Session End:**
- [ ] Display summary (pitch count, strikes, average speed)
- [ ] Show heat map
- [ ] Export player package (videos + PDF)

### Integration Tests

- [ ] Complete setup → launch coaching → record session
- [ ] Role switching (setup → coaching → setup)
- [ ] Calibration persistence across apps
- [ ] Data compatibility (same recording format)

---

## Risk Mitigation

### Risk 1: Data Format Incompatibility
**Mitigation:** Both apps use same pipeline service and data formats
**Fallback:** Keep legacy UI available during transition

### Risk 2: Missing Features
**Mitigation:** Feature mapping document (see main redesign doc)
**Fallback:** Add "Advanced Mode" to coaching app for edge cases

### Risk 3: User Adoption
**Mitigation:** Launch with both UIs available, deprecate legacy after 6 months
**Fallback:** Provide migration guide and training videos

### Risk 4: Development Timeline Overrun
**Mitigation:** Parallel development (setup and coaching apps independent)
**Fallback:** Ship setup app first, coaching app in phase 2

---

## Success Criteria

### Setup Application
- [ ] Complete wizard in <20 minutes (vs 45 currently)
- [ ] >95% success rate without technical support
- [ ] Calibration reprojection error <1.0px
- [ ] Automated validation passes all tests

### Coaching Application
- [ ] Session start in <10 seconds
- [ ] Track >6 pitches per minute
- [ ] Coach satisfaction rating >4.5/5 (survey)
- [ ] Zero accidental calibration changes

### Code Quality
- [ ] Cyclomatic complexity <10 per module
- [ ] Test coverage >80% for both apps
- [ ] No circular dependencies
- [ ] All imports resolve correctly

### User Impact
- [ ] Reduce support tickets by 50%
- [ ] Reduce training time by 60%
- [ ] Increase session efficiency by 30%

---

## Rollout Plan

### Week 1: Internal Testing
- Development team tests both applications
- Fix critical bugs
- Gather initial feedback

### Week 2: Beta Testing
- 5 beta testers (2 installers, 3 coaches)
- Collect feedback surveys
- Make usability improvements

### Week 3: Soft Launch
- Release with legacy UI still available
- Add "Try New UI" prompt
- Monitor adoption metrics

### Month 2-6: Full Adoption
- Promote new UIs based on positive feedback
- Create training videos
- Deprecate legacy UI warnings

### Month 6: Legacy Removal
- Remove legacy UI from main branch
- Archive in `archive/deprecated/`
- Update all documentation

---

## Documentation Deliverables

1. **Setup Guide** (for technicians)
   - Step-by-step wizard instructions
   - Troubleshooting common issues
   - Validation criteria explanations

2. **Coaching Guide** (for coaches)
   - Quick start instructions
   - Feature overview
   - Session workflow best practices

3. **Developer Guide**
   - Architecture documentation
   - Adding new wizard steps
   - Adding new coaching widgets

4. **Migration Guide**
   - Legacy UI → New UIs mapping
   - Data migration (none needed!)
   - FAQ for existing users

---

## Post-Launch Enhancements

### Future Features (3-6 months)

**Setup App:**
- [ ] Cloud backup of calibration packages
- [ ] Automated calibration quality monitoring
- [ ] Remote setup assistance (screen sharing)
- [ ] Calibration templates by venue type

**Coaching App:**
- [ ] Multi-pitcher sessions (quick switch)
- [ ] Voice commands ("start recording", "show replay")
- [ ] Tablet mode (simplified for tablet devices)
- [ ] Parent/player view (read-only spectator mode)

**Both Apps:**
- [ ] Dark mode
- [ ] Localization (Spanish, Japanese)
- [ ] Accessibility improvements
- [ ] Performance metrics dashboard

---

**Document Status:** Implementation Ready
**Created:** 2026-01-16
**Estimated Completion:** 7 working days
**Next Action:** Begin Day 1 - Foundation & Camera Setup
