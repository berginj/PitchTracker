# Oversized Module Triage

**Reviewed:** 2026-08-13
**Baseline:** 31 grandfathered Python files above the 500-line limit

The file-length gate prevents new oversized modules but intentionally
grandfathers inherited debt. A passing gate therefore means no new size debt;
it does not mean every module meets the current limit.

Priorities below combine runtime criticality, one-year commit count, current
line count, and ownership boundaries from `agents.md`. Tests should normally be
split with the source boundary they characterize rather than receiving
standalone extraction projects.

## Next extraction issues

| Priority | File | Lines | One-year changes | Owner | Recommended boundary |
|---|---|---:|---:|---|---|
| P1 | [`ui/coaching/coach_window.py`](https://github.com/berginj/PitchTracker/issues/24) | 1,067 | 34 | UIAgent | Window shell, session controller, mode composition, and pitch presentation |
| P1 | [`calib/quick_calibrate.py`](https://github.com/berginj/PitchTracker/issues/25) | 1,089 | 20 | CalibrationToolingAgent | Input loading, feature matching, geometry estimation, report persistence, and CLI |
| P1 | [`app/pipeline/detection/processor.py`](https://github.com/berginj/PitchTracker/issues/26) | 854 | 12 | DetectionAgent | Pair buffering, candidate association, triangulation decisions, and evidence publication |
| P1 | [`ui/review/review_window.py`](https://github.com/berginj/PitchTracker/issues/27) | 1,156 | 11 | UIAgent | Window shell, session loading, playback coordination, exports, and diagnostics |
| P1 | [`app/pipeline/camera_management.py`](https://github.com/berginj/PitchTracker/issues/28) | 724 | 14 | CaptureAgent | Backend construction, lifecycle/recovery, frame routing, and preview state |

Each P1 extraction requires a dedicated issue, characterization tests, stable
public imports, and removal of its allowlist entry.

## Planned after P1

| Priority | Files | Owner | Rationale |
|---|---|---|---|
| P2 | `app/services/detection/implementation.py`, `app/pipeline/detection/threading_pool.py` | DetectionAgent | High-concurrency runtime ownership; split only after processor boundaries stabilize |
| P2 | `app/services/recording/implementation.py`, `app/pipeline/recording/session_recorder.py`, `app/pipeline/recording/pitch_recorder.py` | RecordingAgent | Keep queue control, session artifacts, and pitch artifacts independently testable |
| P2 | `app/services/analysis/implementation.py` | AnalysisAgent | Separate worker lifecycle, pitch analysis, session aggregation, and refinement |
| P2 | `ui/dialogs/calibration_wizard_dialog.py`, `scripts/check_camera_alignment.py` | CalibrationToolingAgent / UIAgent | Keep tooling execution out of Qt while preserving the dialog facade |
| P2 | `app/review/review_service.py`, `app/review/session_loader.py`, `ui/review/comparison_view.py` | UIAgent | Split durable loading from comparison presentation after review-window extraction |
| P2 | `app/pipeline/pitch_tracking_v2.py` | PitchStateAgent | State transition and snapshot responsibilities need characterization before extraction |

## Lower-churn ownership cleanup

The following modules remain P3 unless change rate or defect history increases:

- `ui/themes/glass_theme.py`
- `ui/analytics/comparison_dashboard.py`
- `analysis/trend_analyzer.py`
- `tools/camera_capabilities_check.py`

Oversized test files are assigned to the corresponding source extraction:

- `tests/integration/test_pipeline_orchestrator.py`
- `tests/integration/test_recording_service.py`
- `tests/integration/test_analysis_service.py`
- `tests/app/pipeline/test_pitch_tracking_v2.py`
- `tests/test_rig_profile.py`
- `tests/test_setup_providers.py`
- `tests/test_system_stress.py`
- `tests/test_online_refinement.py`
- `tests/test_profile_manager.py`

## Governance

1. Do not add new allowlist entries without an owner, issue, and extraction
   boundary.
2. Planned work must reduce or preserve the current physical line count; an
   extraction cannot move unrelated logic into another oversized file.
3. Public facades remain stable until consumer searches and parity tests prove
   removal is safe.
4. Concurrent and hardware-facing modules require simulator coverage plus an
   explicit manual validation note.
5. Structural reviews report both the gate result and remaining grandfathered
   count.
