# Copilot Instructions — PitchTracker

## Project Overview

PitchTracker is a Windows desktop application (Python 3.10+ / PySide6) for real-time baseball pitch tracking using dual stereo UVC cameras. It detects pitches via classical computer vision or ONNX ML models, triangulates 3D trajectories, and computes pitch metrics (velocity, break, approach angles). The UI supports three role-based workflows: **Setup Wizard**, **Coaching App**, and **Review Mode**.

## Build & Run

```powershell
# Install dependencies
pip install -r requirements.txt          # runtime
pip install -r requirements-dev.txt      # adds black, mypy, flake8, py-spy

# Run the app (launches role-selector UI)
.\run.ps1 -Backend uvc                  # dual USB cameras
.\run.ps1 -Backend opencv               # internal/single camera

# Or directly
python launcher.py
```

### Testing

```powershell
python -m pytest                         # full suite (~389 tests)
python -m pytest tests/test_config.py    # single file
python -m pytest tests/test_config.py::TestConfigLoading::test_load_default -v  # single test
python -m pytest tests/integration/      # integration tests only
python -m pytest tests/analysis/         # analysis module tests

# Clip-based detection tests (requires video file)
$env:PITCHTRACKER_TEST_VIDEO="C:\path\to\left.avi"
python -m pytest tests/test_video_clip.py
```

### Linting & Formatting

```powershell
black .                                  # format
flake8 .                                 # lint
mypy .                                   # type check
```

### Building the Installer

```powershell
.\build_installer.ps1 -Clean            # requires PyInstaller + Inno Setup 6
```

## Architecture

### Pipeline Flow

```
Cameras (capture/) → Detection (detect/) → Stereo Matching (stereo/)
  → Tracking (track/) → Trajectory Fitting (trajectory/) → Metrics (metrics/)
```

Each stage is a separate top-level module with a single responsibility. The pipeline is orchestrated by `app/pipeline_service.py` (`InProcessPipelineService`), which runs detection on async thread pools and updates the Qt UI on the main thread.

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `app/` | Pipeline orchestration, services, Qt integration, review workflows |
| `ui/` | PySide6 UI: main window, dialogs, setup wizard, coaching, themes |
| `detect/` | Classical blob detector + ONNX ML detector, lane gates, filters |
| `stereo/` | Left-right frame pairing, epipolar matching, triangulation |
| `track/` | 2D frame-by-frame tracker with state management |
| `trajectory/` | 3D trajectory fitting: physics-based drag model, radar fusion, EKF |
| `metrics/` | Strike zone analysis, release point, approach angles |
| `capture/` | Camera backends: UVC, OpenCV, simulated |
| `record/` | Session recording, frame/metadata persistence, ML data export |
| `contracts/` | Frozen dataclasses defining inter-module data types |
| `configs/` | YAML → immutable `AppConfig` dataclass, validators |
| `log_config/` | Loguru setup: console (INFO) + rotating file logs (DEBUG/ERROR) |
| `schema/` | JSON schemas for session summaries and versioning |

### Entry Points

- **`launcher.py`** — Primary entry point. Clears bytecode cache, shows role selector (Setup / Coaching / Review).
- **`launch_app.py`** — Thin wrapper that ensures sys.path and calls `launcher.main()`.
- **`run.ps1`** — PowerShell launcher with `-Backend` parameter.

### Contracts System

`contracts/types.py` defines frozen dataclasses that flow through the pipeline:
`Frame` → `Detection` → `StereoObservation` → `TrackSample` → `TrajectoryFit` → `PitchMetrics`

`contracts/versioning.py` defines `SCHEMA_VERSION` and `APP_VERSION` constants used directly in manifests. `make_envelope()` is available for wrapping arbitrary payloads with version metadata but manifests use flat `schema_version`/`app_version` keys via `create_base_manifest()` in `app/pipeline/recording/manifest.py`.

### Configuration

YAML files in `configs/` (e.g., `default.yaml`, `snapdragon.yaml`) are loaded by `configs/settings.py` into a frozen `AppConfig` dataclass. On Windows ARM, the UI auto-selects `configs/snapdragon.yaml` unless overridden with `--config`.

## Conventions

### File & Code Size Limits (strictly enforced)

- **Files: max 500 lines** (target 200–300). Stop adding code at 400 lines and extract.
- **Functions: max 50 lines** (target 10–20). Max 5 parameters (use dataclasses for more).
- **Classes: max 30 methods** (target 10–15).
- **Cyclomatic complexity: max 10**. Max 3 levels of nesting.

### Naming

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`, private: `_leading_underscore`

### Error Handling

Always use custom exceptions from `exceptions.py`, never bare `Exception` or `RuntimeError`. The hierarchy:

```
PitchTrackerError
├── CameraError (+ Connection, Configuration, NotFound)
├── CalibrationError (+ InvalidROI, CheckerboardNotFound, Input, Execution, Persistence)
├── ConfigError (+ InvalidConfig, ConfigValidation)
├── DetectionError (+ ModelLoad, ModelInference)
├── StereoError (+ Triangulation)
└── RecordingError (+ DiskSpace, FileWrite)
```

Always chain exceptions with `raise CustomError(...) from exc` and clean up resources on error.

### Logging

Use loguru via `from log_config.logger import get_logger`:

```python
logger = get_logger(__name__)
```

Log levels: INFO for user-visible actions, DEBUG for internal state, WARNING for recoverable errors, ERROR for failures. Don't log every frame.

### Imports

Organize in order: stdlib → third-party → local. Use `TYPE_CHECKING` to avoid circular imports:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.main_window import MainWindow
```

### UI / Qt

- PySide6 types stay in `ui/` — don't pass `QWidget` to core pipeline modules.
- Each dialog gets its own file (max 300 lines). Use `values()` to return user input.
- Use signals/callbacks for decoupling; no business logic in dialogs.

### Testing

- No conftest.py — fixtures are inline with `@pytest.fixture` in each test file.
- Uses `unittest.mock` (Mock, patch, MagicMock) for mocking.
- Integration tests use `unittest.TestCase` with setUp/tearDown.
- Test files mirror source structure under `tests/`.

### Version Management

Update version in both `installer.iss` and `contracts/versioning.py` (`APP_VERSION`). Tag releases as `v1.x.x`.
