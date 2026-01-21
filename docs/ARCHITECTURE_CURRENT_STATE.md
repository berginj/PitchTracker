# Current Architecture: InProcessPipelineService

**Last Updated**: 2026-01-21
**Version**: Pre-refactoring baseline documentation
**File**: `app/pipeline_service.py` (932 LOC)

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [State Variables](#state-variables)
4. [Public API (21 methods)](#public-api)
5. [Private Methods (10 methods)](#private-methods)
6. [Callback Chains](#callback-chains)
7. [Component Dependencies](#component-dependencies)
8. [Threading Model](#threading-model)
9. [Extraction Complexity](#extraction-complexity)

---

## Overview

`InProcessPipelineService` is the monolithic orchestrator for the entire PitchTracker pipeline. It manages:

- **Camera capture** (2 threads @ 30fps each)
- **Object detection** (2-N worker threads)
- **Stereo matching** (1 thread)
- **Pitch tracking** (state machine)
- **Session recording** (video + metadata)
- **Pitch analysis** (trajectory fitting)

**Total**: 56 methods, 30+ state variables, 6+ threads, 4 callback chains

---

## Architecture Diagram

### Current Monolithic Structure

```
┌────────────────────────────────────────────────────────────────────────┐
│                    InProcessPipelineService (932 LOC)                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CAPTURE LAYER                                                   │ │
│  │  - CameraManager (2 threads)                                     │ │
│  │  - Frame buffering                                               │ │
│  │  - Reconnection handling                                         │ │
│  └────────────────────────┬─────────────────────────────────────────┘ │
│                           │ _on_frame_captured                        │
│                           ↓                                            │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  DETECTION LAYER                                                 │ │
│  │  - DetectionThreadPool (2-N threads)                             │ │
│  │  - DetectionProcessor (stereo thread)                            │ │
│  │  - Lane/Plate gating                                             │ │
│  │  - SimpleStereoMatcher                                           │ │
│  └────────────────────────┬─────────────────────────────────────────┘ │
│                           │ _on_stereo_pair                           │
│                           ↓                                            │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  TRACKING LAYER                                                  │ │
│  │  - PitchStateMachineV2                                           │ │
│  │  - Pre-roll buffering                                            │ │
│  │  - Pitch start/end detection                                     │ │
│  └──────────────┬───────────────────────┬───────────────────────────┘ │
│                 │                       │                             │
│    _on_pitch_start                _on_pitch_end                       │
│                 ↓                       ↓                             │
│  ┌──────────────────────────┐  ┌───────────────────────────────────┐ │
│  │  RECORDING LAYER         │  │  ANALYSIS LAYER                   │ │
│  │  - SessionRecorder       │  │  - PitchAnalyzer                  │ │
│  │  - PitchRecorder         │  │  - SessionManager                 │ │
│  │  - Disk monitoring       │  │  - Strike zone calculation        │ │
│  └──────────────────────────┘  └───────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Target Service-Based Structure

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PipelineOrchestrator (150-200 LOC)                │
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │
│  │ Capture      │───→│ Detection    │───→│ Recording    │            │
│  │ Service      │    │ Service      │    │ Service      │            │
│  │ (200 LOC)    │    │ (350 LOC)    │    │ (280 LOC)    │            │
│  └──────────────┘    └──────────────┘    └──────┬───────┘            │
│                              │                    │                    │
│                              └────────────────────┘                    │
│                                     ↓                                  │
│                           ┌──────────────┐                             │
│                           │ Analysis     │                             │
│                           │ Service      │                             │
│                           │ (220 LOC)    │                             │
│                           └──────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## State Variables

### Camera/Capture (4 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `_backend` | str | Camera backend ("uvc", "opencv", "sim") |
| `_initializer` | PipelineInitializer | Config and initialization |
| `_camera_mgr` | CameraManager | Camera lifecycle manager |
| `_detect_queue_size` | int | Detection queue depth (default: 6) |

### Detection/Stereo (9 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `_detection_pool` | Optional[DetectionThreadPool] | Detection worker threads |
| `_detection_processor` | Optional[DetectionProcessor] | Stereo matching processor |
| `_detectors_by_camera` | Dict[str, object] | Per-camera detector instances |
| `_lane_gate` | Optional[LaneGate] | Lane ROI filter |
| `_plate_gate` | Optional[LaneGate] | Plate ROI filter |
| `_stereo_gate` | Optional[StereoLaneGate] | Stereo lane gate |
| `_plate_stereo_gate` | Optional[StereoLaneGate] | Stereo plate gate |
| `_lane_polygon` | Optional[list[tuple]] | Lane ROI polygon |
| `_stereo` | Optional[SimpleStereoMatcher] | Stereo triangulation |

### Recording (8 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `_recording` | bool | Session recording active flag |
| `_recorded_frames` | list[Frame] | Legacy frame buffer (unused in V2) |
| `_record_dir` | Optional[Path] | Base recording directory |
| `_record_session` | Optional[str] | Session name |
| `_record_mode` | Optional[str] | Recording mode identifier |
| `_session_recorder` | Optional[SessionRecorder] | Session video writer |
| `_pitch_recorder` | Optional[PitchRecorder] | Pitch video writer |
| `_record_lock` | threading.Lock | Recording state protection |

### Analysis (6 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `_pitch_analyzer` | Optional[PitchAnalyzer] | Trajectory fitting |
| `_session_manager` | Optional[SessionManager] | Session aggregation |
| `_pitch_tracker` | Optional[PitchStateMachineV2] | Pitch state machine |
| `_radar_client` | RadarGunClient | External radar gun |
| `_manual_speed_mph` | Optional[float] | Manual speed override |
| `_last_session_summary` | SessionSummary | Latest session summary |

### Configuration (4 variables)
| Variable | Type | Purpose |
|----------|------|---------|
| `_config` | Optional[AppConfig] | Application configuration |
| `_config_service` | Optional[ConfigService] | Config update service |
| `_config_path` | Optional[Path] | Config file path |
| `_session_active` | bool | Session active flag |

### Other (1 variable)
| Variable | Type | Purpose |
|----------|------|---------|
| `_pitch_id` | str | Current pitch identifier |

**Total: 32 state variables**

---

## Public API

### Camera Management (4 methods)

#### `start_capture(config: AppConfig, left_serial: str, right_serial: str, config_path: Optional[Path] = None) -> None`
**Purpose**: Initialize and start stereo camera capture pipeline
**Initializes**:
- Camera manager with config
- ROI gates (lane and plate)
- Detectors (classical or ML)
- Stereo matcher
- Detection processor
- Detection thread pool

**Throws**: CameraNotFoundError, CameraConnectionError, CameraConfigurationError, InvalidROIError, ModelLoadError, DetectionError

#### `stop_capture() -> None`
**Purpose**: Stop detection and camera threads
**Stops**: Detection pool → Camera manager
**Thread-Safe**: Best-effort cleanup

#### `get_preview_frames() -> Tuple[Frame, Frame]`
**Purpose**: Get latest frames for UI preview
**Returns**: (left_frame, right_frame)
**Throws**: CameraConnectionError

#### `get_stats() -> Dict[str, Dict[str, float]]`
**Purpose**: Get camera capture statistics
**Returns**: Dict with left/right FPS, latency, etc.

---

### Recording Management (5 methods)

#### `start_recording(pitch_id: Optional[str] = None, session_name: Optional[str] = None, mode: Optional[str] = None) -> str`
**Purpose**: Start session recording
**Initializes**:
- Session recorder (video writer)
- Pitch analyzer (trajectory fitting)
- Session manager (aggregation)
- Pitch tracker (state machine)

**Returns**: Disk space warning message
**Side Effects**: Exports calibration metadata

#### `stop_recording() -> RecordingBundle`
**Purpose**: Stop session and finalize
**Finalizes**:
- Forces pitch end if active
- Stops session recorder
- Writes session summary

**Returns**: RecordingBundle (mostly empty)

#### `set_record_directory(path: Optional[Path]) -> None`
**Purpose**: Set base recording directory
**Modifies**: `_record_dir`

#### `set_manual_speed_mph(speed_mph: Optional[float]) -> None`
**Purpose**: Override radar gun speed
**Modifies**: `_manual_speed_mph`

#### `get_session_dir() -> Optional[Path]`
**Purpose**: Get current session directory
**Returns**: Session directory path or None

---

### Detection Management (6 methods)

#### `set_detector_config(config: CvDetectorConfig, mode: Mode, detector_type: str = "classical", ...) -> None`
**Purpose**: Update detector configuration during session
**Rebuilds**: Detector instances for both cameras
**Supports**: Classical (CV) and ML detectors

#### `set_detection_threading(mode: str, worker_count: int) -> None`
**Purpose**: Change detection threading mode
**Modes**: "per_camera" (2 threads) or "worker_pool" (N threads)

#### `get_latest_detections() -> Dict[str, list[Detection]]`
**Purpose**: Get raw detections by camera
**Returns**: {camera_id: [Detection]}

#### `get_latest_gated_detections() -> Dict[str, Dict[str, list[Detection]]]`
**Purpose**: Get gated detections (lane and plate)
**Returns**: {camera_id: {gate_name: [Detection]}}

#### `get_plate_metrics() -> PlateMetricsStub`
**Purpose**: Get plate-gated metrics
**Returns**: PlateMetricsStub (run_in, rise_in, sample_count)

#### `get_strike_result() -> StrikeResult`
**Purpose**: Get latest strike determination
**Returns**: StrikeResult (is_strike, sample_count)

---

### Analysis Management (5 methods)

#### `get_session_summary() -> SessionSummary`
**Purpose**: Get current session summary
**Returns**: SessionSummary (pitches, strikes, heatmap)

#### `get_recent_pitch_paths() -> list[list[StereoObservation]]`
**Purpose**: Get observation paths for recent pitches
**Returns**: List of pitch paths

#### `set_ball_type(ball_type: str) -> None`
**Purpose**: Set ball type for strike detection
**Updates**: ConfigService

#### `set_batter_height_in(height_in: float) -> None`
**Purpose**: Set batter height for strike zone
**Updates**: ConfigService, PitchAnalyzer config

#### `set_strike_zone_ratios(top_ratio: float, bottom_ratio: float) -> None`
**Purpose**: Set strike zone boundaries
**Updates**: ConfigService, PitchAnalyzer config

---

### Calibration (1 method)

#### `run_calibration(profile_id: str) -> CalibrationProfile`
**Purpose**: Run calibration (stub)
**Returns**: CalibrationProfile metadata

---

## Private Methods

### Frame Capture Callbacks (2 methods)

#### `_on_camera_state_changed(camera_id: str, state) -> None`
**Called By**: CameraManager when connection state changes
**Thread**: Reconnection thread
**Purpose**: Log camera state transitions
**States**: RECONNECTING, CONNECTED, FAILED, DISCONNECTED

#### `_on_frame_captured(label: str, frame: Frame) -> None`
**Called By**: CameraManager capture threads (~30fps each)
**Thread**: Camera capture thread
**Purpose**: Route frame to:
1. Pitch tracker pre-roll buffer (always)
2. Session recorder (if recording)
3. Detection queue (always)

---

### Detection Callbacks (2 methods)

#### `_detect_frame(label: str, frame: Frame) -> list[Detection]`
**Called By**: DetectionThreadPool worker threads
**Thread**: Detection worker thread
**Purpose**: Perform detection on frame
**Error Handling**: Publishes errors to error bus

#### `_on_detection_result(label: str, frame: Frame, detections: list[Detection]) -> None`
**Called By**: DetectionThreadPool result handler
**Thread**: Stereo loop thread
**Purpose**:
1. Write frame with detections to pitch recorder (ML training)
2. Pass to detection processor for stereo matching

---

### Stereo/Pitch Callbacks (2 methods)

#### `_on_stereo_pair(left_frame, right_frame, left_detections, right_detections, observations, lane_count, plate_count) -> None`
**Called By**: DetectionProcessor after stereo matching
**Thread**: Stereo loop thread
**Purpose**:
1. Add observations to pitch tracker
2. Add observations to pitch recorder (ML training)
3. Update pitch tracker state (may trigger pitch start/end)

#### `_on_pitch_start(pitch_index: int, pitch_data: PitchData) -> None`
**Called By**: PitchStateMachineV2 on INACTIVE → ACTIVE transition
**Thread**: Stereo loop thread
**Purpose**:
1. Generate pitch ID
2. Create PitchRecorder
3. Write pre-roll frames to pitch video

#### `_on_pitch_end(pitch_data: PitchData) -> None`
**Called By**: PitchStateMachineV2 on ENDING → FINALIZED transition
**Thread**: Stereo loop thread
**Purpose**:
1. Analyze pitch (trajectory fitting)
2. Add to session manager
3. Write pitch manifest
4. Update session summary

---

### Recording Helpers (4 methods)

#### `_start_recording_io() -> str`
**Called By**: start_recording()
**Thread**: UI thread
**Purpose**: Initialize all recording components
**Creates**: SessionRecorder, PitchAnalyzer, SessionManager, PitchStateMachineV2
**Returns**: Disk space warning

#### `_stop_recording_io() -> None`
**Called By**: stop_recording()
**Thread**: UI thread
**Purpose**: Finalize and close all recorders
**Closes**: PitchRecorder (with post-roll), SessionRecorder
**Writes**: Final session summary

#### `_write_record_frame_single(label: str, frame: Frame) -> None`
**Called By**: _on_frame_captured() when recording
**Thread**: Camera capture thread
**Purpose**: Write frame to session and pitch recorders
**Checks**: Post-roll completion for pitch closure

#### `_write_session_summary() -> None`
**Called By**: _stop_recording_io()
**Thread**: UI thread
**Purpose**: Write final session summary JSON

#### `_on_disk_critical(free_gb: float, message: str) -> None`
**Called By**: SessionRecorder disk monitor
**Thread**: Disk monitor thread
**Purpose**: Emergency stop recording on disk full
**Action**: Auto-stops recording

---

## Callback Chains

### Chain 1: Frame Capture → Detection → Stereo → Pitch

```
Camera Hardware (30fps each)
    ↓
CameraManager._capture_loop() [Camera Thread]
    ↓
_on_frame_captured(label, frame)
    ├→ _pitch_tracker.buffer_frame(label, frame)  [PRE-ROLL]
    ├→ _write_record_frame_single(label, frame)   [SESSION RECORDING]
    └→ _detection_pool.enqueue_frame(label, frame) [DETECTION QUEUE]
        ↓
DetectionThreadPool [Detection Worker Threads]
    ↓
_detect_frame(label, frame) → list[Detection]
    ↓
_on_detection_result(label, frame, detections) [Stereo Loop Thread]
    ├→ _pitch_recorder.write_frame_with_detections() [ML TRAINING]
    └→ _detection_processor.process_detection_result()
        ├→ Buffer frames
        ├→ Match left/right by timestamp
        └→ Triangulate detections → observations
            ↓
_on_stereo_pair(..., observations, ...) [Stereo Loop Thread]
    ├→ _pitch_tracker.add_observation(obs)
    ├→ _pitch_recorder.add_observation(obs)  [ML TRAINING]
    └→ _pitch_tracker.update(frame_ns, lane_count, plate_count, obs_count)
        ├→ [State: INACTIVE → RAMP_UP → ACTIVE]
        │   ↓
        │   _on_pitch_start(pitch_index, pitch_data)
        │       ├→ Generate pitch ID
        │       ├→ Create PitchRecorder
        │       └→ Write pre-roll frames
        │
        └→ [State: ACTIVE → ENDING → FINALIZED]
            ↓
            _on_pitch_end(pitch_data)
                ├→ _pitch_analyzer.analyze_pitch()
                ├→ _session_manager.add_pitch(summary)
                ├→ _pitch_recorder.write_manifest()
                └→ Update _last_session_summary
```

**Key Observations**:
- Frames flow through 3-5 processing stages
- Multiple threads involved (camera → detection → stereo → callbacks)
- Pitch state machine drives recording lifecycle
- Pre-roll frames captured before pitch detection

---

### Chain 2: Configuration Updates → Services

```
UI Thread
    ↓
set_batter_height_in(height_in)
    ↓
_config_service.update_batter_height(height_in)
    ↓
_config = _config_service.get_config()
    ↓
_pitch_analyzer.update_config(_config)
```

**Key Observations**:
- Config updates are synchronous
- PitchAnalyzer needs config for strike zone
- No notification to DetectionProcessor (caches outdated strike zone)

---

### Chain 3: Disk Critical → Emergency Stop

```
Disk Monitor Thread
    ↓
SessionRecorder._monitor_disk_space()
    ↓
[Disk space < 1GB threshold]
    ↓
_on_disk_critical(free_gb, message)
    ↓
stop_recording() [Emergency stop]
```

**Key Observations**:
- Independent thread monitors disk space
- Automatic emergency shutdown
- Error bus notifies UI

---

## Component Dependencies

### External Components

```
InProcessPipelineService
    ├── CameraManager (camera lifecycle)
    │   ├── CameraDevice (abstract)
    │   ├── UvcCamera (backend)
    │   ├── OpenCVCamera (backend)
    │   └── SimulatedCamera (testing)
    │
    ├── DetectionThreadPool (threading)
    │   ├── Per-camera mode (2 threads)
    │   └── Worker pool mode (N threads)
    │
    ├── DetectionProcessor (stereo matching)
    │   ├── SimpleStereoMatcher (triangulation)
    │   ├── LaneGate (ROI filtering)
    │   ├── StereoLaneGate (stereo ROI)
    │   └── SimpleTracker (observation tracking)
    │
    ├── SessionRecorder (video writing)
    │   ├── Video writers (cv2.VideoWriter)
    │   ├── Disk monitor thread
    │   └── Manifest generation
    │
    ├── PitchRecorder (pitch-specific)
    │   ├── Video writers (pre/post-roll)
    │   ├── Observation buffering
    │   └── Manifest generation
    │
    ├── PitchAnalyzer (trajectory)
    │   ├── PhysicsDragFitter (physics model)
    │   ├── Strike zone calculation
    │   └── Metrics computation
    │
    ├── SessionManager (aggregation)
    │   ├── Pitch summaries
    │   ├── Heatmap generation
    │   └── Session statistics
    │
    ├── PitchStateMachineV2 (state machine)
    │   ├── Pre-roll frame buffer
    │   ├── State transitions
    │   └── Timing validation
    │
    ├── PipelineInitializer (factory)
    │   ├── Detector creation
    │   ├── Stereo matcher creation
    │   └── ROI loading
    │
    ├── ConfigService (runtime config)
    │   ├── Config updates
    │   └── Validation
    │
    └── RadarGunClient (external speed)
        ├── TCP connection
        └── Speed queries
```

### Callback Registration

```
_camera_mgr.set_frame_callback(_on_frame_captured)
_camera_mgr.set_camera_state_callback(_on_camera_state_changed)
_detection_pool.set_detect_callback(_detect_frame)
_detection_pool.set_stereo_callback(_on_detection_result)
_detection_processor.set_stereo_pair_callback(_on_stereo_pair)
_session_recorder.set_disk_error_callback(_on_disk_critical)
_pitch_tracker.on_pitch_start = _on_pitch_start
_pitch_tracker.on_pitch_end = _on_pitch_end
```

---

## Threading Model

### Thread Inventory

| Thread Name | Count | Owner | Frequency | Purpose |
|-------------|-------|-------|-----------|---------|
| Camera Left | 1 | CameraManager | 30fps | Capture frames from left camera |
| Camera Right | 1 | CameraManager | 30fps | Capture frames from right camera |
| Detection Worker | 2-N | DetectionThreadPool | On-demand | Perform object detection |
| Stereo Loop | 1 | DetectionThreadPool | Continuous | Stereo matching and observation generation |
| Disk Monitor | 1 | SessionRecorder | 1/sec | Monitor disk space during recording |
| Reconnection | 1 | CameraReconnectionManager | On-demand | Attempt camera reconnection |
| **Total** | **6-N** | | | |

### Thread Communication

```
[Camera Thread] → Queue → [Detection Worker Thread]
[Detection Worker Thread] → Result Queue → [Stereo Loop Thread]
[Stereo Loop Thread] → Callback → [Pipeline Service] (same thread)
[Disk Monitor Thread] → Callback → [Pipeline Service] (disk thread)
[UI Thread] → Direct Call → [Pipeline Service]
```

### Thread Safety Analysis

**Locks Used**:
- `_record_lock` (threading.Lock): Protects recording state
- `_detection_processor._detect_lock`: Protects detection state
- `_pitch_tracker._lock` (RLock): Protects pitch state machine

**Potential Races**:
1. **`_pitch_recorder` creation/use**: Created in stereo thread, used in camera threads
   - Mitigated by sequential lifecycle (only one active pitch)
2. **`_recording` flag**: Set in UI thread, read in camera threads
   - Mitigation: Non-critical flag, worst case is one dropped frame
3. **Config updates**: UI thread updates, stereo thread reads
   - Mitigation: Immutable config objects (no race, but stale reads possible)

---

## Extraction Complexity

### Service Complexity Ranking

| Service | LOC | Complexity | Reason |
|---------|-----|------------|--------|
| **Capture** | ~200 | ⭐ EASY | Clean interface, self-contained |
| **Analysis** | ~220 | ⭐⭐ MEDIUM | Config propagation is tricky |
| **Detection** | ~350 | ⭐⭐⭐ MEDIUM | Complex threading, multiple gates |
| **Recording** | ~280 | ⭐⭐⭐⭐ HARD | Pitch state machine, pre-roll buffering |

### Extraction Order (Recommended)

```
1. Capture Service  ──────┐
                          ↓
2. Detection Service ─────┤
                          ↓
3. Analysis Service ──────┤
                          ↓
4. Recording Service ─────┤
                          ↓
5. Pipeline Orchestrator ─┘
```

**Rationale**:
- Capture is foundation (all others depend on frames)
- Detection processes frames from Capture
- Analysis can work independently on detection results
- Recording consumes output from all services
- Orchestrator ties everything together

### Critical Extraction Challenges

#### 1. Pre-Roll Frame Buffering
**Problem**: Frames buffered in PitchStateMachineV2 before pitch detection
**Current**: Pitch tracker holds 60 frames × 2 cameras = ~8MB buffer
**Challenge**: Buffer lives in Recording service, but frames come from Capture
**Solution**: Recording service subscribes to Capture frame events

#### 2. Configuration Propagation
**Problem**: Config updates affect multiple services
**Current**: ConfigService updates → direct calls to PitchAnalyzer
**Challenge**: Detection service also needs config for strike zone
**Solution**: Config service publishes updates, services subscribe

#### 3. Pitch State Machine Callbacks
**Problem**: Pitch tracker callbacks create/destroy PitchRecorder
**Current**: _on_pitch_start creates recorder, _on_pitch_end closes it
**Challenge**: Lifecycle management across service boundaries
**Solution**: Recording service owns pitch tracker and manages lifecycle

#### 4. Detection Result Routing
**Problem**: Detection results go to multiple consumers
**Current**: _on_detection_result writes to recorder AND processor
**Challenge**: Multiple destinations from single callback
**Solution**: Detection service publishes observation events, services subscribe

---

## Summary

### Strengths
- Clear layered architecture (capture → detect → track → record → analyze)
- Well-defined component boundaries (CameraManager, DetectionProcessor, etc.)
- Comprehensive error handling with error bus
- Robust state machine for pitch detection

### Weaknesses
- Monolithic service (932 LOC) with 56 methods
- Multiple responsibilities (SRP violation)
- Callback hell (4 nested callback chains)
- Tight coupling between layers
- Hard to test in isolation
- Config updates scattered

### Refactoring Benefits
- **Testability**: Each service can be unit tested
- **Reusability**: Detection can run on recorded sessions
- **Maintainability**: Clear boundaries, single responsibility
- **Flexibility**: Easy to swap implementations
- **Performance**: Can profile/optimize individual services

### Estimated Refactoring Effort
- **Capture Service**: 4-5 hours
- **Detection Service**: 6-8 hours
- **Analysis Service**: 4-5 hours
- **Recording Service**: 6-8 hours
- **Orchestrator**: 5-6 hours
- **Testing**: 8-10 hours
- **Migration**: 2-3 hours

**Total**: 35-45 hours (5-6 days)

---

**Next Steps**: Proceed to Phase 1 implementation with Capture Service extraction.
