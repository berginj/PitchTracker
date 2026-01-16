# PitchTracker Design Principles

## Core Philosophy

**"Small files, focused responsibilities, clear boundaries."**

This document defines the design ethos and coding standards for PitchTracker. All development must follow these principles to maintain code quality, testability, and maintainability.

---

## 1. File Size Limits

### Hard Limits
- **Maximum file size: 500 lines** (including docstrings and comments)
- **Preferred file size: 200-300 lines**
- **Warning threshold: 400 lines** (start planning extraction)

### Why?
- Easier to understand and review
- Faster to navigate and edit
- More testable in isolation
- Reduces merge conflicts
- Encourages modular design

### Enforcement
If a file exceeds 400 lines:
1. **Stop** - Do not add more code
2. **Analyze** - Identify logical groupings
3. **Extract** - Create focused modules
4. **Refactor** - Update imports and tests

### Examples (Before → After)
- ❌ `ui/qt_app.py`: 2,807 lines (monolithic)
- ✅ `ui/qt_app.py`: 59 lines (entry point)
- ✅ `ui/main_window.py`: 1,465 lines (still large, but focused)
- ✅ `ui/dialogs/*.py`: 10 files, 45-560 lines each
- ✅ `ui/geometry.py`: 80 lines (utilities)

---

## 2. Module Organization

### Single Responsibility Principle
Each module should have ONE clear purpose:
- ✅ `ui/geometry.py` - Geometry calculations only
- ✅ `ui/drawing.py` - Rendering functions only
- ✅ `ui/export.py` - Export functions only
- ❌ `ui/utils.py` - Too vague, mixing concerns

### Package Structure
Organize by **feature** or **responsibility**, not by type:

```
✅ Good: Organized by feature
ui/
  ├── dialogs/          # All dialog classes
  │   ├── calibration_*.py
  │   └── settings_*.py
  ├── widgets/          # Reusable widgets
  │   └── roi_label.py
  └── export.py         # Export functionality

❌ Bad: Organized by type
ui/
  ├── classes/          # All classes mixed together
  ├── functions/        # All functions mixed together
  └── helpers/          # Vague "helper" functions
```

### File Naming Conventions
- **Modules**: `snake_case.py` (e.g., `calibration_guide.py`)
- **Classes**: `PascalCase` (e.g., `CalibrationGuide`)
- **Functions**: `snake_case` (e.g., `frame_to_pixmap`)
- **Private functions**: `_leading_underscore` (e.g., `_cleanup_cameras`)

---

## 3. Class Design

### Class Size Limits
- **Maximum methods per class: 30**
- **Preferred methods per class: 10-15**
- **Maximum lines per method: 50**

### Class Responsibilities
One class = One responsibility:
- ✅ `RoiLabel` - Interactive ROI drawing widget
- ✅ `CalibrationGuide` - Display calibration help text
- ❌ `MainWindow` - Does everything (needs further refactoring)

### When to Split a Class
If a class has:
- More than 30 methods → Extract helper classes
- More than 500 lines → Split by responsibility
- Multiple unrelated concerns → Create separate classes

### Example Split:
```python
# Before: MainWindow (1,465 lines, 50+ methods)
class MainWindow:
    # Capture control
    # Recording control
    # ROI management
    # Calibration
    # Device management
    # Replay control
    # Export logic
    # UI layout
    # Settings dialogs

# After: Split responsibilities
class MainWindow:        # UI layout + coordination (800 lines)
class CaptureManager:    # Capture control (200 lines)
class RecordingManager:  # Recording control (200 lines)
class ReplayController:  # Replay logic (150 lines)
# Export already extracted to ui/export.py
# Dialogs already extracted to ui/dialogs/
```

---

## 4. Function Design

### Function Size Limits
- **Maximum lines per function: 50**
- **Preferred lines per function: 10-20**
- **Maximum parameters: 5** (use dataclasses for more)

### Function Complexity
- **Maximum cyclomatic complexity: 10**
- **Avoid deep nesting** (max 3 levels)
- **One function = One thing**

### Examples
```python
# ✅ Good: Small, focused, clear purpose
def normalize_rect(rect: Rect, image_size: tuple[int, int]) -> Optional[Rect]:
    """Clamp rectangle to image bounds."""
    x, y, w, h = rect
    img_w, img_h = image_size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = min(w, img_w - x)
    h = min(h, img_h - y)
    return (x, y, w, h) if w > 0 and h > 0 else None

# ❌ Bad: Too long, multiple responsibilities
def process_everything(config, left_cam, right_cam, detector, roi, ...):
    # 150 lines of mixed concerns
    # Camera setup
    # Detection
    # Tracking
    # Metrics
    # Recording
    # Export
    pass
```

### Refactoring Large Functions
If a function exceeds 50 lines:
1. Identify logical sections
2. Extract to helper functions
3. Use descriptive names
4. Add docstrings

---

## 5. Dependency Management

### Import Organization
Always organize imports in this order:
1. Standard library
2. Third-party packages
3. Local application modules

```python
# ✅ Good: Clear organization
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtWidgets

from configs.settings import load_config
from exceptions import CameraConnectionError
from log_config.logger import get_logger
```

### Avoid Circular Imports
- Keep dependency graph acyclic
- Use TYPE_CHECKING for type hints
- Pass callbacks instead of importing parent modules

```python
# ✅ Good: Avoids circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.main_window import MainWindow

class CalibrationWizard:
    def __init__(self, parent: "MainWindow"):
        self._parent = parent
```

### Minimize Dependencies
- Don't import entire modules for one function
- Use specific imports: `from module import function`
- Avoid `import *` (except in `__init__.py` for re-exports)

---

## 6. Error Handling

### Always Use Custom Exceptions
- ❌ Never use generic `Exception` or `RuntimeError`
- ✅ Always use specific custom exceptions

```python
# ✅ Good: Specific exceptions
from exceptions import CameraConnectionError, ModelLoadError

try:
    camera.open(serial)
except Exception as exc:
    raise CameraConnectionError(f"Failed to open camera {serial}") from exc

# ❌ Bad: Generic exceptions
try:
    camera.open(serial)
except Exception:
    raise RuntimeError("Camera failed")  # Too vague
```

### Error Handling Pattern
```python
def risky_operation():
    """Do something that might fail."""
    logger.info("Starting operation")

    try:
        # Attempt operation
        result = do_something()
        logger.debug("Operation succeeded")
        return result

    except SpecificError as exc:
        # Handle specific known error
        logger.error(f"Known error occurred: {exc}")
        raise CustomException(f"Friendly message: {exc}") from exc

    except Exception as exc:
        # Catch unexpected errors
        logger.exception("Unexpected error")
        raise PitchTrackerError(f"Unexpected error: {exc}") from exc
```

### Resource Cleanup
Always clean up resources, even on error:

```python
def start_capture(self, left_serial: str, right_serial: str):
    try:
        self._left.open(left_serial)
        self._right.open(right_serial)
        # ... more setup

    except Exception as exc:
        # Clean up partial state
        self._cleanup_cameras()
        raise CameraConnectionError(f"Startup failed: {exc}") from exc
```

---

## 7. Logging

### Always Log Important Events
- **INFO**: User-visible actions (start/stop capture, record pitch)
- **DEBUG**: Internal state changes (camera opened, detector initialized)
- **WARNING**: Recoverable errors (frame drop, slow processing)
- **ERROR**: Failures that stop operation (camera disconnect)
- **EXCEPTION**: Use for unexpected errors (includes stack trace)

### Logging Pattern
```python
from log_config.logger import get_logger

logger = get_logger(__name__)

def important_operation():
    logger.info("Starting important operation")

    try:
        logger.debug("Step 1: Initialize")
        initialize()

        logger.debug("Step 2: Process")
        process()

        logger.info("Operation completed successfully")

    except Exception as exc:
        logger.exception("Operation failed")
        raise
```

### What to Log
- ✅ State transitions (idle → capturing → recording)
- ✅ Resource acquisition/release (camera open/close)
- ✅ Configuration changes (detector mode changed)
- ✅ Errors and exceptions (with context)
- ❌ Every frame processed (too noisy)
- ❌ Sensitive data (passwords, API keys)

---

## 8. Testing

### Test Organization
Mirror the source structure:
```
src/
  ui/
    dialogs/
      calibration_guide.py
    export.py
    geometry.py

tests/
  ui/                    # Match src structure
    test_dialogs.py      # Or test_calibration_guide.py
    test_export.py
    test_geometry.py
  test_ui_imports.py     # Smoke tests
```

### Test Coverage Targets
- **Critical modules: 80%+ coverage** (capture, detect, stereo, metrics)
- **UI modules: 50%+ coverage** (dialogs, widgets)
- **Utility modules: 90%+ coverage** (geometry, drawing)

### Types of Tests
1. **Unit tests**: Test individual functions/classes
2. **Integration tests**: Test module interactions
3. **Smoke tests**: Verify imports and basic instantiation
4. **Property tests**: Use hypothesis for edge cases

### Test File Size
- **Maximum test file size: 500 lines**
- If a test file gets too large, split by test class or feature

---

## 9. Documentation

### Required Documentation
Every module must have:
1. **Module docstring** - Purpose and usage
2. **Class docstrings** - Responsibility and example
3. **Public function docstrings** - Args, returns, raises
4. **Type hints** - All function signatures

### Docstring Format
```python
"""Module purpose in one line.

Longer description if needed.
Multiple paragraphs are fine.
"""

def function_name(arg: Type) -> ReturnType:
    """One-line summary of function purpose.

    Longer description if needed.
    Explain what the function does, not how.

    Args:
        arg: Description of argument

    Returns:
        Description of return value

    Raises:
        ExceptionType: When and why it's raised
    """
```

### Comments vs Docstrings
- **Docstrings**: What the code does (public API)
- **Comments**: Why the code does it (implementation details)

```python
# ✅ Good: Docstring explains what, comment explains why
def normalize_rect(rect: Rect, size: tuple) -> Optional[Rect]:
    """Clamp rectangle to image bounds."""
    x, y, w, h = rect
    # Ensure rectangle doesn't extend beyond image edges
    # (can happen when user draws ROI partially off-screen)
    x = max(0, min(x, size[0] - 1))
    ...
```

---

## 10. UI-Specific Guidelines

### Qt/PySide6 Best Practices
- Keep Qt types in `ui/` module only
- Don't pass `QWidget` to core pipeline modules
- Use callbacks/signals instead of tight coupling

### Dialog Guidelines
- Each dialog in its own file
- Maximum 300 lines per dialog
- Use `values()` method to return user input
- No business logic in dialogs (just UI)

### Widget Guidelines
- Reusable widgets go in `ui/widgets/`
- One widget = one file
- Maximum 200 lines per widget
- Emit signals for user actions

---

## 11. Performance Guidelines

### When to Optimize
1. **Profile first** - Don't guess what's slow
2. **Optimize hot paths only** - 90% of time in 10% of code
3. **Maintain readability** - Don't sacrifice clarity for minor gains

### Performance Budgets
- Frame processing: < 10ms per frame (100+ FPS)
- Detection: < 5ms per frame per camera
- UI update: < 16ms (60 FPS)

### Optimization Patterns
- Use NumPy operations (avoid Python loops)
- Cache expensive computations
- Use threading for I/O-bound tasks
- Profile with `cProfile` or `py-spy`

---

## 12. Refactoring Guidelines

### When to Refactor
Refactor when:
- ✅ File exceeds 400 lines
- ✅ Class exceeds 30 methods
- ✅ Function exceeds 50 lines
- ✅ Adding new feature would mix concerns
- ✅ Tests are hard to write

### How to Refactor
1. **Write tests first** (if they don't exist)
2. **Extract in small steps** (commit often)
3. **Verify tests pass** after each extraction
4. **Update documentation** immediately
5. **Review changes** before merging

### Refactoring Patterns
- Extract Method: Large function → Multiple small functions
- Extract Class: Large class → Multiple focused classes
- Extract Module: Large file → Multiple files
- Move Method: Move to appropriate class
- Inline: Remove unnecessary abstraction

---

## 13. Git and Version Control

### Commit Guidelines
- **Commit size**: One logical change per commit
- **Commit message**: Describe what and why, not how
- **Co-author**: Always add `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`

### Commit Message Format
```
Brief summary (50 chars or less)

Detailed explanation of what changed and why.
Can be multiple paragraphs.

Specific changes:
- Added error handling to camera startup
- Extracted dialogs to separate files
- Improved logging throughout

Benefits:
- Better error messages for users
- Easier to test individual components

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

### Branch Strategy
- **main**: Production-ready code
- **feature/***: New features
- **refactor/***: Code reorganization
- **fix/***: Bug fixes

---

## 14. Code Review Checklist

Before committing code, verify:

### File Organization
- [ ] No file exceeds 500 lines
- [ ] Each file has clear, single responsibility
- [ ] Imports are organized correctly
- [ ] No circular dependencies

### Code Quality
- [ ] Functions under 50 lines
- [ ] Classes under 30 methods
- [ ] No code duplication
- [ ] Type hints on all functions
- [ ] Docstrings on public APIs

### Error Handling
- [ ] Custom exceptions used (not generic)
- [ ] All errors logged appropriately
- [ ] Resources cleaned up on error
- [ ] Error messages are user-friendly

### Testing
- [ ] Unit tests written/updated
- [ ] All tests pass
- [ ] Coverage meets targets
- [ ] Smoke tests for new modules

### Documentation
- [ ] Module docstring updated
- [ ] README updated if needed
- [ ] AGENTS.md updated if structure changed
- [ ] Comments explain why, not what

---

## 15. Violation Policy

### What Happens When Principles Are Violated

**For Files Exceeding Limits:**
1. Create a GitHub issue documenting the violation
2. Add a TODO comment in the file: `# TODO: Refactor - exceeds 500 line limit`
3. Plan extraction in next sprint
4. Do not add more code until refactored

**For New Code:**
- Pull requests that violate these principles will be **rejected**
- Exception: Temporary violation with explicit plan and timeline
- Must have approval from project maintainer

---

## 16. Quick Reference Card

### The Golden Rules

1. **Files < 500 lines** (target 200-300)
2. **Functions < 50 lines** (target 10-20)
3. **Classes < 30 methods** (target 10-15)
4. **One responsibility per module**
5. **Custom exceptions always**
6. **Log all important events**
7. **Test everything**
8. **Document public APIs**
9. **Type hints everywhere**
10. **Commit often, refactor fearlessly**

### Quick Decisions

**"Should I create a new file?"**
- File approaching 400 lines? → **Yes**
- Mixing two concerns? → **Yes**
- Would make testing easier? → **Yes**

**"Should I extract this function?"**
- Function over 30 lines? → **Probably**
- Code duplicated? → **Yes**
- Hard to understand? → **Yes**

**"Should I split this class?"**
- Over 20 methods? → **Consider it**
- Over 30 methods? → **Do it now**
- Mixing UI and business logic? → **Definitely**

---

## 17. Examples of Excellence

### Great Modules (Follow These)
- ✅ `ui/geometry.py` (80 lines, 5 functions, clear purpose)
- ✅ `ui/device_utils.py` (70 lines, 3 functions, well-tested)
- ✅ `ui/dialogs/checklist_dialog.py` (45 lines, simple dialog)
- ✅ `exceptions.py` (110 lines, 10 exception classes)
- ✅ `log_config/logger.py` (80 lines, focused logging setup)

### Modules Needing Refactoring
- ⚠️ `ui/main_window.py` (1,465 lines - needs further splitting)
- ⚠️ `app/pipeline_service.py` (large, needs extraction)

---

## 18. Getting Help

### When You're Unsure
1. **Check this document** - Is there a principle that applies?
2. **Look at examples** - How is it done elsewhere?
3. **Ask in code review** - Get team feedback
4. **Propose alternatives** - Document tradeoffs

### Resources
- This document: Design principles and patterns
- `AGENTS.md`: Project structure and setup
- `REFACTORING_PROGRESS.md`: Example of good refactoring
- `IMPROVEMENTS_SUMMARY.md`: Technical improvements implemented

---

## Summary

**Remember**: These principles exist to make the codebase:
- **Easier to understand** - Small files, clear responsibilities
- **Easier to test** - Isolated, focused modules
- **Easier to maintain** - Low coupling, high cohesion
- **Easier to extend** - Well-defined boundaries

**When in doubt**: Ask "Will this make the code easier to work with in 6 months?" If no, refactor.

---

*This document is living and should be updated as we learn and evolve. Last updated: 2026-01-15*
