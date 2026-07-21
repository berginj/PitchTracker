# Stereo Setup Wizard (`ui/setup`)

Genuine, test-driven 10-step stereo-rig setup wizard. The core principle of the
v2.0.0 rebuild: **prove the product can receive, pair, compare, and calibrate
left/right camera images before any pitch-tracking logic matters.** Every step
is backed by real, synthetic-testable logic — there are no demo-only
placeholders left in the flow.

The durable inventory and validated-configuration gate are specified in
[`docs/SETUP_SNAPSHOT_REQUIREMENTS.md`](../../docs/SETUP_SNAPSHOT_REQUIREMENTS.md).

## The 10 canonical steps

The flow is defined once by `SetupStep` + `DEFAULT_SETUP_SPEC` in
`state_machine.py` and rendered by a widget registry:

| # | `SetupStep` | Widget | Proves |
|---|-------------|--------|--------|
| 1 | `SELECT_CAMERAS` | `CameraSelectStep` | Distinct left/right cameras discovered and assigned by hardware id |
| 2 | `PAIRED_PREVIEW` | `PairedPreviewStep` | Both streams deliver frames that pair within tolerance |
| 3 | `SYNC_CHECK` | `SyncCheckStep` | Left/right timestamps are aligned |
| 4 | `FOCUS_EXPOSURE_LOCK` | `FocusLockStep` | Manual fixed-focus sharpness + exposure/white-balance lock |
| 5 | `OVERLAP_VALIDATION` | `OverlapStep` | Sufficient field-of-view overlap via ORB feature matching |
| 6 | `COARSE_RECTIFY` | `RectifyStep` | Targetless coarse rectification reduces epipolar error |
| 7 | `CHARUCO_FINE_TUNE` *(optional)* | `CharucoFinetuneStep` | Optional ChArUco fine-tuning of intrinsics |
| 8 | `FIELD_ALIGNMENT` | `FieldAlignmentStep` | Camera coordinates are tied to a measured field fixture |
| 9 | `PERSIST_PROFILE` | `PersistProfileStep` | Evidence and artifacts are persisted in an active `RigProfile` |
| 10 | `QUALITY_REPORT` | `QualityReportStep` | Durable `CalibrationQualityReport` summary and blocking verdict |

ChArUco is positioned as **optional fine-tuning**, not the primary setup
dependency. The wizard finishes on a working targetless calibration if step 7 is
skipped.

## Architecture

```
ui/setup/
├── state_machine.py          # SetupStep enum + DEFAULT_SETUP_SPEC + SetupStateMachine (Qt-free)
├── stereo_steps.py           # build_stereo_step_widgets(): registry of all 10 step widgets
├── stereo_setup_window.py    # StereoSetupWindow: hosts the registry over the canonical spec
├── providers.py              # Real adapter providers + build_live_stereo_step_widgets()
├── <step>_view.py            # Qt-free view-models (grade + present) per step
└── steps/
    ├── base_step.py          # BaseStep: get_title/get_description/validate/on_enter
    └── <step>_step.py        # BaseStep widget per step (injectable provider)

setup_window.py + wizard_spec.py  # Legacy 7-step wizard, retained for compatibility
```

### View-model + widget pattern

Each step separates *logic* from *Qt* so it is unit-testable off-screen:

- A Qt-free **view-model** (`*_view.py`) defines a frozen snapshot dataclass, a
  pure `grade_*()` verdict function, and a `present_*()` formatter returning a
  `ReportView` (shared `ReportRow`/`ReportView` from `quality_report_view.py`).
- A **`BaseStep` widget** (`steps/*_step.py`) takes an injectable
  `*_provider` callable (defaulting to an honest empty/no-hardware provider),
  calls it in `on_enter()`, grades the result, and renders it.

This means the entire wizard is exercised in tests with synthetic snapshots and
the `SimulatedCamera` backend — no physical cameras required.

### Live providers

`providers.py` adapts real backends into the step snapshots:

- `discover_camera_selection()` — `list_uvc_devices()` + `CameraCatalogService`
  (carry-over side assignment by hardware id, model recognition, and explicit
  pair recommendation). It preselects the newest connected previously validated
  pair; otherwise it ranks recognized global-shutter cameras against the
  requested mode, synchronization, throughput, and control capabilities.
- `capture_paired_preview(left, right, ...)` — grabs a burst from any
  `CameraDevice` pair (real `UvcCamera` or `SimulatedCamera`); a `CameraError`
  marks a dead side honestly instead of raising.
- `simulated_paired_preview()` / `make_camera_preview_provider()` — convenience
  preview providers for demos/tests and live UVC capture respectively.
- `build_live_stereo_step_widgets(catalog=, list_devices=, preview_provider=)` —
  wires a shared camera context through discovery, assignment, paired capture,
  sync, focus/exposure, overlap, rectification, field alignment, persistence,
  and the final quality report. All dependencies are injectable so tests never
  touch hardware.

`StereoSetupWindow(widget_factory=...)` accepts the live builder; every launcher
setup route opens this canonical workflow. The old `SetupWindow` remains an
import-compatibility module and is not a launcher destination.

## BaseStep interface

```python
def get_title(self) -> str: ...
def get_description(self) -> str: ...
def validate(self) -> tuple[bool, str]:   # (is_valid, error_message)
def on_enter(self) -> None: ...
def on_exit(self) -> None: ...
def is_optional(self) -> bool: ...        # True only for CHARUCO_FINE_TUNE
```

`BaseStep` does not use `@abstractmethod` because Qt's `QWidget` metaclass
conflicts with `ABCMeta`; required methods `raise NotImplementedError` instead.

## Tests

| Area | Tests |
|------|-------|
| State machine | `tests/test_setup_state_machine.py` |
| Registry + full-flow integration | `tests/test_stereo_steps.py` |
| Per-step view-models + widgets | `tests/test_<step>_view.py`, `tests/test_<step>_step.py` |
| Window smoke | `tests/test_stereo_setup_window.py` |
| Adapter providers + launch wiring | `tests/test_setup_providers.py` |

Run off-screen with `$env:QT_QPA_PLATFORM="offscreen"`. The `*setup_window*`
smoke tests pass deterministically in isolation; they can be flaky under
`pytest -n auto` due to shared Qt state across xdist workers.

## Status

- ✅ All 10 steps are provider-driven, evidence-gated, synthetic-testable widgets.
- ✅ `StereoSetupWindow` + live provider registry wired into the launcher.
- ✅ Persisted profiles include a content-addressed system snapshot; incomplete
  evidence fails closed for physical accuracy claims.
- 🚧 Pending (hardware-bound, cannot run in CI): prove DirectShow control
  readback semantics and end-to-end accuracy on the physical global-shutter
  rig. The wizard intentionally will not claim a control lock or validated
  measurement until that evidence exists.
