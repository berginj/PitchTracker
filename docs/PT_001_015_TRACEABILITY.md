# PT-001–PT-015 implementation traceability

This document maps the field-robustness work to implementation and verification
evidence. Automated tests prove software behavior with simulated or synthetic
inputs. They do **not** prove physical camera accuracy; only a named
ground-truth dataset can produce a `VALIDATED` assessment.

| Task | Delivered behavior | Primary implementation | Automated evidence |
|---|---|---|---|
| PT-001 | Shared evidence, correction, quality, and uncertainty vocabulary | `contracts/quality.py` | `tests/test_quality_contracts.py` |
| PT-002 | Versioned error budgets with warn/reject gates, explicit units, invalid-value rejection, and unavailable zero-opportunity states | `app/monitoring/error_budget.py`; orchestrator runtime assessment | quality-contract, runtime-loss, and orchestrator integration tests |
| PT-003 | Pitch lifecycle advances once per processed stereo pair, including empty pairs | `StereoFrameProcessedEvent`; detection/orchestrator wiring | detection and pipeline-orchestrator integration tests |
| PT-004 | Active rig owns camera identity, calibrated mode/readback, controls, transforms, artifact hashes, revision, and trajectory approvals | `app/services/rig_profile_models.py`; `app/services/rig_profile.py` | rig-profile, camera-manager, and setup-doctor runtime tests |
| PT-005 | One canonical, evidence-gated ten-step setup workflow | `ui/setup/`; launcher routing | setup state-machine, provider, registry, and window tests |
| PT-006 | Burst-based capture qualification exposes drops, unmatched rate, FPS, cadence jitter, skew tails, and verified physical control readback | `calib/capture_qualification.py`; live setup context | capture-qualification, UVC-readback, camera-manager, and setup-provider tests |
| PT-007 | Measured camera-to-field transform is mandatory for physical measurement mode | `calib/field_transform.py`; field-alignment setup step; orchestrator transform | field-transform, field-alignment, and runtime profile tests |
| PT-008 | Corrections are bounded, preserve raw values, and create an audit record | `app/pipeline/corrections.py`; analysis summary/manifest ledger | evidence-pipeline primitive tests |
| PT-009 | Rolling rig drift uses hysteresis and recommends operator action without mutating calibration | `app/monitoring/rig_drift.py`; detection/orchestrator diagnostics | `tests/test_field_robustness_models.py` |
| PT-010 | Per-pitch active-interval pair/observation evidence, final verdict, corrections, and atomic content-addressed SHA-256 generations are integrity-checkable | `app/pipeline/recording/evidence_package.py`; pitch recorder | evidence primitive, failure durability, and recording integration tests |
| PT-011 | Timestamp-aware per-camera tracklets suppress isolated/inconsistent candidates; one-to-one stereo association is deterministic | `trajectory/tracklets.py`; detection service; `app/pipeline/utils.py` | field-robustness, detection, and pipeline utility tests |
| PT-012 | Speed carries its exact source; vision speed is derived only from a usable fit; legacy movement fields disclose their raw-displacement basis and cannot drive fatigue claims unless validated | `app/pipeline/analysis/pitch_summary.py`; `analysis/fatigue_detector.py`; durable quality diagnostics | analysis integration, fatigue evidence-gating, and manifest tests |
| PT-013 | Mode comparison cannot auto-promote; validation rejects ambiguous IDs; physical ray-primary use requires an exact durable rig/report approval | `trajectory/mode_validation.py`; `calib/ground_truth.py`; rig profiles | field-robustness and rig-profile approval tests |
| PT-014 | Coaching shows compact health/action state; detailed evidence is hidden until explicitly opened | `ui/coaching/diagnostics_view.py`; coaching window | field-robustness model and Qt service tests |
| PT-015 | Analysis and frame writing use bounded worker generations, reject stale submissions, expose drops/failures, and refuse unsafe close after a drain timeout | analysis/recording worker and service modules | worker, pause/resume, failure-durability, recording, and analysis integration tests |

## AR-001 through AR-015 follow-up

| Tasks | Delivered behavior | Primary implementation | Automated evidence |
|---|---|---|---|
| AR-001–AR-002 | Circular fixture evidence is diagnostic-only; refinement is proposal-only; operational and physical-claim eligibility are separate | `calib/field_fixture*.py`; `calib/online_refinement.py`; rig-profile services | field-fixture, online-refinement, rig-profile, and physical-validation tests |
| AR-003–AR-006 | Setup capture runs in a supervised disposable process with cancellation, hard deadline, stale-result rejection, and responsive Qt workflow | `contracts/setup_capture.py`; `app/services/capture/setup_capture.py`; `ui/setup/setup_capture_controller.py` | setup-process, setup-UI, provider, wizard, and capture integration tests |
| AR-007–AR-012 | Stable decision lineage, terminal frame conservation, unmatched outcomes, complete candidate/edge/triangulation evidence, deterministic global association, session journal, and replay reconciliation | detection processor/service; `stereo/global_assignment.py`; `app/pipeline/recording/evidence_journal.py`; `app/pipeline/replay/` | decision-evidence, detection, recording, orchestrator, and replay tests |
| AR-013–AR-015 | Physical-validation v2 contracts/tooling, immutable fingerprint-bound approvals, shadow/confirmation separation, and manual protocol | `contracts/physical_validation.py`; `calib/physical_validation.py`; rig-profile/tooling services; `docs/PHYSICAL_VALIDATION_PROTOCOL_V2.md` | physical-validation, rig-profile, tooling, analysis, and orchestrator tests |

## Validated setup snapshot follow-up

| Requirement | Delivered behavior | Primary implementation | Automated evidence |
|---|---|---|---|
| SSR-001 | Every persisted setup carries a canonical, content-addressed system inventory; physical claim eligibility fails closed when it is incomplete or altered | `docs/SETUP_SNAPSHOT_REQUIREMENTS.md`; `contracts/setup_snapshot.py`; `app/services/setup_snapshot.py`; rig-profile services | setup-snapshot, setup-provider, and rig-profile tests |
| SSR-002 | Camera selection preselects a connected previously validated pair first, otherwise the strongest recognized global-shutter pair for the requested mode, while retaining explicit operator override | setup providers, camera-selection view and step | setup-provider and camera-selection-step tests |

## Operational acceptance boundary

Before enabling validated onsite claims for a physical rig, run the canonical
setup with the actual global-shutter cameras and archive:

1. Requested/actual mode and backend control readback for both serial numbers.
2. Burst qualification with frame-drop, unmatched-frame, achieved-FPS, jitter,
   and pair-skew p50/p95/p99 values.
3. Calibration and field-fixture artifacts whose hashes match the active rig.
4. A named ground-truth dataset, environment description, software version,
   rejection denominator, and predeclared speed/plate thresholds.

If DirectShow cannot verify exposure units or the physical dataset misses a
threshold, the correct result is `DEGRADED`, `UNAVAILABLE`, or `REJECTED`—never
`VALIDATED` by inference.
