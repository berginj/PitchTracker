# PitchTracker - Prioritized Next Steps

**Date:** 2026-01-18
**Current Version:** v1.2.0
**Status:** System Hardening Complete, Production Gaps Identified

---

## Executive Summary

The PitchTracker application is **well-architected and close to production-ready**, with:
- ✅ Comprehensive system hardening (Phase 2-4 complete)
- ✅ Professional installer and auto-update mechanism
- ✅ ML data collection system (v1.2.0)
- ✅ 287 tests with 98% pass rate
- ✅ Extensive documentation (37 markdown files)

However, **critical stability issues remain** that must be addressed before production deployment to end users.

---

## Critical Path to Production

### Priority Level Definitions

- **🔴 CRITICAL:** Blocks production deployment, causes data loss or crashes
- **🟠 HIGH:** Production quality issues, impacts reliability or user experience
- **🟡 MEDIUM:** Nice to have, improves quality but not blocking
- **🟢 LOW:** Future enhancements, optimization, polish

---

## 🔴 CRITICAL PRIORITY (Do First - Blocks Production)

### 1. Fix Silent Thread Failures in Detection Pipeline
**Impact:** Data loss, no user feedback when detection fails
**Effort:** 2-3 hours
**Status:** ❌ Not fixed

**Problem:**
```python
# app/pipeline/detection/threading_pool.py:213-216
try:
    detections = self._detect_callback(label, frame)
except Exception:
    detections = []  # ← Silent failure! No logging!
```

**Fix Required:**
- Add exception logging with traceback
- Publish error to error bus (integration done, just need to call it)
- Track consecutive failures and alert after 10 failures
- Add error notification to UI

**Files to modify:**
- `app/pipeline/detection/threading_pool.py`

**Acceptance Criteria:**
- [ ] All exceptions logged with full traceback
- [ ] Errors published to error bus with ErrorCategory.DETECTION
- [ ] UI shows error notification after 10 consecutive failures
- [ ] Test with broken detector to verify error handling

---

### 2. Implement Backpressure Mechanism
**Impact:** Memory exhaustion, system crashes under load
**Effort:** 2-3 hours
**Status:** ❌ Not implemented

**Problem:**
```python
# app/pipeline/camera_management.py:383-389
# Camera capture threads produce frames faster than detection can consume
# Queues fill up, memory grows unbounded, system crashes
```

**Fix Required:**
- Add queue full detection in camera capture threads
- Block or skip frames when detection queue is full
- Log frame drop events
- Alert user when dropping frames consistently

**Files to modify:**
- `app/pipeline/camera_management.py` (capture threads)
- `app/pipeline/detection/threading_pool.py` (queue management)

**Acceptance Criteria:**
- [ ] Camera threads block when queue full (backpressure)
- [ ] Frame drop counter increments correctly
- [ ] Warning logged when frames dropped
- [ ] UI status shows "Dropping frames" message
- [ ] Test with slow detector to verify backpressure works

---

### 3. Add Continuous Disk Space Monitoring
**Impact:** Silent data loss when disk fills during recording
**Effort:** 1-2 hours
**Status:** ⚠️ Partially done (Phase 1), needs integration

**Problem:**
```python
# app/pipeline/recording/session_recorder.py:59-92
# Disk space checked only at session start
# If disk fills during recording, writes silently fail
```

**Fix Status:**
- ✅ Background monitoring thread implemented (Phase 1)
- ✅ 3-tier thresholds (50GB warning, 10GB critical, 5GB emergency)
- ❌ Not integrated into pipeline service
- ❌ Not wired to error bus for UI notifications

**Fix Required:**
- Wire disk space monitor to error bus
- Show UI notification when disk space critical
- Auto-stop recording when disk space < 10GB
- Add disk space to status bar

**Files to modify:**
- `app/pipeline_service.py` (integrate monitoring)
- `ui/main_window.py` (add to status bar)

**Acceptance Criteria:**
- [ ] Disk space checked every 5 seconds during recording
- [ ] Warning notification at 50GB free
- [ ] Critical notification at 10GB free
- [ ] Recording auto-stops at 5GB free
- [ ] Test by filling disk during recording

---

### 4. Fix Video Codec Fallback Mechanism
**Impact:** Video file corruption when primary codec fails
**Effort:** 1-2 hours
**Status:** ⚠️ Partially done (Phase 1), needs testing

**Problem:**
```python
# app/pipeline/recording/session_recorder.py:257-298
# Codec fallback implemented but not tested
# May still corrupt files on codec failure
```

**Fix Status:**
- ✅ Codec fallback implemented (MJPG → XVID → H264 → MP4V)
- ✅ Resource cleanup on failures
- ❌ Not tested with actual codec failures
- ❌ Edge cases not handled (left succeeds, right fails)

**Fix Required:**
- Test codec fallback with missing codecs
- Ensure left/right cameras use same codec
- Add clear error message when all codecs fail
- Verify no file corruption on codec switch

**Files to verify:**
- `app/pipeline/recording/session_recorder.py`

**Acceptance Criteria:**
- [ ] Test with MJPG disabled → Falls back to XVID
- [ ] Test with all codecs disabled → Clear error message
- [ ] Verify left and right use matching codecs
- [ ] No file corruption when codec changes
- [ ] Unit test with mocked codec failures

---

### 5. Fix Resource Leaks from Timeout Threads
**Impact:** 10+ ghost threads after operations, memory leak
**Effort:** 1-2 hours
**Status:** ✅ **DONE** (Phase 1 - ThreadPoolExecutor)

**Fix Status:**
- ✅ Replaced daemon threads with ThreadPoolExecutor
- ✅ Automatic thread cleanup
- ✅ Tested with 14 unit tests (all passing)

**Verification Needed:**
- [ ] Manual test: Run 100 operations, check thread count
- [ ] Verify no threads remain after operations complete
- [ ] Check memory doesn't grow over time

---

## 🟠 HIGH PRIORITY (Do Next - Production Quality)

### 6. Test Installer on Clean Windows System
**Impact:** Users can't install application
**Effort:** 1-2 hours
**Status:** ❌ Not tested

**What to Test:**
- [ ] Download installer from GitHub releases
- [ ] Run on Windows 10/11 without Python/dev tools
- [ ] Verify desktop shortcut created
- [ ] Launch application from shortcut
- [ ] Test basic capture/recording functionality
- [ ] Check for any missing DLLs or dependencies
- [ ] Verify uninstaller works correctly

**Blockers:**
- Requires access to clean Windows VM or separate machine
- Current: Built and published, but not verified

**Deliverable:**
- Document installation issues if any
- Update installer script if needed
- Create installation troubleshooting guide

---

### 7. Verify Auto-Update Mechanism Works
**Impact:** Users can't get updates, stuck on old versions
**Effort:** 30-60 minutes
**Status:** ❌ Not tested

**What to Test:**
- [ ] Install v1.0.0 from GitHub releases
- [ ] Publish fake v1.0.1 release
- [ ] Launch app and check for updates
- [ ] Verify update dialog shows new version
- [ ] Test "Download Update" button
- [ ] Verify update installs correctly
- [ ] Check app restarts with new version

**Files Involved:**
- `updater.py` - GitHub API integration
- `ui/dialogs/update_dialog.py` - UI for updates

**Deliverable:**
- Confirm auto-update works end-to-end
- Document any issues found
- Add user documentation for updates

---

### 8. Add End-to-End Integration Tests
**Impact:** Unknown behavior in production, bugs not caught
**Effort:** 2-4 hours
**Status:** ❌ Not implemented

**Tests Needed:**

**Test 1: Full Pipeline with Simulated Cameras**
```python
def test_full_pipeline_simulated():
    """Test capture → detection → recording → export with sim cameras."""
    service = InProcessPipelineService(backend="sim")
    service.start_capture(config, "left", "right")
    service.start_recording("test-session")
    # Run for 10 seconds
    time.sleep(10)
    bundle = service.stop_recording()
    service.stop_capture()

    # Verify files created
    assert session_dir.exists()
    assert (session_dir / "session_left.avi").exists()
    assert (session_dir / "session_right.avi").exists()
    assert (session_dir / "manifest.json").exists()
```

**Test 2: Error Recovery**
```python
def test_error_recovery():
    """Test system recovers from detection errors."""
    # Inject failing detector
    # Verify error published to error bus
    # Verify system continues operating
    # Verify UI shows error notification
```

**Test 3: ML Data Export**
```python
def test_ml_data_export():
    """Test ML data export with real recording."""
    # Enable ML data collection
    # Record session with sim cameras
    # Verify detection JSON created
    # Verify observation JSON created
    # Verify frames exported as PNG
    # Verify calibration metadata exported
```

**Deliverable:**
- Create `tests/integration/` directory
- Add 5-10 integration tests
- Run in CI/CD pipeline
- Document test results

---

### 9. Test ML Data Export with Real Cameras
**Impact:** ML features may not work in production
**Effort:** 1-2 hours (if cameras available)
**Status:** ❌ Not tested

**What to Test:**
- [ ] Enable ML data collection in config
- [ ] Record session with real cameras
- [ ] Throw some pitches
- [ ] Verify detection JSON has real detections
- [ ] Verify observations JSON has 3D coordinates
- [ ] Verify frame PNGs saved at correct times
- [ ] Verify calibration export is complete
- [ ] Test `export_ml_submission.py` to create ZIP

**Blocker:**
- Requires access to stereo camera setup
- Current: Feature implemented but untested with real data

**Deliverable:**
- Confirm ML data export works with real cameras
- Document any issues or improvements needed
- Add example ML submission to documentation

---

### 10. Add State Corruption Recovery
**Impact:** Undefined behavior when errors occur mid-operation
**Effort:** 1-2 hours
**Status:** ❌ Not implemented

**Problem:**
```python
# app/pipeline/pitch_tracking_v2.py:394-404
# If callback throws exception, state machine may be corrupted
# No recovery mechanism to reset to clean state
```

**Fix Required:**
- Add try/except around all callbacks
- Reset state machine to INACTIVE on error
- Clear all buffers and observations
- Log error details
- Publish to error bus

**Files to modify:**
- `app/pipeline/pitch_tracking_v2.py`

**Acceptance Criteria:**
- [ ] Exception in `on_pitch_start` callback doesn't corrupt state
- [ ] Exception in `on_pitch_end` callback doesn't corrupt state
- [ ] State machine resets to INACTIVE after error
- [ ] Error logged and published to error bus
- [ ] Test with callbacks that throw exceptions

---

## 🟡 MEDIUM PRIORITY (After Critical/High Fixed)

### 11. Add User-Facing Documentation
**Impact:** Users struggle with setup and troubleshooting
**Effort:** 2-3 hours
**Status:** ❌ Not created

**Documents Needed:**

**FAQ.md (Frequently Asked Questions)**
```markdown
Q: Why can't I see my cameras?
A: Check USB connection, try different ports, restart application

Q: Why is my video choppy?
A: Reduce resolution (1280x720), lower FPS (30), close other programs

Q: How do I calibrate the strike zone?
A: Use Calibration Wizard from Setup menu, follow on-screen instructions

Q: Why am I getting disk space warnings?
A: Free up at least 50GB, check recording output directory

Q: How do I export my session data?
A: File → Export Session → Select format (JSON/CSV/ZIP)
```

**TROUBLESHOOTING.md**
```markdown
# Camera Issues
- USB 3.0 required for 60 FPS
- Some USB hubs don't provide enough power
- Windows may require camera permissions

# Performance Issues
- Reduce resolution if CPU > 80%
- Close background applications
- Update graphics drivers

# Installation Issues
- Requires Windows 10 version 1809 or later
- May need Visual C++ Redistributable
- Check Windows Defender isn't blocking
```

**CALIBRATION_TIPS.md**
```markdown
# Quick Calibration Guide
1. Place cameras 6-8 feet apart
2. Angle inward toward strike zone
3. Use checkerboard pattern for intrinsics
4. Measure exact distance between cameras
5. Verify calibration with test pitch
```

**Deliverable:**
- Create 3 new documentation files
- Add links to README.md
- Include in installer as PDF

---

### 12. Add Performance Benchmarks
**Impact:** Don't know if system meets performance targets
**Effort:** 1-2 hours
**Status:** ❌ Not implemented

**Benchmarks Needed:**

**Benchmark 1: Frame Processing Throughput**
```python
def benchmark_frame_processing():
    """Measure frames per second through detection pipeline."""
    # Process 1000 frames
    # Measure total time
    # Calculate FPS
    # Target: 60 FPS minimum
```

**Benchmark 2: Memory Stability**
```python
def benchmark_memory_stability():
    """Check for memory leaks over extended operation."""
    # Run pipeline for 30 minutes
    # Sample memory every 10 seconds
    # Verify memory doesn't grow > 10%
    # Target: Stable memory usage
```

**Benchmark 3: Detection Latency**
```python
def benchmark_detection_latency():
    """Measure time from frame capture to detection result."""
    # Measure 1000 frames
    # Calculate p50, p95, p99 latency
    # Target: <20ms p95
```

**Deliverable:**
- Create `benchmarks/` directory
- Add 5-10 benchmark scripts
- Document baseline performance
- Add CI check for performance regression

---

### 13. Add Memory Leak Detection Tests
**Impact:** Application crashes after extended use
**Effort:** 1-2 hours
**Status:** ❌ Not implemented

**Tests Needed:**

```python
def test_no_memory_leak_capture():
    """Verify no memory leak during extended capture."""
    import tracemalloc
    tracemalloc.start()

    # Capture for 5 minutes
    initial_memory = tracemalloc.get_traced_memory()[0]
    time.sleep(300)
    final_memory = tracemalloc.get_traced_memory()[0]

    growth = (final_memory - initial_memory) / initial_memory
    assert growth < 0.10, f"Memory grew {growth*100:.1f}%, expected <10%"
```

**Deliverable:**
- Add memory leak tests to test suite
- Run weekly in CI/CD
- Document memory usage patterns

---

### 14. Archive or Delete V1 Pitch Tracking Code
**Impact:** Code confusion, maintenance burden
**Effort:** 30 minutes
**Status:** ❌ Not done

**Files to Handle:**
- `app/pipeline/pitch_tracking.py` (194 lines) - **Unused, V2 is active**

**Options:**
1. **Delete:** Remove completely (can recover from git history)
2. **Archive:** Move to `archive/pitch_tracking_v1.py` with comment
3. **Keep:** Add warning comment that it's deprecated

**Recommendation:** Archive with documentation note

**Deliverable:**
- Move to `archive/` directory
- Update documentation to reference V2 only
- Add git history reference in archive comment

---

## 🟢 LOW PRIORITY (Future Enhancements)

### 15. Add Video Walkthrough for Setup Wizard
**Impact:** Easier onboarding for new users
**Effort:** 2-4 hours (recording + editing)
**Status:** ❌ Not created

**Content Needed:**
- Camera connection and positioning
- ROI drawing tutorial
- Calibration procedure
- First recording session
- Data export walkthrough

**Deliverable:**
- 5-10 minute video on YouTube
- Link from README.md and installer

---

### 16. Add Concurrent Camera Stress Tests
**Impact:** Unknown behavior under heavy load
**Effort:** 2-3 hours
**Status:** ❌ Not implemented

**Tests Needed:**
- 4+ cameras simultaneously (if hardware available)
- 120 FPS capture for extended period
- 1000+ pitch recording session
- Rapid start/stop cycles

**Deliverable:**
- Stress test suite
- Document maximum supported load
- Performance tuning recommendations

---

### 17. Obtain Code Signing Certificate
**Impact:** Windows SmartScreen warning on install
**Effort:** 1-2 hours setup + $200-400/year
**Status:** ❌ Not obtained

**Steps:**
1. Choose certificate authority (Sectigo, DigiCert, SSL.com)
2. Purchase EV code signing certificate ($200-400/year)
3. Complete identity verification (2-7 days)
4. Install certificate on build machine
5. Update build script to sign exe and installer
6. Test signed installer on clean Windows

**Deliverable:**
- Signed installer without SmartScreen warning
- Document signing process
- Update BUILD_INSTRUCTIONS.md

---

### 18. Add Camera Reconnection Integration
**Impact:** Better reliability when cameras disconnect
**Effort:** 2-3 hours
**Status:** ⚠️ Feature built, not wired to cameras

**What to Do:**
- Camera reconnection manager exists (Phase 3)
- Not yet connected to camera error callbacks
- Need to wire camera disconnection → reconnection manager
- Test with USB disconnect/reconnect

**Files to modify:**
- `app/pipeline/camera_management.py` (add callback)
- Wire to `app/camera/reconnection.py`

**Deliverable:**
- Automatic camera reconnection on USB disconnect
- UI notification: "Camera reconnecting..."
- Success message: "Camera reconnected"
- Test with physical USB disconnect

---

## Implementation Roadmap

### Week 1: Critical Fixes (12-16 hours)
**Goal:** Fix all blocking production issues

- Day 1-2: Fix silent thread failures (#1) - 3 hrs
- Day 2-3: Implement backpressure (#2) - 3 hrs
- Day 3-4: Continuous disk monitoring (#3) - 2 hrs
- Day 4: Test codec fallback (#4) - 2 hrs
- Day 5: Verify resource leak fix (#5) - 2 hrs

**Deliverable:** Application is stable and production-ready

---

### Week 2: Deployment Verification (8-12 hours)
**Goal:** Verify installer and updates work

- Day 1: Test installer on clean system (#6) - 2 hrs
- Day 1: Verify auto-update (#7) - 1 hr
- Day 2-3: Add integration tests (#8) - 4 hrs
- Day 4: Test ML data export (#9) - 2 hrs
- Day 5: State corruption recovery (#10) - 2 hrs

**Deliverable:** Verified working deployment

---

### Week 3: Documentation & Quality (6-10 hours)
**Goal:** Professional user experience

- Day 1-2: User documentation (#11) - 3 hrs
- Day 3: Performance benchmarks (#12) - 2 hrs
- Day 4: Memory leak tests (#13) - 2 hrs
- Day 5: Archive V1 code (#14) - 1 hr

**Deliverable:** Complete user-facing documentation

---

### Week 4+: Enhancements (Optional)
**Goal:** Polish and future-proofing

- Video walkthrough (#15) - 4 hrs
- Stress tests (#16) - 3 hrs
- Code signing certificate (#17) - 2 hrs + cost
- Camera reconnection (#18) - 3 hrs

**Deliverable:** Professional-grade product

---

## Success Criteria

### Phase 1: Critical Fixes Complete
- [ ] All 5 critical issues fixed
- [ ] Unit tests added for all fixes
- [ ] Manual testing confirms stability
- [ ] No silent failures or crashes in 1-hour stress test

### Phase 2: Deployment Verified
- [ ] Installer tested on clean Windows 10/11
- [ ] Auto-update verified working
- [ ] Integration tests pass
- [ ] ML data export validated with real data

### Phase 3: Production Ready
- [ ] All documentation complete
- [ ] Performance benchmarks documented
- [ ] No memory leaks detected
- [ ] User guide and troubleshooting available

### Phase 4: Professional Product
- [ ] Video walkthrough published
- [ ] Code signed (if budget allows)
- [ ] Stress tested at scale
- [ ] Camera reconnection working

---

## Risk Assessment

### High Risk Items
1. **Installer not working** - Could block all deployments
2. **Silent failures in production** - Data loss, user frustration
3. **Memory leaks** - Application crashes after extended use

### Mitigation Strategies
1. Test installer on VM before distributing
2. Add logging and error notifications for all failures
3. Add memory leak detection tests and run regularly

---

## Resource Requirements

### Development Time
- **Critical Path:** 12-16 hours (Week 1)
- **Deployment:** 8-12 hours (Week 2)
- **Quality:** 6-10 hours (Week 3)
- **Total:** 26-38 hours for production-ready application

### Equipment Needed
- Clean Windows 10/11 machine or VM (for installer testing)
- Stereo camera setup (for hardware testing, optional)

### Budget (Optional)
- Code signing certificate: $200-400/year
- Video hosting: Free (YouTube) or $5/month (Vimeo)

---

## Conclusion

The PitchTracker application is **very close to production-ready** with excellent architecture and comprehensive hardening. The main blockers are:

1. **Critical stability issues** that need fixing (12-16 hours)
2. **Deployment verification** to ensure installer works (8-12 hours)
3. **Documentation** for users to get started (6-10 hours)

**Recommended:** Focus on Week 1 (Critical Fixes) immediately, then Week 2 (Deployment) before any wider distribution.

After these 2-3 weeks, the application will be **truly production-ready** for end users.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Next Review:** After Week 1 completion
