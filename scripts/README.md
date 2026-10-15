# Utility Scripts

This directory contains standalone utility and validation scripts for PitchTracker development and testing.

## Validation Scripts

### UX evidence tools

`capture_ux_baseline.py` renders real UI widgets with synthetic inputs, isolated
configuration and display-only pipeline state. It never starts capture, reads
private recordings or loads the local roster. Output is a gallery and geometry
manifest under `docs/review/ux/baseline/`.

`capture_workspace.py` renders the implemented workspace at three viewport sizes
with synthetic Idle/Recording state on all four destinations. It opens guided
setup only through an explicit fixture action in disposable local state. Its
27 captures and geometry manifest live under `docs/review/ux/ux02/`; see the
[UX-02 implementation record](../docs/review/ux/UX_02_IMPLEMENTATION.md).

`capture_session_states.py` captures confirmed session states, pending commands
and recovery actions in the implemented shell, using synthetic snapshots only.
The 60 actual-widget captures live under `docs/review/ux/ux03/`; see the
[UX-03 implementation record](../docs/review/ux/UX_03_IMPLEMENTATION.md).

`capture_live_experience.py` renders Latest Pitch, Session Trends and Games in
six synthetic states and three viewport sizes. Its 54 captures and geometry
manifest are under `docs/review/ux/ux04/`; see the
[UX-04 implementation record](../docs/review/ux/UX_04_IMPLEMENTATION.md).

`capture_session_review.py` renders Sessions with disposable recorded-artifact
fixtures and an in-memory decoder. The 24 captures include missing-video,
invalid-mapping and active-capture browsing states. See the
[UX-05 implementation record](../docs/review/ux/UX_05_IMPLEMENTATION.md).

`capture_setup_players.py` renders Players, filtered history and guided Setup
with disposable configuration, roster and synthetic recorded artifacts. Its 30
captures include pending pitch changes, capture conflicts and saved re-entry.
See the [UX-06 implementation record](../docs/review/ux/UX_06_IMPLEMENTATION.md).

`render_ux_prototype.py` checks the local HTML workspace design with Qt WebEngine
and creates target images through Chromium PDF output and Qt PDF rasterization.
Its profile is in memory; it loads only the local prototype. The browser child
may require execution outside a restricted filesystem sandbox. Qt WebEngine and
Qt PDF are optional evidence-tool dependencies, not a new application frontend.

Run from the repository root using the supported Python environment:

```powershell
python scripts/capture_ux_baseline.py
python scripts/capture_workspace.py
python scripts/capture_session_states.py
python scripts/capture_live_experience.py
python scripts/capture_session_review.py
python scripts/capture_setup_players.py
python scripts/render_ux_prototype.py
```

See the [UX-01 specification](../docs/review/ux/UX_01_SPEC.md) for fixture limits,
source identity and remaining physical-display/hardware checks. Target images
describe a future PySide6 workspace; they do not prove its implementation.

### `check_public_docs.py`
Check the public documentation entry points before opening a pull request.
The check verifies required local Markdown links, prevents obsolete PyQt6 and
Python-version wording in the README, and checks that each dated public page has
a valid review date that is not in the future. Review dates are independent;
the check does not require them to match `docs/CURRENT_STATUS.md` or assess freshness.

**Usage:**
```bash
python scripts/check_public_docs.py
```

### `validate_v2.py`
Validation script for Pitch Tracking V2 integration.

Verifies core functionality without requiring pytest:
- Pre-roll capture
- Ramp-up observation capture
- Thread safety
- Timing accuracy
- Data validation

**Usage:**
```bash
python scripts/validate_v2.py
```

### `test_integration.py`
Tests hardening integration and component imports.

**Usage:**
```bash
python scripts/test_integration.py
```

## Test Launchers

### `test_camera_capture.py`
Test launcher for Camera Capture Validator.

Validates camera setup and calibration by capturing raw video without detection/tracking.

Use this to:
- Verify cameras are working correctly
- Test calibration setup
- Record test footage for debugging

**Usage:**
```bash
python scripts/test_camera_capture.py
```

### `test_coaching_app.py`
Test launcher for Coaching App prototype.

Launches the coaching-specific UI for testing.

**Usage:**
```bash
python scripts/test_coaching_app.py
```

### `test_setup_wizard.py`
Compatibility launcher for the five-stage guided setup. Camera actions are
explicit. Prefer `python launcher.py --setup --backend uvc`; use the
[rig walkthrough](../docs/RIG_VALIDATION_WALKTHROUGH.md) for physical qualification.

**Usage:**
```bash
python scripts/test_setup_wizard.py
```

## ML/Data Export Scripts

### `test_ml_data_export.py`
Verify ML training data export functionality.

Validates that a recorded session properly exported:
- Detection JSON files
- Observation JSON files
- Training frames (PNG)
- Calibration metadata

**Usage:**
```bash
python scripts/test_ml_data_export.py <session_dir>
```

**Example:**
```bash
python scripts/test_ml_data_export.py "recordings\session-2026-01-16_001"
```

## Recording Utilities

### `check_recordings.py`
Utility to inspect and validate recording directories.

**Usage:**
```bash
python scripts/check_recordings.py
```

---

## Note

These are standalone scripts for development/debugging, not part of the pytest test suite.

For pytest tests, see the `tests/` directory.
