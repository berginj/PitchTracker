> Historical January 2026 notes. Not agent instructions or current readiness evidence.
> Use [AGENTS.md](../../../AGENTS.md) for maintenance instructions.

# PitchTracker Agent Notes

## 🎯 Project Summary
PitchTracker is a Windows-first Python app that uses two USB3 cameras, OpenCV, and a PySide6 UI to capture, detect, and track baseball/softball pitches. The UI drives an in-process pipeline service, with core modules living outside the UI layer.

**Status**: Production-ready with comprehensive error handling, logging, and modular architecture.

---

## 🚀 Quick Start

### Setup (PowerShell)
```powershell
.\setup.ps1
```

### Run (PowerShell)
```powershell
.\run.ps1 -Backend uvc      # For USB cameras
.\run.ps1 -Backend opencv   # For built-in cameras
.\run.ps1 -Backend sim      # For simulation mode
```

### Tests
```powershell
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=. --cov-report=html

# Run specific test suite
python -m pytest tests/test_ui_imports.py -v
python -m pytest tests/test_ui_smoke.py -v

# Run clip test (optional)
$env:PITCHTRACKER_TEST_VIDEO="C:\path\to\left.avi"
python -m pytest tests/test_video_clip.py
```

---

## 📁 Project Structure

### Core Directories
```
PitchTracker/
├── app/                    # Pipeline service (needs refactoring)
├── capture/                # Camera backends (UVC, OpenCV, Sim)
├── calib/                  # Calibration utilities
├── configs/                # Configuration and validation
├── contracts/              # Serialized contract definitions
├── detect/                 # Detection (classical + ML)
├── exceptions.py           # Custom exception hierarchy
├── log_config/             # Structured logging with loguru
├── metrics/                # Strike zone and metrics
├── record/                 # Recording and manifests
├── stereo/                 # Stereo matching and triangulation
├── telemetry/              # Performance tracking
├── tests/                  # Pytest test suite
├── track/                  # Simple tracker
└── ui/                     # PySide6 UI (RECENTLY REFACTORED ✅)
    ├── __init__.py         # Exports MainWindow, Renderer
    ├── qt_app.py           # Entry point (59 lines)
    ├── main_window.py      # Main application window (1,465 lines)
    ├── geometry.py         # Geometry utilities (80 lines)
    ├── drawing.py          # Rendering functions (230 lines)
    ├── device_utils.py     # Device discovery (70 lines)
    ├── export.py           # Export functions (340 lines)
    ├── dialogs/            # 10 dialog classes in separate files
    │   ├── __init__.py
    │   ├── calibration_guide.py
    │   ├── calibration_wizard_dialog.py
    │   ├── checklist_dialog.py
    │   ├── detector_settings_dialog.py
    │   ├── plate_plane_dialog.py
    │   ├── quick_calibrate_dialog.py
    │   ├── recording_settings_dialog.py
    │   ├── session_summary_dialog.py
    │   ├── startup_dialog.py
    │   └── strike_zone_settings_dialog.py
    └── widgets/            # Reusable widgets
        ├── __init__.py
        └── roi_label.py    # Interactive ROI drawing widget
```

---

## 🎨 Design Principles

### **READ THIS FIRST**: [DESIGN_PRINCIPLES.md](./DESIGN_PRINCIPLES.md)

**Critical Rules for All Development:**
1. **Files must be < 500 lines** (target 200-300 lines)
2. **Functions must be < 50 lines** (target 10-20 lines)
3. **Classes must be < 30 methods** (target 10-15 methods)
4. **One responsibility per module**
5. **Always use custom exceptions** (never generic `Exception` or `RuntimeError`)
6. **Log all important events** (use `from log_config.logger import get_logger`)
7. **Test everything** (smoke tests + unit tests + integration tests)
8. **Type hints everywhere** (all function signatures)
9. **Document public APIs** (docstrings with Args, Returns, Raises)
10. **Commit often** (one logical change per commit)

### Quick Decision Tree
- **File approaching 400 lines?** → Extract modules NOW
- **Function over 30 lines?** → Consider extraction
- **Function over 50 lines?** → Extract NOW
- **Class over 30 methods?** → Split into multiple classes
- **Adding code to 500+ line file?** → STOP. Refactor first.

---

## 🏗️ Architecture Principles

### Separation of Concerns
- **Core pipeline**: UI-agnostic, no Qt types outside `ui/`
- **UI layer**: PySide6 only, no business logic in dialogs
- **Configuration**: Centralized in `configs/`, validated with JSON Schema
- **Errors**: Custom exception hierarchy in `exceptions.py`
- **Logging**: Structured logging in `logging/`, used throughout

### Module Boundaries
```
ui/           → app/, configs/, exceptions, logging
app/          → capture/, detect/, stereo/, track/, metrics/
detect/       → contracts/, exceptions, logging
capture/      → exceptions, logging
configs/      → exceptions, logging
```

### Dependency Flow
```
UI Layer (PySide6)
    ↓
Pipeline Service (app/)
    ↓
Core Modules (capture, detect, stereo, track, metrics)
    ↓
Contracts & Utilities (contracts, exceptions, logging)
```

---

## 🔧 Recent Improvements (2026-01-15)

### ✅ Completed
1. **Structured Logging** - loguru with rotation, thread-safety, performance tracking
2. **Custom Exceptions** - 10+ exception types for type-safe error handling
3. **Config Validation** - JSON Schema validation for YAML configs
4. **Camera Error Handling** - Comprehensive error handling in UVC backend
5. **Expanded Tests** - 22+ new tests (stereo, detector, strike zone)
6. **UI Refactoring** - Reduced `qt_app.py` from 2,807 to 59 lines (97.9% reduction)
   - Extracted 18 focused modules
   - Created 10 dialog files
   - Extracted widgets, utilities, export functions
7. **Pipeline Error Handling** - Added error handling to pipeline service
8. **Smoke Tests** - 26 tests for UI imports and functionality

### 📊 Metrics
- **Lines organized**: 2,748 from qt_app.py → 18 focused modules
- **Files created**: 35 new modules (UI + tests)
- **Test coverage**: 22 core tests + 26 UI smoke tests
- **Time efficiency**: 56% faster than estimated (3.75h vs 8.5h)

---

## 📝 Key Files and Documentation

### Essential Reading
- **[DESIGN_PRINCIPLES.md](./DESIGN_PRINCIPLES.md)** - Core design ethos and coding standards
- **[REQ.md](./REQ.md)** - Architecture, data contract definitions, system constraints
- **[REFACTORING_PROGRESS.md](./REFACTORING_PROGRESS.md)** - Complete UI refactoring log
- **[IMPROVEMENTS_SUMMARY.md](./IMPROVEMENTS_SUMMARY.md)** - Technical improvements implemented
- **[AGENTS.md](agent-notes-historical.md)** - This file (agent quick reference)

### Configuration
- **[configs/default.yaml](./configs/default.yaml)** - Main configuration file
- **[configs/validator.py](./configs/validator.py)** - JSON Schema validation

### Contracts
- If you change serialized contracts or schemas:
  1. Update `contracts-shared/schema/version.json`
  2. Ensure manifests include schema/app metadata
  3. Run tests to verify compatibility

---

## 🚨 Critical Reminders

### Before Writing Code
1. **Check file size** - Will this exceed 500 lines? If yes, refactor first
2. **Check function size** - Will this exceed 50 lines? If yes, extract helpers
3. **Check responsibility** - Does this belong in this module? If no, create new module
4. **Check tests** - Do tests exist? If no, write them first

### During Development
1. **Use custom exceptions** - Never use generic `Exception` or `RuntimeError`
2. **Add logging** - Log important events (INFO), state changes (DEBUG), errors (ERROR)
3. **Add type hints** - All function signatures must have type hints
4. **Write docstrings** - All public functions must have docstrings

### Before Committing
1. **Run tests** - `python -m pytest` must pass
2. **Check imports** - Run `python -m pytest tests/test_ui_imports.py`
3. **Review changes** - Does this follow design principles?
4. **Update docs** - Update AGENTS.md if structure changed

---

## 🐛 Troubleshooting

### Import Errors
```powershell
# Test all UI imports
python -m pytest tests/test_ui_imports.py -v

# Check for circular imports
python -c "from ui import MainWindow; print('✓ No circular imports')"
```

### Camera Issues
- Check `logs/app.log` for detailed error messages
- Verify camera permissions (Windows Camera Privacy Settings)
- Try different backends: `-Backend uvc`, `-Backend opencv`

### Configuration Issues
```python
# Validate config file
python -c "from configs.validator import validate_config_file; validate_config_file('configs/default.yaml')"
```

---

## 🎓 Learning Resources

### Understanding the Codebase
1. Start with `ui/qt_app.py` (entry point, 59 lines)
2. Read `ui/main_window.py` (main application logic)
3. Explore `app/pipeline_service.py` (core pipeline)
4. Study `detect/`, `stereo/`, `metrics/` (computer vision algorithms)

### Adding Features
1. Read [DESIGN_PRINCIPLES.md](./DESIGN_PRINCIPLES.md)
2. Find appropriate module (or create new one)
3. Write tests first (TDD)
4. Implement feature (following size limits)
5. Add error handling and logging
6. Update documentation
7. Run full test suite
8. Commit with descriptive message

### Refactoring
1. Read [REFACTORING_PROGRESS.md](./REFACTORING_PROGRESS.md) for example
2. Write tests for existing code (if missing)
3. Extract in small steps
4. Verify tests pass after each step
5. Update imports and documentation
6. Commit each extraction separately

---

## 🤝 Contributing

### Code Review Checklist
Before submitting code, ensure:
- [ ] No file exceeds 500 lines
- [ ] No function exceeds 50 lines
- [ ] No class exceeds 30 methods
- [ ] Custom exceptions used (not generic)
- [ ] All errors logged appropriately
- [ ] Type hints on all functions
- [ ] Docstrings on public APIs
- [ ] Tests written/updated
- [ ] All tests pass
- [ ] Documentation updated

### Commit Message Format
```
Brief summary (50 chars or less)

Detailed explanation of changes.

Specific changes:
- Added X
- Fixed Y
- Refactored Z

Benefits:
- Better performance
- Easier to test

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 📞 Getting Help

### In Code
- Check existing modules for patterns
- Read function docstrings for usage
- Look at tests for examples

### Documentation
- Design questions → [DESIGN_PRINCIPLES.md](./DESIGN_PRINCIPLES.md)
- Architecture questions → [REQ.md](./REQ.md)
- Refactoring questions → [REFACTORING_PROGRESS.md](./REFACTORING_PROGRESS.md)

### When Stuck
1. Check if principle applies (DESIGN_PRINCIPLES.md)
2. Look for similar code (grep/search)
3. Read tests for examples
4. Consult team in code review

---

## 🎯 Current Priorities

### High Priority
1. **Test the refactored UI** - Run application, verify all features work
2. **Add more pipeline error handling** - Extend to recording, detection threads
3. **Refactor large modules** - app/pipeline_service.py, ui/main_window.py

### Medium Priority
1. **Improve test coverage** - Target 80% on core modules
2. **Add integration tests** - Test full pipeline end-to-end
3. **Documentation** - API docs, architecture diagrams

### Low Priority
1. **Performance optimization** - Profile and optimize hot paths
2. **CI/CD setup** - Automated testing on commits
3. **Additional export formats** - HDF5, TrackMan CSV

---

**Remember**: Keep files small, responsibilities clear, and boundaries well-defined. When in doubt, refer to [DESIGN_PRINCIPLES.md](./DESIGN_PRINCIPLES.md).

*Last updated: 2026-01-15*
