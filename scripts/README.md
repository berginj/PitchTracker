# Utility Scripts

This directory contains standalone utility and validation scripts for PitchTracker development and testing.

## Validation Scripts

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
Test launcher for Setup Wizard.

Validates the initial setup wizard flow.

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
