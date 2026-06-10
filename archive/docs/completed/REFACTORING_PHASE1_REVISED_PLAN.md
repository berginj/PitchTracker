# Phase 1: Service Extraction - REVISED Implementation Plan

**Date**: 2026-01-21
**Based On**: Architecture review and user decisions
**Scope**: Complete extraction (all 4 services, 5-6 days)
**Approach**: Event-driven, recording-first, clean break

## Executive Summary

### Key Decisions
1. ✅ **Recording Fidelity is PRIMARY** - No dropped frames, detection can lag
2. ✅ **Event-Driven Architecture** - EventBus from Day 1 with pub/sub pattern
3. ✅ **Recording First** - Extract hardest service first
4. ✅ **Parallel Frame Flow** - Recording AND Detection receive frames simultaneously
5. ✅ **Orchestrator Owns State Machine** - PitchStateMachineV2 managed centrally
6. ✅ **Static Config** - Set at session start, no runtime propagation needed
7. ✅ **Clean Break** - No backward compatibility facade
8. ✅ **Integration Tests Only** - Skip unit tests, focus on end-to-end validation

### Changes from Original Plan
| Aspect | Original | Revised | Reason |
|--------|----------|---------|--------|
| **Order** | Capture → Detection → Analysis → Recording | EventBus → Recording → Capture → Detection → Analysis | Recording fidelity priority |
| **Frame Flow** | Sequential (Capture → Detection) | Parallel (Capture → Recording + Detection) | No dropped frames |
| **State Machine** | In Recording Service | In PipelineOrchestrator | Central coordination |
| **Communication** | Phase 2 (callbacks first) | Phase 1 (EventBus from start) | Clean architecture from day 1 |
| **Compatibility** | Facade pattern | Clean break | Simpler migration |
| **Config Updates** | Event-based propagation | Static per session | Not needed during session |

---

## Revised Architecture

### Event Flow

```
Camera Hardware (30fps each)
    ↓
CaptureService
    ↓
EventBus.publish(FrameCapturedEvent)
    ├─→ RecordingService.on_frame() [PRIORITY - NO DROPS]
    └─→ DetectionService.on_frame() [BEST EFFORT]
            ↓
        Detect objects
            ↓
        EventBus.publish(ObservationDetectedEvent)
            ├─→ RecordingService.on_observation()
            ├─→ AnalysisService.on_observation()
            └─→ PipelineOrchestrator.on_observation()
                    ↓
                PitchStateMachineV2.update()
                    ├─→ [INACTIVE → ACTIVE]
                    │   EventBus.publish(PitchStartEvent)
                    │       └─→ RecordingService.start_pitch()
                    │
                    └─→ [ACTIVE → FINALIZED]
                        EventBus.publish(PitchEndEvent)
                            ├─→ RecordingService.end_pitch()
                            └─→ AnalysisService.analyze_pitch()
```

### Service Responsibilities (Final)

| Service | Responsibility | Events Published | Events Subscribed |
|---------|---------------|------------------|-------------------|
| **CaptureService** | Camera management, frame capture | FrameCaptured | None |
| **DetectionService** | Detection, stereo matching | ObservationDetected | FrameCaptured |
| **RecordingService** | Video/metadata recording | None | FrameCaptured, ObservationDetected, PitchStart, PitchEnd |
| **AnalysisService** | Trajectory fitting, summaries | None | ObservationDetected, PitchEnd |
| **PipelineOrchestrator** | State machine, coordination | PitchStart, PitchEnd | ObservationDetected |

---

## Implementation Steps

### Step 0: EventBus Infrastructure (4-6 hours) [NEW]

**Create**: `app/events/event_bus.py`

#### Event Definitions

```python
from dataclasses import dataclass
from typing import Callable, TypeVar
from contracts import Frame, StereoObservation

@dataclass(frozen=True)
class FrameCapturedEvent:
    """Published when a frame is captured from camera."""
    camera_id: str  # "left" or "right"
    frame: Frame
    timestamp_ns: int

@dataclass(frozen=True)
class ObservationDetectedEvent:
    """Published when stereo observation is generated."""
    observation: StereoObservation
    timestamp_ns: int

@dataclass(frozen=True)
class PitchStartEvent:
    """Published when pitch detection begins."""
    pitch_id: str
    pitch_index: int
    timestamp_ns: int

@dataclass(frozen=True)
class PitchEndEvent:
    """Published when pitch is finalized."""
    pitch_id: str
    observations: List[StereoObservation]
    timestamp_ns: int
```

#### EventBus Implementation

```python
EventType = TypeVar('EventType')
EventHandler = Callable[[EventType], None]

class EventBus:
    """Thread-safe event bus for service communication."""

    def __init__(self):
        self._subscribers: Dict[Type, List[EventHandler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: Type[EventType], handler: EventHandler) -> None:
        """Register handler for event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def publish(self, event: EventType) -> None:
        """Publish event to all subscribers."""
        event_type = type(event)
        handlers = []

        with self._lock:
            handlers = self._subscribers.get(event_type, []).copy()

        # Call handlers outside lock
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}", exc_info=True)
                publish_error(
                    category=ErrorCategory.INTERNAL,
                    severity=ErrorSeverity.WARNING,
                    message=f"Event handler failed: {e}"
                )
```

**Testing**:
- Unit test: Subscribe and publish events
- Unit test: Multiple subscribers receive same event
- Unit test: Error in one handler doesn't affect others
- Unit test: Thread safety with concurrent publishers

**Success Criteria**:
- EventBus compiles and imports successfully
- All event types defined with proper dataclasses
- Thread-safe publish/subscribe works
- Error handling prevents handler failures from crashing

**Files Created**:
- `app/events/event_bus.py` (~150 LOC)
- `app/events/event_types.py` (~80 LOC)
- `tests/integration/test_event_bus.py` (~100 LOC)

---

### Step 1: RecordingService Implementation (8-10 hours)

**Priority**: HIGHEST (recording fidelity is critical)

**Create**: `app/services/recording/implementation.py`

#### Key Responsibilities
1. Subscribe to FrameCaptured events (priority handling)
2. Subscribe to ObservationDetected events
3. Subscribe to PitchStart/PitchEnd events
4. Manage SessionRecorder (full session video)
5. Manage PitchRecorder (individual pitches with pre/post-roll)
6. Pre-roll frame buffering (60 frames × 2 cameras)
7. Disk space monitoring

#### Implementation Strategy

```python
class RecordingServiceImpl(RecordingService):
    def __init__(self, event_bus: EventBus, config: AppConfig):
        self._event_bus = event_bus
        self._config = config

        # Pre-roll buffer (60 frames × 2 cameras)
        self._pre_roll_buffer: Dict[str, deque[Frame]] = {
            "left": deque(maxlen=60),
            "right": deque(maxlen=60)
        }

        # Recorders
        self._session_recorder: Optional[SessionRecorder] = None
        self._pitch_recorder: Optional[PitchRecorder] = None

        # State
        self._is_recording_session = False
        self._is_recording_pitch = False
        self._current_pitch_id: Optional[str] = None

        # Thread safety
        self._lock = threading.Lock()

    def start_session(self, session_name: str, config: AppConfig, mode: Optional[str] = None) -> str:
        """Start recording session."""
        with self._lock:
            self._session_recorder = SessionRecorder(config, ...)
            self._session_recorder.start_session(session_name)
            self._is_recording_session = True

            # Subscribe to events
            self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured)
            self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation)
            self._event_bus.subscribe(PitchStartEvent, self._on_pitch_start)
            self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end)

            return self._check_disk_space()

    def _on_frame_captured(self, event: FrameCapturedEvent) -> None:
        """Handle frame capture event - PRIORITY: NO DROPS."""
        # Always buffer for pre-roll
        self._pre_roll_buffer[event.camera_id].append(event.frame)

        # Write to session if recording
        if self._is_recording_session and self._session_recorder:
            self._session_recorder.write_frame(event.camera_id, event.frame)

        # Write to pitch if recording
        if self._is_recording_pitch and self._pitch_recorder:
            self._pitch_recorder.write_frame(event.camera_id, event.frame)

    def _on_pitch_start(self, event: PitchStartEvent) -> None:
        """Handle pitch start - create recorder and write pre-roll."""
        with self._lock:
            self._current_pitch_id = event.pitch_id
            self._pitch_recorder = PitchRecorder(...)
            self._pitch_recorder.start_pitch(event.pitch_id)

            # Write pre-roll frames
            for camera_id in ["left", "right"]:
                for frame in self._pre_roll_buffer[camera_id]:
                    self._pitch_recorder.write_frame(camera_id, frame)

            self._is_recording_pitch = True
```

**Testing**:
- Integration test: Start session, capture frames, verify video written
- Integration test: Pre-roll buffer captures frames before pitch
- Integration test: Pitch start creates recorder, writes pre-roll
- Integration test: Pitch end finalizes recorder, writes manifest
- Integration test: Disk space monitoring triggers emergency stop

**Success Criteria**:
- All frames captured to session video (no drops)
- Pre-roll buffer works correctly
- Pitch recording lifecycle (start → write → end) works
- Disk space monitoring functional

**Files Created**:
- `app/services/recording/implementation.py` (~280 LOC)
- `tests/integration/test_recording_service.py` (~150 LOC)

---

### Step 2: CaptureService Implementation (4-5 hours)

**Priority**: HIGH (feeds Recording)

**Create**: `app/services/capture/implementation.py`

#### Key Responsibilities
1. Manage camera lifecycle (open/close)
2. Capture frames from both cameras
3. Publish FrameCaptured events to EventBus
4. Handle camera reconnection
5. Provide preview frames for UI

#### Implementation Strategy

```python
class CaptureServiceImpl(CaptureService):
    def __init__(self, event_bus: EventBus, backend: str = "uvc"):
        self._event_bus = event_bus
        self._camera_mgr = CameraManager(backend, initializer)

        # Set callback to publish events
        self._camera_mgr.set_frame_callback(self._on_camera_frame)

    def _on_camera_frame(self, camera_id: str, frame: Frame) -> None:
        """Camera callback - publish to EventBus."""
        event = FrameCapturedEvent(
            camera_id=camera_id,
            frame=frame,
            timestamp_ns=time.time_ns()
        )
        self._event_bus.publish(event)
```

**Testing**:
- Integration test: Start capture, verify FrameCaptured events published
- Integration test: Both cameras publish events
- Integration test: Frame rate matches expected (30fps)
- Integration test: Reconnection works after disconnect

**Success Criteria**:
- Events published for every captured frame
- No frame drops during event publishing
- Reconnection functional

**Files Created**:
- `app/services/capture/implementation.py` (~200 LOC)
- `tests/integration/test_capture_service.py` (~100 LOC)

---

### Step 3: DetectionService Implementation (6-8 hours)

**Priority**: MEDIUM (best-effort, can lag behind Recording)

**Create**: `app/services/detection/implementation.py`

#### Key Responsibilities
1. Subscribe to FrameCaptured events
2. Run detection on frames (async, best-effort)
3. Perform stereo matching
4. Publish ObservationDetected events
5. Maintain detection statistics

#### Implementation Strategy

```python
class DetectionServiceImpl(DetectionService):
    def __init__(self, event_bus: EventBus, config: AppConfig):
        self._event_bus = event_bus
        self._detection_pool = DetectionThreadPool()
        self._detection_processor = DetectionProcessor()

        # Subscribe to frame events
        self._event_bus.subscribe(FrameCapturedEvent, self._on_frame_captured)

        # Set processor callback to publish observations
        self._detection_processor.set_stereo_pair_callback(self._on_stereo_pair)

    def _on_frame_captured(self, event: FrameCapturedEvent) -> None:
        """Handle frame event - enqueue for detection."""
        # Best effort - may drop if queue full
        try:
            self._detection_pool.enqueue_frame(event.camera_id, event.frame)
        except queue.Full:
            logger.warning(f"Detection queue full, dropping frame")

    def _on_stereo_pair(self, observations: List[StereoObservation], ...) -> None:
        """Stereo callback - publish observations."""
        for obs in observations:
            event = ObservationDetectedEvent(
                observation=obs,
                timestamp_ns=time.time_ns()
            )
            self._event_bus.publish(event)
```

**Testing**:
- Integration test: Frame events trigger detection
- Integration test: Observations published after stereo matching
- Integration test: Detection can lag without blocking capture
- Integration test: Queue overflow handled gracefully

**Success Criteria**:
- Detections run asynchronously
- Observations published correctly
- No blocking of capture/recording

**Files Created**:
- `app/services/detection/implementation.py` (~350 LOC)
- `tests/integration/test_detection_service.py` (~120 LOC)

---

### Step 4: AnalysisService Implementation (4-5 hours)

**Priority**: LOW (post-processing only)

**Create**: `app/services/analysis/implementation.py`

#### Key Responsibilities
1. Subscribe to ObservationDetected events (buffer for pitch)
2. Subscribe to PitchEnd events (analyze trajectory)
3. Calculate strike zone
4. Generate pitch summaries
5. Aggregate session statistics

#### Implementation Strategy

```python
class AnalysisServiceImpl(AnalysisService):
    def __init__(self, event_bus: EventBus, config: AppConfig):
        self._event_bus = event_bus
        self._pitch_analyzer = PitchAnalyzer(config, ...)
        self._session_manager = SessionManager()

        # Current pitch observations buffer
        self._current_pitch_observations: List[StereoObservation] = []

        # Subscribe to events
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation)
        self._event_bus.subscribe(PitchEndEvent, self._on_pitch_end)

    def _on_observation(self, event: ObservationDetectedEvent) -> None:
        """Buffer observations for current pitch."""
        self._current_pitch_observations.append(event.observation)

    def _on_pitch_end(self, event: PitchEndEvent) -> None:
        """Analyze pitch and generate summary."""
        summary = self._pitch_analyzer.analyze_pitch(
            event.observations or self._current_pitch_observations
        )
        self._session_manager.add_pitch(summary)
        self._current_pitch_observations.clear()
```

**Testing**:
- Integration test: Observations buffered correctly
- Integration test: Pitch analysis triggered on PitchEnd
- Integration test: Session summary updated

**Success Criteria**:
- Pitch analysis completes correctly
- Session summaries accurate

**Files Created**:
- `app/services/analysis/implementation.py` (~220 LOC)
- `tests/integration/test_analysis_service.py` (~100 LOC)

---

### Step 5: PipelineOrchestrator Implementation (6-8 hours)

**Priority**: CRITICAL (coordinates everything)

**Create**: `app/services/orchestrator/pipeline_orchestrator.py`

#### Key Responsibilities
1. Create and wire all services
2. Manage PitchStateMachineV2
3. Subscribe to ObservationDetected events (feed to state machine)
4. Publish PitchStart/PitchEnd events
5. Implement PipelineService interface
6. Route UI queries to appropriate services

#### Implementation Strategy

```python
class PipelineOrchestrator(PipelineService):
    """Orchestrates all services and owns pitch state machine."""

    def __init__(self, backend: str = "uvc", radar_client: Optional[RadarGunClient] = None):
        # Create event bus
        self._event_bus = EventBus()

        # Create services
        self._capture = CaptureServiceImpl(self._event_bus, backend)
        self._detection = DetectionServiceImpl(self._event_bus, config)
        self._recording = RecordingServiceImpl(self._event_bus, config)
        self._analysis = AnalysisServiceImpl(self._event_bus, config)

        # Pitch state machine (owned by orchestrator)
        self._pitch_tracker: Optional[PitchStateMachineV2] = None

        # Subscribe to observation events
        self._event_bus.subscribe(ObservationDetectedEvent, self._on_observation)

    def start_capture(self, config: AppConfig, left_serial: str, right_serial: str, config_path: Optional[Path] = None) -> None:
        """Implement PipelineService interface - delegate to services."""
        self._capture.start_capture(config, left_serial, right_serial, config_path)
        self._detection.configure_detectors(config.detector, config.mode)

    def start_recording(self, pitch_id: Optional[str] = None, session_name: Optional[str] = None, mode: Optional[str] = None) -> str:
        """Start recording and initialize pitch tracking."""
        # Start recording service
        warning = self._recording.start_session(session_name, self._config, mode)

        # Create pitch tracker
        self._pitch_tracker = PitchStateMachineV2(
            config=PitchConfig(...),
            on_pitch_start=self._on_pitch_start,
            on_pitch_end=self._on_pitch_end
        )

        return warning

    def _on_observation(self, event: ObservationDetectedEvent) -> None:
        """Feed observations to pitch tracker."""
        if self._pitch_tracker:
            self._pitch_tracker.add_observation(event.observation)
            self._pitch_tracker.update(event.timestamp_ns, ...)

    def _on_pitch_start(self, pitch_index: int, pitch_data: PitchData) -> None:
        """Pitch tracker callback - publish event."""
        event = PitchStartEvent(
            pitch_id=f"pitch_{pitch_index}",
            pitch_index=pitch_index,
            timestamp_ns=pitch_data.start_time_ns
        )
        self._event_bus.publish(event)

    def _on_pitch_end(self, pitch_data: PitchData) -> None:
        """Pitch tracker callback - publish event."""
        event = PitchEndEvent(
            pitch_id=pitch_data.pitch_id,
            observations=pitch_data.observations,
            timestamp_ns=pitch_data.end_time_ns
        )
        self._event_bus.publish(event)
```

**Testing**:
- Integration test: Service wiring works correctly
- Integration test: Pitch state machine coordinates services
- Integration test: Events flow through system correctly
- Integration test: Full capture → detect → record → analyze flow

**Success Criteria**:
- All services communicate via events
- Pitch detection lifecycle works end-to-end
- No deadlocks or race conditions

**Files Created**:
- `app/services/orchestrator/pipeline_orchestrator.py` (~200 LOC)
- `tests/integration/test_pipeline_orchestrator.py` (~150 LOC)

---

### Step 6: MainWindow Integration (4-6 hours)

**Priority**: FINAL (update UI to use new architecture)

**Modify**: `ui/main_window.py`

#### Changes Required

```python
# OLD
from app.pipeline_service import InProcessPipelineService
self._service = InProcessPipelineService(backend="uvc")

# NEW
from app.services.orchestrator.pipeline_orchestrator import PipelineOrchestrator
self._orchestrator = PipelineOrchestrator(backend="uvc")
```

**All existing method calls remain the same** - PipelineOrchestrator implements PipelineService interface.

**Testing**:
- Manual test: UI launches successfully
- Manual test: Camera preview works
- Manual test: Recording session works
- Manual test: Pitch detection works
- Manual test: Session summary displays

**Success Criteria**:
- UI works identically to before
- No regressions in functionality

**Files Modified**:
- `ui/main_window.py` (minimal changes)
- Any other UI files that directly import InProcessPipelineService

---

## Integration Testing Strategy

Since we're skipping unit tests and focusing on integration tests, here's the comprehensive test plan:

### Test Suite 1: EventBus Foundation (~2 hours)
**File**: `tests/integration/test_event_bus.py`

```python
def test_event_bus_publish_subscribe():
    """Test basic pub/sub functionality."""

def test_event_bus_multiple_subscribers():
    """Test multiple subscribers receive same event."""

def test_event_bus_thread_safety():
    """Test concurrent publishers and subscribers."""

def test_event_bus_error_handling():
    """Test handler errors don't crash bus."""
```

### Test Suite 2: Service Integration (~4 hours)
**File**: `tests/integration/test_service_integration.py`

```python
def test_capture_to_recording_flow():
    """Test frames flow from capture to recording without drops."""
    # Setup: Create EventBus, CaptureService, RecordingService
    # Start recording
    # Start capture (simulated camera with known frames)
    # Verify: All frames written to session video

def test_capture_to_detection_flow():
    """Test frames flow from capture to detection."""
    # Setup: Create EventBus, CaptureService, DetectionService
    # Start capture
    # Verify: Detections generated
    # Verify: Observations published

def test_parallel_recording_and_detection():
    """Test recording and detection both receive frames."""
    # Setup: All services
    # Start recording + detection
    # Generate 100 frames
    # Verify: All 100 frames in recording
    # Verify: ~100 detections (best effort)

def test_pitch_lifecycle():
    """Test full pitch detection and recording."""
    # Setup: All services + orchestrator
    # Start session
    # Simulate pitch (observations)
    # Verify: PitchStart event published
    # Verify: Pre-roll frames in pitch video
    # Verify: PitchEnd event published
    # Verify: Pitch analysis completed
```

### Test Suite 3: End-to-End Workflow (~4 hours)
**File**: `tests/integration/test_end_to_end.py`

```python
def test_full_session_workflow():
    """Test complete session from start to stop."""
    # Setup: PipelineOrchestrator with simulated cameras
    # 1. Start capture
    # 2. Start recording
    # 3. Simulate 3 pitches
    # 4. Stop recording
    # 5. Verify: Session summary correct
    # 6. Verify: 3 pitch videos created
    # 7. Verify: Session video complete

def test_disk_space_emergency_stop():
    """Test emergency stop on low disk space."""
    # Setup: Mock SessionRecorder with low disk space
    # Start recording
    # Trigger disk critical
    # Verify: Recording stops gracefully

def test_camera_reconnection():
    """Test camera reconnection during session."""
    # Setup: Simulated camera with disconnect/reconnect
    # Start capture
    # Simulate disconnect
    # Verify: Reconnection attempted
    # Verify: Recording continues after reconnect
```

**Total Integration Test Time**: ~10 hours

---

## Implementation Timeline

### Day 1: EventBus + Recording (12-16 hours)
- ✅ Morning: EventBus infrastructure (4-6 hours)
- ✅ Afternoon: RecordingService implementation (8-10 hours)
- 🧪 Evening: Integration tests for EventBus and Recording

### Day 2: Capture + Detection (10-13 hours)
- ✅ Morning: CaptureService implementation (4-5 hours)
- ✅ Afternoon: DetectionService implementation (6-8 hours)
- 🧪 Evening: Integration tests for Capture and Detection

### Day 3: Analysis + Orchestrator (10-13 hours)
- ✅ Morning: AnalysisService implementation (4-5 hours)
- ✅ Afternoon: PipelineOrchestrator implementation (6-8 hours)
- 🧪 Evening: Integration tests for full pipeline

### Day 4: MainWindow + End-to-End Testing (8-10 hours)
- ✅ Morning: Update MainWindow integration (4-6 hours)
- 🧪 Afternoon: End-to-end integration tests (4 hours)

### Day 5: Bug Fixes + Polish (8 hours)
- 🐛 Fix integration test failures
- 🐛 Address race conditions
- 🐛 Performance tuning
- 📝 Update documentation

**Total: 48-60 hours (5-6 days @ 10 hours/day)**

---

## Success Criteria

### ✅ Functional Requirements
- [ ] All frames captured to recording (no drops)
- [ ] Detection runs in parallel without blocking recording
- [ ] Pitch state machine coordinates services correctly
- [ ] PitchStart/PitchEnd events trigger correct actions
- [ ] Session summaries are accurate
- [ ] UI works identically to before refactoring

### ✅ Performance Requirements
- [ ] Frame capture: 30fps per camera (no regression)
- [ ] Recording: All frames written (no drops)
- [ ] Detection: Best-effort, can lag
- [ ] Event bus: < 1ms overhead per event

### ✅ Code Quality Requirements
- [ ] All services < 400 LOC each
- [ ] Event-driven architecture (no direct service calls)
- [ ] Integration test coverage for all workflows
- [ ] No thread safety issues (verified by testing)

### ✅ Documentation Requirements
- [ ] Architecture diagrams updated
- [ ] Service interfaces documented
- [ ] Event types documented
- [ ] Migration guide for future developers

---

## Risk Management

### High Risk: Frame Drops During Recording
**Mitigation**:
- RecordingService has priority event handling
- Test with high frame rates (60fps simulation)
- Profile event bus overhead

### Medium Risk: Event Bus Performance
**Mitigation**:
- Use thread-safe queues for async handling
- Profile event publishing overhead
- Test with high event rates

### Medium Risk: Pitch State Machine Coordination
**Mitigation**:
- Comprehensive integration tests
- Extensive logging of state transitions
- Validate pre-roll buffer behavior

### Low Risk: Service Communication Complexity
**Mitigation**:
- Clear event type definitions
- Typed event handlers
- Runtime event tracing for debugging

---

## Next Steps After Phase 1

Once Phase 1 is complete:

**Phase 2: Performance Optimization**
- Profile event bus overhead
- Optimize frame buffering
- Add async event handling

**Phase 3: Enhanced Features**
- Real-time config updates via events
- Cloud recording backend
- Multiple recording formats

**Phase 4: Plugin Architecture**
- Plugin interface for services
- Custom detector plugins
- Custom analysis plugins

---

## Appendix: File Structure

```
app/
├── events/
│   ├── __init__.py
│   ├── event_bus.py (EventBus class)
│   └── event_types.py (Event dataclasses)
├── services/
│   ├── __init__.py
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── interface.py (abstract)
│   │   └── implementation.py (concrete)
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── interface.py
│   │   └── implementation.py
│   ├── recording/
│   │   ├── __init__.py
│   │   ├── interface.py
│   │   └── implementation.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── interface.py
│   │   └── implementation.py
│   └── orchestrator/
│       ├── __init__.py
│       └── pipeline_orchestrator.py
├── pipeline_service.py (kept for compatibility, deprecated)
└── ...

tests/
└── integration/
    ├── test_event_bus.py
    ├── test_service_integration.py
    ├── test_recording_service.py
    ├── test_capture_service.py
    ├── test_detection_service.py
    ├── test_analysis_service.py
    ├── test_pipeline_orchestrator.py
    └── test_end_to_end.py
```

**Total New Files**: ~15 files
**Total New LOC**: ~2000 LOC (services + tests)
**Files Modified**: 1-2 (MainWindow, imports)

---

This revised plan reflects all user decisions and provides a clear path forward for the complete service extraction with event-driven architecture.
