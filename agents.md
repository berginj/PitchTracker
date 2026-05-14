# PitchTracker Agent Specification

## Overview

### Purpose

PitchTracker uses agents as bounded, message-driven workers around the camera, detection, tracking, trajectory, recording, analysis, tooling, and UI workflows. The agent system exists to keep responsibilities explicit, make automation testable, and prevent future LLM or service integrations from bypassing safety-critical pipeline boundaries.

This document is the authoritative specification for agents in this repository. If code, prompts, or docs disagree with this file, update the implementation or update this file in the same change.

### Architecture

Agents are logical roles, not necessarily separate processes. In the current repo they map primarily to service boundaries:

| Agent | Primary Runtime Module | Responsibility |
|---|---|---|
| `PipelineOrchestratorAgent` | `app/services/orchestrator/pipeline_orchestrator.py` | Coordinate capture, detection, recording, and analysis events |
| `CaptureAgent` | `app/services/capture`, `capture/` | Acquire camera frames and publish frame events |
| `DetectionAgent` | `app/services/detection`, `app/pipeline/detection/processor.py` | Detect ball candidates, gate detections, produce stereo and ray observations |
| `PitchStateAgent` | `app/pipeline/pitch_tracking_v2.py` | Own pitch lifecycle state and pitch data snapshots |
| `TrajectoryAgent` | `trajectory/`, `app/pipeline/analysis/pitch_summary.py` | Fit trajectory modes and produce trajectory diagnostics |
| `RecordingAgent` | `app/services/recording`, `app/pipeline/recording/` | Persist session/pitch video, observations, manifests, and summaries |
| `AnalysisAgent` | `app/services/analysis`, `app/pipeline/analysis/` | Convert finalized pitch data into pitch and session summaries |
| `CalibrationToolingAgent` | `app/services/tooling`, `calib/` | Run calibration, environment validation, alignment, and training-report tooling |
| `UIAgent` | `ui/`, `app/qt_pipeline_service.py` | Present state, accept operator commands, and avoid owning pipeline logic |
| `MaintenanceAgent` | Repository-level LLM/developer workflow | Modify code, tests, docs, and configs under this specification |

### Message Flow

The preferred runtime flow is event-driven:

1. `CaptureAgent` publishes `FrameCapturedEvent`.
2. `DetectionAgent` consumes frames and publishes `ObservationDetectedEvent` and, when ray modes are enabled, `RayObservationDetectedEvent`.
3. `PipelineOrchestratorAgent` forwards observations to `PitchStateAgent`.
4. `PitchStateAgent` emits pitch start/end callbacks.
5. `RecordingAgent` records frames and observations during the pitch lifecycle.
6. `AnalysisAgent` analyzes `PitchEndEvent` and publishes `PitchAnalyzedEvent`.
7. `RecordingAgent` writes final manifests after analysis.
8. `UIAgent` observes summaries, metrics, warnings, and errors.

Agents communicate through typed dataclasses, service interfaces, or explicit callbacks. Agents must not reach into another agent's private state except in tests.

## Agent Definitions

### PipelineOrchestratorAgent

| Field | Specification |
|---|---|
| Mission | Coordinate service lifecycle and event flow. It owns wiring, not domain algorithms. |
| Inputs | App config, camera serials, recording commands, runtime config updates, observation events. |
| Outputs | Pitch start/end events, service calls, session state, public pipeline API responses. |
| Tools/APIs | `EventBus`, `CaptureServiceImpl`, `DetectionServiceImpl`, `RecordingServiceImpl`, `AnalysisServiceImpl`, `PitchStateMachineV2`. |
| Constraints | Must not perform camera I/O, detection, trajectory fitting, or file persistence directly. Must remain idempotent for start/stop where practical. |
| Escalation | Hand camera failures to `CaptureAgent`; detection faults to `DetectionAgent`; analysis failures to `AnalysisAgent`; manifest failures to `RecordingAgent`. |
| Example Message | `start_capture(config, left_serial="left", right_serial="right")` |

### CaptureAgent

| Field | Specification |
|---|---|
| Mission | Acquire frames from configured backends and provide consistent `Frame` contracts. |
| Inputs | Camera config, backend name, camera identifiers, start/stop commands. |
| Outputs | `FrameCapturedEvent`, camera stats, camera state changes. |
| Tools/APIs | UVC/OpenCV/simulated camera backends, `CameraManager`, `Frame`. |
| Constraints | Must not mutate image contents except configured rotation/format conversion. Must not block on detection, analysis, recording, or UI. |
| Escalation | Escalate missing/disconnected cameras, stalls, and unsupported modes to `PipelineOrchestratorAgent` through typed errors/events. |
| Example Message | `FrameCapturedEvent(camera_id="left", frame=frame, timestamp_ns=frame.t_capture_monotonic_ns)` |

### DetectionAgent

| Field | Specification |
|---|---|
| Mission | Convert camera frames into lane-gated 2D detections, stereo observations, and ray observations. |
| Inputs | `FrameCapturedEvent`, detector config, lane/plate ROIs, stereo calibration config. |
| Outputs | `Detection`, `StereoObservation`, `RayObservation`, latest gated detections, detection stats. |
| Tools/APIs | Classical/ML detectors, `DetectionThreadPool`, `DetectionProcessor`, `LaneGate`, `StereoMatcher`. |
| Constraints | Must not decide pitch lifecycle. Must preserve the stereo path when ray modes are enabled. Must limit candidates per frame according to config. |
| Escalation | Escalate model loading failures, invalid ROIs, calibration mismatch, and repeated detector exceptions to `PipelineOrchestratorAgent` and error bus. |
| Example Message | `RayObservationDetectedEvent(observation=ray, timestamp_ns=ray.t_ns, confidence=ray.confidence)` |

### PitchStateAgent

| Field | Specification |
|---|---|
| Mission | Own pitch lifecycle transitions and produce immutable pitch snapshots. |
| Inputs | Frame timestamps, lane counts, plate counts, stereo observations, ray observations, pre-roll frames. |
| Outputs | `PitchData`, pitch start callback, pitch end callback, phase/event log. |
| Tools/APIs | `PitchStateMachineV2`, `PitchConfig`, `PitchData`. |
| Constraints | Must be thread-safe. Must not analyze, record, or fit trajectory. Must reject too-short or under-observed pitches. |
| Escalation | Escalate callback exceptions via error bus and recover to a valid phase. |
| Example Message | `PitchData(pitch_index=1, phase=FINALIZED, observations=[...], ray_observations=[...])` |

### TrajectoryAgent

| Field | Specification |
|---|---|
| Mission | Fit the best configured trajectory result and record comparison diagnostics for non-primary modes. |
| Inputs | `TrajectoryFitRequest`, stereo observations, ray observations, camera models, radar speed, trajectory config. |
| Outputs | `TrajectoryFitResult`, plate crossing, confidence, residual diagnostics, failure codes. |
| Tools/APIs | `PhysicsDragFitter`, `RayReprojectionFitter`, `RayGraphFitter`, `TrajectoryFitterRegistry`, calibration NPZ loader. |
| Constraints | Default primary mode is `stereo_3d`. Ray modes require full stereo calibration. Ray failure must not erase stereo metrics when fallback is enabled. |
| Escalation | Return structured failure codes such as `CAMERA_MODEL_MISSING`, `INSUFFICIENT_RAYS`, or `OPT_DID_NOT_CONVERGE`; do not raise for expected fit failure. |
| Example Message | `TrajectoryFitRequest(mode="ray_graph", ray_observations=rays, camera_models=models, plate_plane_z_ft=0.0)` |

### AnalysisAgent

| Field | Specification |
|---|---|
| Mission | Convert finalized pitch data into coach-facing and durable summaries. |
| Inputs | `PitchEndEvent`, `PitchData`, app config, radar/manual speed, ball and strike-zone settings. |
| Outputs | `PitchSummary`, `SessionSummary`, `PitchAnalyzedEvent`, refinement inputs. |
| Tools/APIs | `PitchAnalyzer`, strike-zone metrics, trajectory registry, `OnlineCalibrationRefiner`. |
| Constraints | Must not write pitch manifests directly in the event-driven path. Must preserve summary compatibility when optional trajectory diagnostics are absent. |
| Escalation | Escalate corrupt pitch data, missing observations, and refinement errors through logs; avoid terminating the recording session for analysis-only failure. |
| Example Message | `PitchAnalyzedEvent(pitch_id="pitch_00001", summary=summary, session_summary=session_summary)` |

### RecordingAgent

| Field | Specification |
|---|---|
| Mission | Persist session and pitch artifacts without blocking capture longer than necessary. |
| Inputs | Frame events, pitch start/end events, stereo observations, pitch analysis events, config path, manual speed. |
| Outputs | Session videos, pitch videos, timestamp CSVs, observations JSON, pitch manifests, session manifest. |
| Tools/APIs | `SessionRecorder`, `PitchRecorder`, OpenCV video writers, manifest helpers. |
| Constraints | Must not fit trajectories or classify pitches. Must include schema/app metadata in durable artifacts. Must close writers cleanly on stop/pause/error. |
| Escalation | Escalate disk-full, codec, and file-write failures to error bus and `PipelineOrchestratorAgent`. |
| Example Message | `create_pitch_manifest(summary, config_path, performance_metrics)` |

### CalibrationToolingAgent

| Field | Specification |
|---|---|
| Mission | Run heavyweight setup, validation, calibration, alignment, and report-generation tasks outside the UI process. |
| Inputs | Tooling request contracts, image paths, calibration options, environment validation commands. |
| Outputs | Tooling result contracts, calibration files, validation diagnostics, training reports. |
| Tools/APIs | `SubprocessToolingService`, `app.services.tooling.worker_main`, `calib/`, `contracts.tooling`. |
| Constraints | Must isolate subprocess failures and map them to typed errors. Must not modify runtime config without explicit caller action. |
| Escalation | Escalate unknown tooling tasks, subprocess timeouts, invalid input paths, and calibration quality failures to the caller. |
| Example Message | `CalibrationRequest(left_image_path=..., right_image_path=..., output_dir=...)` |

### UIAgent

| Field | Specification |
|---|---|
| Mission | Provide operator controls and visualization while keeping business logic in services. |
| Inputs | User actions, service summaries, preview frames, error events, configuration changes. |
| Outputs | Pipeline API calls, dialogs, visual overlays, export requests. |
| Tools/APIs | `QtPipelineService`, `PipelineOrchestrator`, PySide6 widgets, export tooling. |
| Constraints | Must not own detection, trajectory, recording, or calibration algorithms. Must not access private service state except via compatibility shims already exposed. |
| Escalation | Escalate long-running work to service/tooling agents; surface user-actionable errors without hiding logs. |
| Example Message | `pipeline.start_recording(session_name="bullpen", mode="coaching")` |

### MaintenanceAgent

| Field | Specification |
|---|---|
| Mission | Help developers and future LLMs modify the repository safely, with tests and clear boundaries. |
| Inputs | Developer requests, source files, tests, configs, logs, issue/PR context. |
| Outputs | Code changes, tests, docs, analysis notes, review findings. |
| Tools/APIs | Shell, pytest, `rg`, `apply_patch`, GitHub connector when explicitly needed, repo scripts. |
| Constraints | Must preserve unrelated user changes. Must read existing code before editing. Must prefer focused patches and existing patterns. |
| Escalation | Ask for human decision when requirements conflict, destructive operations are requested, credentials are needed, or hardware-only validation is required. |
| Example Prompt | `Add a new trajectory comparison mode and update tests without changing default behavior.` |

## Interaction Protocols

### Message Schema

All inter-agent messages must have a typed payload and enough metadata to support debugging. Runtime events should use dataclasses when in-process and JSON-compatible dictionaries when persisted.

| Field | Required | Description |
|---|---:|---|
| `message_type` | Yes | Event, command, request, response, or error type. |
| `schema_version` | Required for durable data | Contract/schema version for persisted artifacts. |
| `correlation_id` | Yes for async flows | Stable ID linking frame, pitch, session, or tooling request. |
| `timestamp_ns` | Yes for runtime observations | Monotonic timestamp where applicable. |
| `session_id` | Yes once recording starts | Session identifier. |
| `pitch_id` | Yes for pitch-scoped messages | Pitch identifier. |
| `camera_id` | Yes for camera-scoped messages | Camera label or serial. |
| `payload` | Yes | Typed data contract. |
| `diagnostics` | Optional | Failure codes, timings, residuals, quality metrics. |

### Required Metadata

- Frames: `camera_id`, `frame_index`, `t_capture_monotonic_ns`, dimensions, pixel format.
- Detections: camera/frame identity, pixel center, radius, confidence.
- Stereo observations: paired pixels, 3D feet, quality, confidence.
- Ray observations: camera/frame identity, timestamp, pixel center, radius, confidence.
- Pitch summaries: pitch ID, start/end timestamps, sample count, strike result, trajectory mode, diagnostics.
- Manifests: schema version, app version, created UTC, config path, artifact filenames.

### Error Handling

- Expected domain failures must be represented as failure codes or typed exceptions.
- Agents must not swallow exceptions silently. Log the exception and return a degraded but valid state where possible.
- Long-running or hardware operations must expose timeout/failure paths.
- User-facing errors should be actionable; logs should preserve technical detail.
- A failed comparison trajectory mode must not fail the primary pitch analysis unless that mode is primary and fallback is disabled.

### State Rules

- Agents should prefer immutable input/output contracts.
- Runtime state must be owned by exactly one agent.
- Shared mutable state requires explicit locking or event handoff.
- Durable state belongs in manifests, summaries, config files, videos, CSVs, or exported JSON. Do not rely on in-memory state for replay.
- Maintenance agents must check `git status` before editing and must not revert unrelated changes.

### Assumption Validation

Before acting, agents must validate:

- Required config sections exist and pass schema validation.
- Camera, calibration, and ROI files exist before hardware-dependent actions.
- Units are explicit: pixels for image coordinates, feet for world coordinates, nanoseconds for monotonic timestamps.
- Requested trajectory mode is one of `stereo_3d`, `ray_reprojection`, or `ray_graph`.
- Tooling inputs are local, expected file types, and inside intended working paths when applicable.

## Security & Safety Requirements

### Forbidden Actions

- Do not delete recordings, calibration files, or configs unless the user explicitly requests it.
- Do not run destructive Git commands such as hard reset or checkout over user work without explicit approval.
- Do not transmit videos, frames, manifests, calibration files, athlete data, or logs to external services unless upload is explicitly enabled and authorized.
- Do not store API keys, credentials, or private tokens in repo files, manifests, logs, or screenshots.
- Do not bypass config validation or write malformed manifests.
- Do not operate cameras or recording in a hidden/background mode without clear operator intent.

### Required Checks Before Tool Use

- File writes: verify target path and preserve unrelated changes.
- Recursive file operations: verify resolved paths are inside the intended workspace or output directory.
- Calibration: verify input image pairs, board settings, output directory, and expected NPZ keys.
- Recording: check disk space and writer availability.
- Camera capture: verify backend, serials, mode support, and reconnection policy.
- Test/benchmark runs: prefer focused tests first; use longer timeouts for known slow integration tests.

### Privacy Rules

- Treat frames, videos, manifests, logs, athlete names, team data, and location profiles as private.
- Persist only the minimum data required by the recording/training mode.
- Redact secrets from logs and support bundles.
- Review exports must include only the selected session artifacts.

### Logging Expectations

- Log service lifecycle transitions at `INFO`.
- Log repeated frame-level details at `DEBUG`, not `INFO`.
- Log recoverable failures at `WARNING`.
- Log failed operations with exceptions at `ERROR`.
- Include pitch/session/camera identifiers in logs when available.
- Diagnostics should use structured fields where supported.

## Implementation Notes

### Instantiation

The current preferred runtime entry point is `PipelineOrchestrator`, wrapped by `QtPipelineService` for UI usage. Agents should be instantiated through services and constructors already present in `app/services/` rather than by importing concrete lower-level classes from UI code.

Legacy `InProcessPipelineService` remains a compatibility path. New work should prefer the service-based architecture unless explicitly maintaining legacy behavior.

### Testing

Each agent requires tests at the smallest useful boundary:

| Agent | Test Style |
|---|---|
| CaptureAgent | Sim backend tests, camera state tests, frame contract tests |
| DetectionAgent | Detector unit tests, ROI gating tests, stereo/ray observation tests |
| PitchStateAgent | State transition, pre-roll, ramp-up, concurrency tests |
| TrajectoryAgent | Synthetic stereo/ray tests, fallback tests, failure-code tests |
| AnalysisAgent | Pitch summary, session summary, event-bus integration tests |
| RecordingAgent | Manifest, video writer fallback, disk monitor, artifact tests |
| CalibrationToolingAgent | Subprocess command construction, timeout, error mapping tests |
| UIAgent | Import, smoke, controller, and workflow tests |
| MaintenanceAgent | Not runtime-tested; validate via changed-code tests and review checklist |

Use `python -m pytest` for full validation and focused paths for development. Some integration tests are slow because trajectory fitting uses scipy; use adequate timeouts and document slow paths when adding tests.

### Extending With New Agents

To add an agent:

1. Define its mission, ownership boundary, inputs, outputs, tools, constraints, escalation rules, and examples in this file.
2. Add or update typed contracts before wiring runtime behavior.
3. Add config schema entries if the agent is configurable.
4. Implement behind a service interface or narrow module boundary.
5. Add focused unit tests and one integration test that proves message flow.
6. Update manifests or schemas only when durable data changes.
7. Preserve backward compatibility or document the migration path.

New agents must have one primary owner for state. If an agent needs another agent's data, it should request it through a typed message, service interface, callback, or event.

## Maintenance Checklist

- Default trajectory mode remains `stereo_3d` unless a release decision changes it.
- Ray modes remain comparison-first until validated with field recordings.
- UI code must not absorb pipeline logic.
- Recording artifacts must remain replayable without in-memory state.
- Hardware-dependent changes need simulator tests plus an explicit manual validation note.
