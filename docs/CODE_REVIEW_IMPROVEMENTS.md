# Code Review & Improvement Suggestions

**Review Date**: 2026-02-18
**Reviewer**: Analysis of recent refactoring work

## Executive Summary

The recent work shows excellent progress on documentation, testing, and refactoring. Below are prioritized improvement suggestions organized by impact and effort.

---

## 🔴 High Priority (Should Fix Soon)

### 1. ProfileManager: Tight UI Coupling

**Issue**: ProfileManager directly manipulates Qt widgets, violating separation of concerns.

**Current Code** (profile_manager.py:117-125):
```python
if left:
    for i in range(self._left_input.count()):
        if self._left_input.itemData(i) == left:
            self._left_input.setCurrentIndex(i)
            break
    else:
        self._left_input.setCurrentText(left)
```

**Problem**:
- Hard to test without Qt widgets
- Violates Single Responsibility (manages data + UI)
- Can't reuse ProfileManager in non-Qt contexts

**Recommended Solution**:
```python
# profile_manager.py - Data model only
class ProfileManager:
    """Pure data/business logic - no Qt dependencies."""

    def load_profile(self, name: str) -> ProfileData:
        """Load profile, return data model."""
        profile = load_profile(name)
        return ProfileData(
            left_serial=profile.get("left_serial"),
            right_serial=profile.get("right_serial"),
            roi_config=profile.get("rois")
        )

    def get_current_state(self) -> dict:
        """Return current state without UI coupling."""
        return {
            "profile": self._location_profile,
            "pitcher": self._pitcher_name,
        }

# main_window.py - UI logic
def _load_profile(self):
    profile_data = self._profile_manager.load_profile(name)
    self._apply_profile_to_ui(profile_data)  # New helper method
```

**Benefits**:
- ✅ Testable without Qt
- ✅ True separation of concerns
- ✅ Reusable in CLI tools, tests, batch scripts

**Effort**: Medium (2-3 hours to refactor)

---

### 2. Error Handling: Swallowing Exceptions

**Issue**: Multiple places use broad exception catching without logging details.

**Examples**:
```python
# profile_manager.py:109
except Exception as exc:  # noqa: BLE001 - show profile errors
    QtWidgets.QMessageBox.warning(parent, "Load Profile", str(exc))
    return
```

**Problems**:
- Loses stack traces (hard to debug)
- User sees generic error, can't self-diagnose
- No telemetry/metrics on failure rates

**Recommended Solution**:
```python
from log_config.logger import get_logger

logger = get_logger(__name__)

def load_profile(self, parent: QtWidgets.QWidget) -> bool:
    """Load profile, return success status."""
    name = self._profile_combo.currentText().strip()
    if not name:
        return False

    try:
        profile = load_profile(name)
    except FileNotFoundError as exc:
        logger.warning(f"Profile '{name}' not found: {exc}")
        QtWidgets.QMessageBox.warning(
            parent,
            "Load Profile",
            f"Profile '{name}' not found.\n\n"
            f"Available profiles:\n" + "\n".join(list_profiles())
        )
        return False
    except ValueError as exc:
        logger.error(f"Invalid profile data in '{name}': {exc}", exc_info=True)
        QtWidgets.QMessageBox.warning(
            parent,
            "Load Profile",
            f"Profile '{name}' is corrupted.\n\n"
            f"Error: {exc}\n\n"
            f"Try deleting and recreating the profile."
        )
        return False
    except Exception as exc:
        logger.exception(f"Unexpected error loading profile '{name}'")
        QtWidgets.QMessageBox.critical(
            parent,
            "Load Profile",
            f"Unexpected error loading profile.\n\n"
            f"Error: {exc}\n\n"
            f"Check logs for details."
        )
        return False

    # ... success path ...
    return True
```

**Benefits**:
- ✅ Specific error messages for users
- ✅ Full stack traces in logs
- ✅ Metrics on failure types
- ✅ Return values enable caller logic

**Effort**: Low (1-2 hours across all controllers)

---

### 3. Missing Input Validation

**Issue**: No validation of profile/pitcher names before saving.

**Current Code** (profile_manager.py:158):
```python
name = self._profile_name_input.text().strip()
if not name:
    QtWidgets.QMessageBox.information(parent, "Save Profile", "Enter a profile name.")
    return
```

**Problems**:
- Allows invalid characters in profile names (/, \, :, etc.)
- No length limits (could cause filesystem issues)
- No check for name conflicts
- No sanitization (security risk if names used in paths)

**Recommended Solution**:
```python
import re

def validate_profile_name(name: str) -> tuple[bool, str]:
    """Validate profile name, return (is_valid, error_message)."""
    if not name:
        return False, "Profile name cannot be empty."

    if len(name) > 100:
        return False, "Profile name too long (max 100 characters)."

    # Allow alphanumeric, spaces, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9 _-]+$', name):
        return False, "Profile name contains invalid characters.\nAllowed: letters, numbers, spaces, hyphens, underscores."

    # Check for existing profile
    if name in list_profiles():
        return False, f"Profile '{name}' already exists.\nChoose a different name or delete the existing profile."

    return True, ""

def save_profile(self, parent: QtWidgets.QWidget) -> None:
    name = self._profile_name_input.text().strip()
    is_valid, error_msg = validate_profile_name(name)
    if not is_valid:
        QtWidgets.QMessageBox.warning(parent, "Save Profile", error_msg)
        return
    # ... rest of save logic ...
```

**Benefits**:
- ✅ Prevents filesystem errors
- ✅ Better UX (clear validation rules)
- ✅ Security (prevents path traversal)
- ✅ Consistency across UI

**Effort**: Low (1 hour)

---

## 🟡 Medium Priority (Should Consider)

### 4. Test Coverage Gaps

**Issue**: New ProfileManager has no unit tests.

**Current State**:
- ✅ UI workflow tests exist (test_ui_workflows.py)
- ❌ No unit tests for ProfileManager
- ❌ No tests for error paths
- ❌ No tests for edge cases

**Recommended Tests**:
```python
# tests/ui/test_profile_manager.py (NEW)
import pytest
from unittest.mock import Mock, patch
from ui.controllers.profile_manager import ProfileManager

class TestProfileManager:
    def test_load_profile_success(self):
        """Test successful profile load."""
        # Test implementation
        pass

    def test_load_profile_not_found(self):
        """Test loading non-existent profile."""
        pass

    def test_save_profile_invalid_name(self):
        """Test saving with invalid characters."""
        pass

    def test_set_pitcher_saves_to_state(self):
        """Test pitcher selection persists."""
        pass

    def test_refresh_profiles_updates_combo(self):
        """Test profile list refresh."""
        pass
```

**Coverage Target**: 80%+ for new controller classes

**Effort**: Medium (3-4 hours per controller)

---

### 5. Callback Hell Pattern

**Issue**: ProfileManager uses callbacks for parent notification.

**Current Code** (profile_manager.py:39-40):
```python
on_profile_loaded: Optional[Callable[[str], None]] = None,
on_rois_changed: Optional[Callable[[], None]] = None,
```

**Problems**:
- Hard to track control flow
- Error handling unclear (what if callback raises?)
- Adding features requires modifying constructor
- Testing requires mocking callbacks

**Recommended Solution**: Use Qt Signals (proper Qt pattern)
```python
from PySide6.QtCore import QObject, Signal

class ProfileManager(QObject):
    """Use Qt signals for loose coupling."""

    profile_loaded = Signal(str)  # profile_name
    rois_changed = Signal()
    profile_save_failed = Signal(str)  # error_message
    pitcher_changed = Signal(str)  # pitcher_name

    def __init__(self, ...):
        super().__init__()
        # No callback parameters needed

    def load_profile(self, name: str):
        # ... load logic ...
        self.profile_loaded.emit(name)
        self.rois_changed.emit()

# main_window.py
self._profile_manager.profile_loaded.connect(self._on_profile_loaded)
self._profile_manager.rois_changed.connect(self._load_rois)
```

**Benefits**:
- ✅ Standard Qt pattern
- ✅ Multiple listeners possible
- ✅ Easier testing (spy on signals)
- ✅ Better separation

**Effort**: Medium (2-3 hours)

---

### 6. Duplication in load_profile()

**Issue**: Repeated code for finding combo box items by serial.

**Current Code** (profile_manager.py:117-135):
```python
if left:
    for i in range(self._left_input.count()):
        if self._left_input.itemData(i) == left:
            self._left_input.setCurrentIndex(i)
            break
    else:
        self._left_input.setCurrentText(left)

if right:
    for i in range(self._right_input.count()):
        if self._right_input.itemData(i) == right:
            self._right_input.setCurrentIndex(i)
            break
    else:
        self._right_input.setCurrentText(right)
```

**Recommended Solution**:
```python
def _set_combo_by_data(self, combo: QtWidgets.QComboBox, value: str) -> bool:
    """Set combo box selection by item data.

    Args:
        combo: Combo box widget
        value: Value to match against itemData

    Returns:
        True if item found and set, False otherwise
    """
    if not value:
        return False

    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return True

    # Fallback: try setting text directly (for legacy profiles)
    combo.setCurrentText(value)
    return False

def load_profile(self, parent: QtWidgets.QWidget) -> None:
    # ...
    self._set_combo_by_data(self._left_input, left)
    self._set_combo_by_data(self._right_input, right)
```

**Benefits**:
- ✅ DRY principle
- ✅ Easier to maintain
- ✅ Reusable

**Effort**: Low (30 minutes)

---

## 🟢 Low Priority (Nice to Have)

### 7. Documentation: Missing Examples

**Issue**: API documentation lacks usage examples.

**Current Code** (profile_manager.py:97):
```python
def load_profile(self, parent: QtWidgets.QWidget) -> None:
    """Load selected location profile.

    Args:
        parent: Parent widget for message boxes
    """
```

**Recommended Improvement**:
```python
def load_profile(self, parent: QtWidgets.QWidget) -> bool:
    """Load selected location profile.

    Reads the currently selected profile from the profile combo box,
    loads its configuration, and applies camera serials and ROI settings.

    Args:
        parent: Parent widget for displaying error message boxes

    Returns:
        True if profile loaded successfully, False otherwise

    Raises:
        No exceptions raised (errors shown to user via message box)

    Example:
        >>> # User selects "Backyard Field" from combo
        >>> success = manager.load_profile(main_window)
        >>> if success:
        >>>     print(f"Loaded: {manager.location_profile}")
        >>>     # Camera serials updated, ROIs applied

    Note:
        Emits profile_loaded signal on success (if using signal version).
    """
```

**Benefits**:
- ✅ Easier for new developers
- ✅ Clearer API contracts
- ✅ Better IDE autocomplete

**Effort**: Low (15 min per method)

---

### 8. Type Hints: Incomplete Coverage

**Issue**: Some methods missing return type hints.

**Examples**:
```python
def refresh_profiles(self) -> None:  # ✅ Good
def add_pitcher(self) -> None:       # ✅ Good
def apply_startup_selection(self, profile_name: Optional[str], pitcher: Optional[str]) -> None:  # ✅ Good
```

All methods have type hints! ✅ **No action needed.**

---

### 9. Magic Strings

**Issue**: Hardcoded strings scattered throughout code.

**Examples**:
```python
# profile_manager.py:110
QtWidgets.QMessageBox.warning(parent, "Load Profile", str(exc))

# profile_manager.py:162
QtWidgets.QMessageBox.information(parent, "Save Profile", "Enter a profile name.")
```

**Recommended Solution**:
```python
# ui/constants.py (NEW)
class DialogTitles:
    LOAD_PROFILE = "Load Profile"
    SAVE_PROFILE = "Save Profile"
    ADD_PITCHER = "Add Pitcher"

class Messages:
    PROFILE_NAME_REQUIRED = "Enter a profile name."
    DEVICE_REQUIRED = "Select at least one device before saving."
    PROFILE_LOAD_ERROR = "Failed to load profile: {error}"

# profile_manager.py
from ui.constants import DialogTitles, Messages

QtWidgets.QMessageBox.information(
    parent,
    DialogTitles.SAVE_PROFILE,
    Messages.PROFILE_NAME_REQUIRED
)
```

**Benefits**:
- ✅ Easier localization (i18n)
- ✅ Consistent messaging
- ✅ Easier to update

**Effort**: Low (1-2 hours)

---

### 10. Logging: Inconsistent Coverage

**Issue**: ProfileManager has no logging at all.

**Recommended Addition**:
```python
from log_config.logger import get_logger

logger = get_logger(__name__)

class ProfileManager:
    def load_profile(self, parent: QtWidgets.QWidget) -> bool:
        name = self._profile_combo.currentText().strip()
        logger.info(f"Loading profile: {name}")

        try:
            profile = load_profile(name)
            logger.debug(f"Profile data: left={profile.get('left_serial')}, right={profile.get('right_serial')}")
        except Exception as exc:
            logger.error(f"Failed to load profile '{name}': {exc}", exc_info=True)
            # ...

        logger.info(f"Successfully loaded profile '{name}'")
        return True
```

**Benefits**:
- ✅ Debugging production issues
- ✅ Audit trail
- ✅ Performance monitoring

**Effort**: Low (30 minutes)

---

## 📊 Architecture Recommendations

### 11. Consider MVC/MVP Pattern

**Current**: Controllers manipulate widgets directly
**Recommended**: Full MVC separation

```
Model (Pure Python)          View (Qt Widgets)         Controller (Glue)
├── ProfileData              ├── QComboBox             ├── ProfileController
├── PitcherData              ├── QLineEdit             │   - updateView()
└── ConfigData               └── QLabel                │   - handleUserInput()
                                                       └── bind()
```

**Benefits**: Easier testing, better separation, reusable components

**Effort**: High (requires architecture redesign)

---

### 12. Introduce Domain Events

**Pattern**: Event sourcing for state changes

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ProfileLoadedEvent:
    profile_name: str
    timestamp: datetime
    user: str

@dataclass
class PitcherSelectedEvent:
    pitcher_name: str
    timestamp: datetime

class EventBus:
    def publish(self, event):
        """Publish event to all subscribers."""
        for handler in self._handlers[type(event)]:
            handler(event)

# Usage
event_bus.publish(ProfileLoadedEvent(
    profile_name=name,
    timestamp=datetime.now(),
    user=os.getlogin()
))
```

**Benefits**: Audit log, undo/redo, replay, analytics

**Effort**: High (requires framework)

---

## 🧪 Testing Improvements

### 13. Add Property-Based Tests

**Current**: Example-based tests only
**Recommended**: Add hypothesis tests

```python
from hypothesis import given, strategies as st

@given(
    name=st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters="/\\:*?\"<>|")),
    left_serial=st.text(min_size=0, max_size=50),
    right_serial=st.text(min_size=0, max_size=50)
)
def test_save_profile_with_random_inputs(name, left_serial, right_serial):
    """Test profile saving with generated inputs."""
    # Property: Any valid name should be saveable
    # Property: Saved profile should be loadable
```

**Benefits**: Finds edge cases, better coverage

**Effort**: Medium (2-3 hours)

---

### 14. Integration Tests for Refactored Controllers

**Missing**: End-to-end tests with real ProfileManager

```python
# tests/integration/test_profile_workflow.py (NEW)
class TestProfileWorkflow:
    def test_create_and_load_profile(self, qtbot):
        """Test complete profile creation and loading workflow."""
        # 1. Create profile with cameras
        # 2. Save profile
        # 3. Clear UI
        # 4. Load profile
        # 5. Verify cameras restored

    def test_profile_with_rois(self, qtbot, tmp_path):
        """Test profile includes ROI configuration."""
```

**Effort**: Medium (2-3 hours)

---

## 🔧 Performance Improvements

### 15. Cache Profile List

**Issue**: `list_profiles()` reads filesystem every time.

**Recommended**:
```python
class ProfileManager:
    def __init__(self, ...):
        self._profile_cache: Optional[list[str]] = None
        self._cache_timestamp: Optional[float] = None

    def refresh_profiles(self, force: bool = False) -> None:
        """Refresh profiles with optional caching."""
        now = time.time()
        if not force and self._profile_cache and (now - self._cache_timestamp < 5.0):
            # Use cached list if < 5 seconds old
            self._profile_combo.clear()
            self._profile_combo.addItems(self._profile_cache)
            return

        # Fetch fresh list
        self._profile_cache = list_profiles()
        self._cache_timestamp = now
        self._profile_combo.clear()
        self._profile_combo.addItems(self._profile_cache)
```

**Benefits**: Faster UI updates, less I/O

**Effort**: Low (1 hour)

---

## 📋 Summary: Prioritized Action Items

### Immediate (This Week)
1. ✅ **Add logging to ProfileManager** (30 min)
2. ✅ **Fix error handling** - specific exceptions (1-2 hrs)
3. ✅ **Add input validation** (1 hr)

### Short Term (Next 2 Weeks)
4. ✅ **Refactor to remove UI coupling** (2-3 hrs)
5. ✅ **Add unit tests for ProfileManager** (3-4 hrs)
6. ✅ **Extract helper method for combo box** (30 min)

### Medium Term (Next Month)
7. ✅ **Convert callbacks to Qt signals** (2-3 hrs)
8. ✅ **Add integration tests** (2-3 hrs)
9. ✅ **Create constants file for strings** (1-2 hrs)

### Long Term (Future)
10. Consider MVC refactoring
11. Add event sourcing
12. Property-based testing

---

## ✅ What's Already Great

1. **Excellent documentation** - DETECTION_ALGORITHMS.md, TRAJECTORY_PHYSICS.md, KEYBOARD_SHORTCUTS.md
2. **Comprehensive refactoring plan** - MAINWINDOW_REFACTORING_PLAN.md is thorough
3. **Good test coverage for workflows** - test_ui_workflows.py covers critical paths
4. **Clean git history** - Well-organized commits with clear messages
5. **Type hints** - Consistent use of Optional, Path, etc.
6. **Separation started** - ProfileManager extraction is the right approach

---

**Overall Assessment**: 8/10 - Strong foundation, needs refinement in error handling and testing.
