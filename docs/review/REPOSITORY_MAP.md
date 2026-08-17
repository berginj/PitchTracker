# Repository Map

## Audit environment

- Windows 11 Home Insider Preview build 29639, ARM64; Snapdragon X X1E80100,
  12 logical processors; America/New_York.
- Python 3.13.14 AMD64 running on the ARM64 host; this is an emulated and
  non-representative platform combination.
- NumPy 2.2.2 on Python 3.13 and 2.3.5 on Python 3.14+, SciPy 1.17.0,
  OpenCV-contrib-python 4.10.0.84, PySide6 6.10.1,
  pytest 7.4.3, pytest-qt 4.5.0, xdist 3.6.1, timeout 2.3.1, Flake8 6.1.0,
  psutil 7.2.1, scikit-learn 1.8.0, Loguru 0.7.2, jsonschema 4.20.0,
  PyYAML 6.0.1, and PyInstaller 6.18.0.
- OpenCV x64 build: FFmpeg, DirectShow, and MSMF enabled; GStreamer and CUDA
  absent. Writer behavior depends on whether Qt offscreen mode is active.
- Default config identity: 1280×720 at 60 requested fps, classical detector,
  `greedy_v1` stereo association, `stereo_3d` trajectory, uploads disabled.
- Latest HEAD Actions evidence: run `29923290687` succeeded for Python 3.11,
  Python 3.12, and security. No open pull requests were present on the audit date.

## Runtime and ownership

| Area | Primary paths | Runtime owner / role | State |
|---|---|---|---|
| Entry points | `run_pitch_tracker.py`, `ui/launcher.py`, `ui/main_window.py` | UI shell | Active |
| Orchestration | `app/services/orchestrator/`, `app/qt_pipeline_service.py` | Pipeline orchestrator | Preferred |
| Capture | `app/services/capture/`, `capture/` | Camera acquisition, simulated/OpenCV/UVC backends | Active; hardware not verified |
| Detection | `app/services/detection/`, `app/pipeline/detection/`, `detect/` | Classical/ML candidates, gating, pairing, triangulation | Active |
| Pitch lifecycle | `app/pipeline/pitch_tracking_v2.py` | Single pitch-state owner | Active |
| Trajectory | `trajectory/`, `app/pipeline/analysis/` | Stereo, ray reprojection, ray graph fitting | Active; ray comparison-first |
| Recording | `app/services/recording/`, `app/pipeline/recording/` | Videos, timestamps, evidence, manifests | Active; codec portability risk |
| Analysis | `app/services/analysis/`, `app/pipeline/analysis/` | Pitch/session summaries | Active |
| Setup/tooling | `app/services/tooling/`, `calib/`, `ui/setup/` | Subprocess calibration and ten-step setup | Active; worktree delta |
| Review/export | `ui/review/`, `export/`, `ml/` | Replay, annotation, selected export, ML data export | Active/local |
| Contracts/config | `contracts/`, `configs/`, `schemas/` | Typed and durable boundaries | Active |
| Integrations | `app/integrations/`, upload/update/radar paths | Cloud, Bluetooth, radar, updater | Staged, disabled, stubbed, or externally dependent |
| Packaging/CI | installer scripts/specs, `.github/workflows/` | Windows packaging and required checks | Build automation exists; clean install unverified |
| Tests/benchmarks | `tests/`, `benchmarks/`, `scripts/` | Automated confidence and developer gates | Broad tests; benchmark semantics defective |
| Documentation | `README.md`, `docs/`, `agents.md`, `.github/copilot-instructions.md` | Product/developer/agent guidance | Active plus marked history/archive |

## Material workflow traces

1. Setup: launcher → `StereoSetupWindow` → ten step providers/widgets → setup capture subprocess → camera/calibration/ROI quality results → rig-profile persistence. HEAD has no outer scroll wrapper; the worktree adds one but still computes a 1,998-pixel minimum width.
2. Coaching: `CoachWindow` → `QtPipelineService` → `PipelineOrchestrator` → capture events → detection pool → stereo/ray observations → pitch state → recording and analysis → summaries/UI. Construction currently fails before this flow begins because game widgets call a missing style API.
3. Review: session manifest/artifacts → `ReviewWindow` → replay/timeline/annotation → selected export or ML export. Durable data supports replay, but not all runtime metadata required by `agents.md` is present.
4. Calibration/tooling: typed request → `SubprocessToolingService` → `worker_main` → calibration/validation script → typed result. `PipelineOrchestrator.run_calibration` itself remains intentionally unimplemented.
5. Updating/installing: launcher/update configuration → release/update checks and installer scripts. Source paths exist; issue #11 correctly requires a clean-machine smoke test.
6. Optional integrations: TAG/cloud and Bluetooth are feature-gated and skipped in tests; radar is a stub/manual-input boundary. They are not part of the proven default workflow.

## Duplication and legacy classification

| Component | Classification | Evidence |
|---|---|---|
| `PipelineOrchestrator` + service implementations | Preferred current path | Used by `QtPipelineService` and current architecture guidance |
| `InProcessPipelineService` | Compatibility/legacy, not dead | Explicitly retained and exercised by compatibility tests |
| Global assignment | Implemented optional capability | Registry/config/tests exist; default remains `greedy_v1` |
| Ray fitters | Implemented comparison capability | Registry/tests/config exist; default primary remains `stereo_3d` |
| `ConfigUpdateEvent` | Reserved/unused | Event type says it is unused while configuration remains static |
| TAG cloud/Bluetooth | Staged, not complete | Disabled defaults and opt-in skipped tests |
| Archived/historical docs | Historical | They must not be treated as current product status |

## RM-001 — Oversized ownership map

- **Finding:** The repository passes its gate by grandfathering 34 Python files over 500 lines, including core orchestrator, detection, recording, setup, review, theme, and calibration owners.
- **Evidence:** `scripts/check_file_length.py` reports pass with 34 grandfathered files; `ui/setup/providers.py` is 1,172 lines in the worktree and several runtime owners exceed 800 lines.
- **Impact:** High coupling and review surface undermine the otherwise clear agent ownership model.
- **Confidence:** High.
- **Recommendation:** Keep #14 and #15 first, then budget extractions by change frequency and ownership overlap.
- **Dependencies:** Green characterization tests and explicit public interfaces.
- **Effort:** Large, incremental.
- **Definition of Done:** Every grandfathered entry has an owner, target boundary, issue, and removal condition; no new entry is added; the count decreases each milestone.
