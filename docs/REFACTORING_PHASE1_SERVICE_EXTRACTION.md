# Phase 1: Service Extraction - Implementation Plan

## Overview

Extract focused services from the monolithic `InProcessPipelineService` (932 LOC) to improve:
- **Testability**: Each service can be unit tested in isolation
- **Reusability**: Detection can run on recorded sessions, recording can be swapped
- **Maintainability**: Clear boundaries and single responsibility
- **Flexibility**: Easy to add new features or swap implementations

## Target Architecture

```
Before:
┌─────────────────────────────────────────┐
│   InProcessPipelineService (932 LOC)    │
│  ┌─────────────────────────────────┐   │
│  │ Camera Management               │   │
│  │ Detection Orchestration         │   │
│  │ Recording I/O                   │   │
│  │ Pitch Tracking                  │   │
│  │ Analysis & Summaries            │   │
│  │ Configuration Management        │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘

After:
┌──────────────────────────────────────────────────────────────┐
│              PipelineOrchestrator (150-200 LOC)              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Capture   │→ │ Detection  │→ │ Recording  │            │
│  │  Service   │  │  Service   │  │  Service   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│         ↓                                                    │
│  ┌────────────┐                                             │
│  │ Analysis   │                                             │
│  │  Service   │                                             │
│  └────────────┘                                             │
└──────────────────────────────────────────────────────────────┘
```

## Service Breakdown

### 1. CaptureService
**Responsibility**: Camera lifecycle and frame capture
**Lines of Code**: ~200-250
**Extracts from InProcessPipelineService**:
- Camera opening/closing
- Frame buffering
- Camera stats collection
- Reconnection handling

**Interface**:
```python
class CaptureService:
    def start_capture(config: AppConfig, left_serial: str, right_serial: str) -> None
    def stop_capture() -> None
    def get_preview_frames() -> Tuple[Frame, Frame]
    def get_stats() -> Dict[str, CameraStats]
    def on_frame_captured(callback: FrameCallback) -> None
    def enable_reconnection(enabled: bool) -> None
```

**Dependencies**:
- `CameraManager` (existing)
- `PipelineInitializer` (existing)
- Config for camera settings

**Benefits**:
- Can test camera handling independently
- Can mock for testing downstream services
- Easy to add camera backends

---

### 2. DetectionService
**Responsibility**: Detection orchestration and stereo matching
**Lines of Code**: ~300-400
**Extracts from InProcessPipelineService**:
- Detection threading pool management
- Frame-to-detection processing
- Stereo matching
- Lane gating
- Detection stats

**Interface**:
```python
class DetectionService:
    def configure_detectors(config: DetectorConfig, mode: Mode) -> None
    def configure_threading(mode: str, worker_count: int) -> None
    def process_frame(camera_id: str, frame: Frame) -> List[Detection]
    def get_latest_detections() -> Dict[str, List[Detection]]
    def get_latest_gated_detections() -> Dict[str, Dict[str, List[Detection]]]
    def get_latest_observations() -> List[StereoObservation]
    def on_observation_detected(callback: ObservationCallback) -> None
```

**Dependencies**:
- `DetectionThreadPool` (existing)
- `DetectionProcessor` (existing)
- `Detector` instances (existing)
- `SimpleStereoMatcher` (existing)
- `LaneGate`, `StereoLaneGate` (existing)

**Benefits**:
- Can run detection on recorded sessions
- Can test detection logic independently
- Easy to swap stereo matching algorithms
- Can benchmark detection performance

---

### 3. RecordingService
**Responsibility**: Async recording of frames and metadata
**Lines of Code**: ~250-300
**Extracts from InProcessPipelineService**:
- Session recording
- Pitch recording
- Video writing
- Manifest generation
- Disk space monitoring

**Interface**:
```python
class RecordingService:
    def start_session(session_name: str, config: AppConfig) -> str
    def stop_session() -> RecordingBundle
    def start_pitch(pitch_id: str) -> None
    def stop_pitch() -> PitchSummary
    def record_frame(camera_id: str, frame: Frame) -> None
    def record_observation(obs: StereoObservation) -> None
    def set_record_directory(path: Path) -> None
    def get_session_dir() -> Optional[Path]
```

**Dependencies**:
- `SessionRecorder` (existing)
- `PitchRecorder` (existing)
- Config for recording settings

**Benefits**:
- Async I/O doesn't block capture
- Can implement cloud recording
- Can replay sessions for debugging
- Easy to add recording formats

---

### 4. AnalysisService
**Responsibility**: Post-processing and pattern detection
**Lines of Code**: ~200-250
**Extracts from InProcessPipelineService**:
- Pitch trajectory analysis
- Session summary generation
- Pattern detection integration
- Strike zone calculation

**Interface**:
```python
class AnalysisService:
    def analyze_pitch(pitch_data: PitchData) -> PitchSummary
    def analyze_session(session_path: Path) -> SessionSummary
    def detect_patterns(session_path: Path) -> PatternAnalysisReport
    def calculate_strike_result(obs: StereoObservation, config: AppConfig) -> StrikeResult
    def get_session_summary() -> SessionSummary
```

**Dependencies**:
- `PitchAnalyzer` (existing)
- `SessionManager` (existing)
- `PatternDetector` (existing)
- Strike zone utilities (existing)

**Benefits**:
- Can run analysis on old sessions
- Can batch analyze multiple sessions
- Easy to add new analysis algorithms
- Can integrate ML models

---

### 5. PipelineOrchestrator
**Responsibility**: Compose services and manage state transitions
**Lines of Code**: ~150-200
**Replaces**: `InProcessPipelineService`

**Interface**:
```python
class PipelineOrchestrator(PipelineService):
    def __init__(
        self,
        capture: CaptureService,
        detection: DetectionService,
        recording: RecordingService,
        analysis: AnalysisService,
        config_service: ConfigService
    ):
        # Wire up event handlers between services
        capture.on_frame_captured(self._handle_frame)
        detection.on_observation_detected(self._handle_observation)

    def _handle_frame(self, camera_id: str, frame: Frame) -> None:
        # Route frames to detection and recording
        if self._is_recording:
            recording.record_frame(camera_id, frame)
        detection.process_frame(camera_id, frame)

    def _handle_observation(self, obs: StereoObservation) -> None:
        # Route observations to recording and pitch tracking
        if self._pitch_tracker:
            self._pitch_tracker.add_observation(obs)
        if self._is_recording_pitch:
            recording.record_observation(obs)
```

**Dependencies**:
- All 4 services above
- `PitchStateMachineV2` (existing)
- `ConfigService` (existing)

**Benefits**:
- Clear orchestration logic
- Easy to test state transitions
- Can swap service implementations
- Minimal code duplication

---

## Implementation Steps

### Step 1: Define Service Interfaces (2-3 hours)
**Files to Create**:
- `app/services/__init__.py`
- `app/services/capture_service.py` - Interface only
- `app/services/detection_service.py` - Interface only
- `app/services/recording_service.py` - Interface only
- `app/services/analysis_service.py` - Interface only

**Approach**:
- Define abstract base classes with `@abstractmethod`
- Document each method with clear contracts
- Define event callback types
- No implementation yet - just contracts

**Validation**:
- All interfaces compile
- No circular dependencies
- Clear documentation

---

### Step 2: Implement CaptureService (4-5 hours)
**Files to Create**:
- `app/services/impl/__init__.py`
- `app/services/impl/capture_service_impl.py`

**Approach**:
1. Extract camera management code from `InProcessPipelineService`
2. Move `_camera_mgr` initialization and usage
3. Implement frame callback mechanism
4. Add preview frame buffering
5. Add stats collection

**Code to Extract**:
```python
# From InProcessPipelineService.__init__:
self._camera_mgr = CameraManager(backend, self._initializer)
self._camera_mgr.set_frame_callback(self._on_frame_captured)
self._camera_mgr.enable_reconnection(enabled=True)
self._camera_mgr.set_camera_state_callback(self._on_camera_state_changed)

# Methods to move:
- start_capture()
- stop_capture()
- get_preview_frames()
- get_stats()
- _on_camera_state_changed()
```

**Testing**:
- Unit test: Can open/close cameras
- Unit test: Frame callbacks work
- Unit test: Stats collection accurate
- Unit test: Reconnection handling works

---

### Step 3: Implement DetectionService (6-8 hours)
**Files to Create**:
- `app/services/impl/detection_service_impl.py`

**Approach**:
1. Extract detection pool management
2. Extract detector configuration
3. Extract stereo matching logic
4. Extract lane gating
5. Implement observation callbacks

**Code to Extract**:
```python
# From InProcessPipelineService.__init__:
self._detection_pool: Optional[DetectionThreadPool] = None
self._detection_processor: Optional[DetectionProcessor] = None
self._lane_gate: Optional[LaneGate] = None
self._stereo: Optional[SimpleStereoMatcher] = None

# Methods to move:
- set_detector_config()
- set_detection_threading()
- get_latest_detections()
- get_latest_gated_detections()
- _detect_frame()
- _on_detection_result()
- _on_stereo_pair()
```

**Testing**:
- Unit test: Detection on synthetic frames
- Unit test: Stereo matching with known geometry
- Unit test: Lane gating filters correctly
- Unit test: Threading modes work
- Integration test: End-to-end detection pipeline

---

### Step 4: Implement RecordingService (5-6 hours)
**Files to Create**:
- `app/services/impl/recording_service_impl.py`

**Approach**:
1. Extract session recorder logic
2. Extract pitch recorder logic
3. Implement async frame writing
4. Add disk space monitoring
5. Implement recording callbacks

**Code to Extract**:
```python
# From InProcessPipelineService.__init__:
self._session_recorder: Optional[SessionRecorder] = None
self._pitch_recorder: Optional[PitchRecorder] = None
self._recording = False
self._record_dir: Optional[Path] = None

# Methods to move:
- start_recording()
- stop_recording()
- set_record_directory()
- get_session_dir()
- _write_record_frame_single()
- _handle_pitch_start()
- _handle_pitch_end()
```

**Testing**:
- Unit test: Session creation
- Unit test: Frame writing
- Unit test: Manifest generation
- Unit test: Disk space checks
- Integration test: Record and verify session

---

### Step 5: Implement AnalysisService (4-5 hours)
**Files to Create**:
- `app/services/impl/analysis_service_impl.py`

**Approach**:
1. Extract pitch analyzer logic
2. Extract session manager logic
3. Integrate pattern detector
4. Extract strike zone calculation

**Code to Extract**:
```python
# From InProcessPipelineService.__init__:
self._pitch_analyzer: Optional[PitchAnalyzer] = None
self._session_manager: Optional[SessionManager] = None

# Methods to move:
- get_plate_metrics()
- get_strike_result()
- set_ball_type()
- set_batter_height_in()
- set_strike_zone_ratios()
- get_session_summary()
```

**Testing**:
- Unit test: Pitch trajectory fitting
- Unit test: Strike zone calculation
- Unit test: Session summary generation
- Integration test: Analyze recorded session

---

### Step 6: Implement PipelineOrchestrator (5-6 hours)
**Files to Create**:
- `app/services/impl/pipeline_orchestrator.py`

**Approach**:
1. Create orchestrator skeleton
2. Wire up service callbacks
3. Implement state management
4. Migrate remaining logic from `InProcessPipelineService`
5. Implement pitch tracking integration

**Code Structure**:
```python
class PipelineOrchestrator(PipelineService):
    def __init__(
        self,
        capture: CaptureService,
        detection: DetectionService,
        recording: RecordingService,
        analysis: AnalysisService,
        config_service: ConfigService,
        pitch_tracker: Optional[PitchStateMachineV2] = None
    ):
        self._capture = capture
        self._detection = detection
        self._recording = recording
        self._analysis = analysis
        self._config_service = config_service
        self._pitch_tracker = pitch_tracker

        # Wire callbacks
        self._capture.on_frame_captured(self._handle_frame)
        self._detection.on_observation_detected(self._handle_observation)

    def _handle_frame(self, camera_id: str, frame: Frame) -> None:
        """Route frames to appropriate services."""
        # Buffer for pitch pre-roll
        if self._pitch_tracker and self._session_active:
            self._pitch_tracker.buffer_frame(camera_id, frame)

        # Route to recording
        if self._is_recording:
            self._recording.record_frame(camera_id, frame)

        # Already handled by capture → detection wiring

    def _handle_observation(self, obs: StereoObservation) -> None:
        """Route observations to pitch tracking and recording."""
        if self._pitch_tracker:
            self._pitch_tracker.add_observation(obs)

        if self._is_recording_pitch:
            self._recording.record_observation(obs)
```

**Testing**:
- Unit test: Service wiring
- Unit test: State transitions
- Integration test: Full capture → detect → record → analyze flow
- Integration test: Pitch tracking workflow

---

### Step 7: Add Service Unit Tests (6-8 hours)
**Files to Create**:
- `tests/services/__init__.py`
- `tests/services/test_capture_service.py`
- `tests/services/test_detection_service.py`
- `tests/services/test_recording_service.py`
- `tests/services/test_analysis_service.py`
- `tests/services/test_pipeline_orchestrator.py`

**Test Coverage**:
- Each service tested in isolation
- Mock dependencies with clear contracts
- Test error handling and edge cases
- Test callback mechanisms
- Integration tests for service composition

**Example Test**:
```python
def test_detection_service_stereo_matching():
    # Arrange
    config = DetectorConfig(...)
    detection_service = DetectionServiceImpl(config)

    left_frame = create_synthetic_frame(ball_at=(100, 200))
    right_frame = create_synthetic_frame(ball_at=(110, 200))

    # Act
    left_detections = detection_service.process_frame("left", left_frame)
    right_detections = detection_service.process_frame("right", right_frame)
    observations = detection_service.get_latest_observations()

    # Assert
    assert len(observations) == 1
    assert observations[0].x_ft == pytest.approx(expected_x, abs=0.1)
```

---

### Step 8: Migrate InProcessPipelineService (2-3 hours)
**Files to Modify**:
- `app/pipeline_service.py`

**Approach**:
1. Keep `InProcessPipelineService` as facade
2. Replace internal implementation with service calls
3. Maintain backward compatibility
4. Add deprecation warnings

**Migration Strategy**:
```python
class InProcessPipelineService(PipelineService):
    """Legacy facade for backward compatibility.

    DEPRECATED: Use PipelineOrchestrator directly.
    This class will be removed in a future version.
    """

    def __init__(self, backend: str = "uvc", radar_client: Optional[RadarGunClient] = None):
        # Create services
        capture = CaptureServiceImpl(backend)
        detection = DetectionServiceImpl()
        recording = RecordingServiceImpl()
        analysis = AnalysisServiceImpl()
        config_service = ConfigService()

        # Create orchestrator
        self._orchestrator = PipelineOrchestrator(
            capture, detection, recording, analysis, config_service
        )

    def start_capture(self, config, left_serial, right_serial, config_path=None):
        """Delegate to orchestrator."""
        return self._orchestrator.start_capture(config, left_serial, right_serial, config_path)

    # ... delegate all other methods
```

**Testing**:
- Ensure all existing tests pass
- Verify MainWindow still works
- Check for performance regressions

---

### Step 9: Update MainWindow (Optional - Can defer to Phase 3)
**Files to Modify**:
- `ui/main_window.py`

**Approach** (if doing now):
1. Import `PipelineOrchestrator` instead of `InProcessPipelineService`
2. Update service instantiation
3. No other changes needed (backward compatible interface)

**Approach** (if deferring):
- Keep using `InProcessPipelineService` facade
- Plan for Phase 3 UI refactoring

---

### Step 10: Integration Testing (3-4 hours)
**Files to Create**:
- `tests/integration/test_service_pipeline.py`

**Test Scenarios**:
1. **Full capture workflow**:
   - Start capture → frames arrive → detection runs → observations generated

2. **Recording workflow**:
   - Start session → record frames → detect pitches → stop session → verify recordings

3. **Pitch tracking**:
   - Simulate pitch → verify pre-roll buffer → verify pitch detection → verify summary

4. **Configuration updates**:
   - Update detector config → verify applied
   - Update strike zone → verify calculation

5. **Error scenarios**:
   - Camera disconnection → verify reconnection
   - Disk full → verify graceful handling
   - Detection failure → verify recovery

---

## Migration Checklist

### Pre-Implementation
- [ ] Read and understand current `InProcessPipelineService` code
- [ ] Document all responsibilities and dependencies
- [ ] Create migration plan document (this file)
- [ ] Get stakeholder approval

### Implementation
- [ ] Step 1: Define service interfaces
- [ ] Step 2: Implement CaptureService
- [ ] Step 3: Implement DetectionService
- [ ] Step 4: Implement RecordingService
- [ ] Step 5: Implement AnalysisService
- [ ] Step 6: Implement PipelineOrchestrator
- [ ] Step 7: Add service unit tests
- [ ] Step 8: Migrate InProcessPipelineService
- [ ] Step 9: Update MainWindow (optional)
- [ ] Step 10: Integration testing

### Post-Implementation
- [ ] Update documentation
- [ ] Code review
- [ ] Performance benchmarking
- [ ] Deploy to staging
- [ ] Monitor for issues
- [ ] Plan Phase 2 (Event-based communication)

---

## Success Criteria

✅ **Testability**
- Each service has 80%+ unit test coverage
- Can mock services for testing downstream code
- Integration tests pass for full pipeline

✅ **Reusability**
- DetectionService can run on recorded sessions
- RecordingService can be used independently
- AnalysisService can batch process sessions

✅ **Maintainability**
- Each service < 400 LOC
- Clear interfaces and contracts
- Single responsibility per service

✅ **Backward Compatibility**
- All existing tests pass
- MainWindow works without changes
- No performance degradation

✅ **Documentation**
- Service interfaces documented
- Architecture diagram updated
- Migration guide written

---

## Estimated Timeline

| Step | Effort | Dependencies |
|------|--------|--------------|
| 1. Define interfaces | 2-3 hours | None |
| 2. CaptureService | 4-5 hours | Step 1 |
| 3. DetectionService | 6-8 hours | Step 1 |
| 4. RecordingService | 5-6 hours | Step 1 |
| 5. AnalysisService | 4-5 hours | Step 1 |
| 6. PipelineOrchestrator | 5-6 hours | Steps 2-5 |
| 7. Unit tests | 6-8 hours | Steps 2-6 |
| 8. Migration | 2-3 hours | Steps 6-7 |
| 9. MainWindow (optional) | 1-2 hours | Step 8 |
| 10. Integration testing | 3-4 hours | Steps 8-9 |

**Total: 38-50 hours (5-6 days full-time)**

---

## Risks and Mitigation

### Risk: Breaking existing functionality
**Mitigation**:
- Keep `InProcessPipelineService` as facade
- Comprehensive test coverage
- Incremental rollout with feature flags

### Risk: Performance regression
**Mitigation**:
- Benchmark before/after
- Profile critical paths
- Optimize hot spots

### Risk: Incomplete extraction
**Mitigation**:
- Detailed code audit of current service
- Comprehensive checklist
- Peer review before merging

### Risk: Testing complexity
**Mitigation**:
- Mock services with clear contracts
- Integration tests for full pipeline
- Incremental testing per service

---

## Next Steps After Phase 1

Once Phase 1 is complete, we can proceed to:

**Phase 2: Event-Based Communication**
- Replace callbacks with typed events
- Implement event bus for service communication
- Add event replay for debugging

**Phase 3: UI Decoupling**
- Introduce view model pattern
- Separate UI state from business logic
- Dependency injection for services

**Phase 4: Plugin Architecture**
- Define plugin interfaces
- Support custom detectors, stereo matchers
- Enable third-party extensions
