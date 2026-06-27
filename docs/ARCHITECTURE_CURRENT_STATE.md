# Current Architecture: Service-Oriented Event Pipeline

**Last Updated:** 2026-06-26
**Applies To:** v2.0.0-stereo
**Primary Entry Point:** `app.services.orchestrator.PipelineOrchestrator`

---

## Summary

PitchTracker now uses a service-oriented runtime coordinated by
`PipelineOrchestrator` and an in-process `EventBus`. The older
`InProcessPipelineService` still exists as a compatibility path, but it is not
the preferred architecture for new work.

The current architecture matches the agent boundaries in `agents.md`:

| Runtime Role | Current Implementation | Owns |
| --- | --- | --- |
| Pipeline orchestration | `app/services/orchestrator/pipeline_orchestrator.py` | Service wiring, lifecycle, pitch event publishing |
| Capture | `app/services/capture/implementation.py` | Camera lifecycle, frames, preview stats |
| Detection | `app/services/detection/implementation.py` | Detector setup, ROI gates, stereo/ray observations |
| Pitch state | `app/pipeline/pitch_tracking_v2.py` | Pitch lifecycle and finalized pitch snapshots |
| Recording | `app/services/recording/implementation.py` | Session/pitch videos, observations, manifests |
| Analysis | `app/services/analysis/implementation.py` | Pitch summaries, session summaries, trajectory analysis |
| Qt adapter | `app/qt_pipeline_service.py` | Qt-safe signal bridge around `PipelineOrchestrator` |
| Legacy compatibility | `app/pipeline_service.py` | Existing in-process API compatibility only |

---

## Runtime Flow

The preferred flow is event-driven:

```text
CaptureService
  publishes FrameCapturedEvent
        |
        v
DetectionService  <--- also receives frames for detection
  publishes ObservationDetectedEvent / RayObservationDetectedEvent
        |
        v
PipelineOrchestrator
  feeds PitchStateMachineV2
  publishes PitchStartEvent / PitchEndEvent
        |
        +--> RecordingService
        |
        +--> AnalysisService
                publishes PitchAnalyzedEvent
                        |
                        v
                RecordingService / UI observers
```

The Qt UI should reach pipeline behavior through `QtPipelineService` or
`PipelineOrchestrator`. UI code should not import lower-level capture,
detection, recording, or analysis implementation details unless it is working
on a dedicated tool surface with a documented boundary.

---

## Service Responsibilities

### `PipelineOrchestrator`

`PipelineOrchestrator` owns runtime coordination:

- loads and validates the active rig profile
- applies calibration and ROI paths to runtime config
- creates capture, detection, recording, and analysis services
- subscribes to observation events
- feeds observations into `PitchStateMachineV2`
- publishes pitch lifecycle events
- exposes the public `PipelineService` API used by the UI and tests

It must not own camera I/O, detection algorithms, recording persistence, or
trajectory fitting.

### `CaptureServiceImpl`

Capture owns camera access and frame publication. It is responsible for camera
startup/shutdown, preview frames, stats, and reconnection behavior for physical
backends.

### `DetectionServiceImpl`

Detection owns detector configuration, frame processing, ROI gating, stereo
matching, and optional ray observation publication. It must preserve stereo
observations even when ray modes are enabled.

### `PitchStateMachineV2`

Pitch state owns pitch lifecycle transitions, pre-roll/ramp-up handling, phase
tracking, and finalized `PitchData`. It does not analyze or persist pitch data.

### `RecordingServiceImpl`

Recording owns session and pitch artifact persistence. It subscribes to frame,
observation, pitch lifecycle, and analysis events and writes durable videos,
CSV/JSON metadata, manifests, and summaries.

### `AnalysisServiceImpl`

Analysis owns conversion from finalized pitch data into pitch and session
summaries. Trajectory fitting and diagnostics happen behind this boundary.

### `QtPipelineService`

`QtPipelineService` wraps `PipelineOrchestrator` and converts EventBus events
into Qt signals. It exists to keep worker-thread events out of Qt widgets.

---

## State Ownership

State should remain owned by exactly one service:

| State | Owner |
| --- | --- |
| Camera handles and latest preview frames | Capture service |
| Detector instances, gates, latest detections | Detection service |
| Pitch phase and pitch snapshots | `PitchStateMachineV2` |
| Active session/pitch recorders and artifact paths | Recording service |
| Current pitch/session summaries | Analysis service |
| Runtime service wiring and public API flags | `PipelineOrchestrator` |

Shared mutable state should move by event, typed contract, callback, or service
interface. Tests may inspect internals where useful, but production code should
not reach through another service's private fields.

---

## Stereo Setup Wizard (v2.0.0)

Setup/calibration runs outside the runtime orchestrator in a dedicated, tested
wizard under `ui/setup/` (see `ui/setup/README.md` for full detail):

- `state_machine.py` defines the canonical 9-step flow (`SetupStep` +
  `DEFAULT_SETUP_SPEC`) on a Qt-free `SetupStateMachine`.
- `stereo_steps.py` builds a registry of nine genuine, provider-driven step
  widgets; `stereo_setup_window.py` hosts them; `providers.py` supplies live
  UVC-discovery and camera-backed preview adapters via
  `build_live_stereo_step_widgets()`.
- Each step keeps verdict logic in a Qt-free view-model with an injectable
  provider, so the whole flow is testable with synthetic snapshots and the
  `SimulatedCamera` backend.

This keeps calibration/setup in setup/tooling paths; the runtime orchestrator
only starts from a validated rig profile (see Current Known Gaps #1).

---

## Current Known Gaps

These are the main architecture issues to resolve before the service-based path
can be considered fully complete:

1. `PipelineOrchestrator.run_calibration()` is intentionally not implemented.
   Calibration remains in Setup Doctor/tooling and the stereo setup wizard so
   the runtime orchestrator only starts from a validated rig profile. The
   method rejects calls with an actionable message pointing to those paths.
2. Event dataclasses do not yet carry the full message metadata described in
   `agents.md` (`correlation_id`, `session_id`, durable `schema_version`, and
   diagnostics fields where applicable). Runtime events are typed, but metadata
   completeness still needs an audit.
3. `InProcessPipelineService` remains in the repo. Treat it as compatibility
   code unless a maintenance task explicitly targets legacy behavior.
4. Some historical architecture and status reports remain in `archive/`; those
   files are retained for context and should not be read as current guidance.

---

## Testing Entry Points

Focused architecture validation:

```powershell
python -m pytest tests/integration/test_pipeline_orchestrator.py
python -m pytest tests/integration/test_qt_pipeline_service.py
python -m pytest tests/integration/test_event_bus.py
python -m pytest tests/test_interfaces.py
```

Full validation:

```powershell
python -m pytest
```

Some integration and trajectory tests are slower because they exercise
threading, recording, and scipy-backed trajectory logic.

---

## Maintenance Rules

- Prefer `PipelineOrchestrator` for new runtime integration work.
- Keep UI logic behind `QtPipelineService` or narrow controller APIs.
- Add or update typed contracts before changing durable data.
- Do not let comparison trajectory failures erase primary stereo metrics.
- Update this file and `agents.md` together when service boundaries change.
