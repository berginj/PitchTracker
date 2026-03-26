# PitchTracker UX Normalization - Comprehensive Plan

**Document Type:** Complete UI Consistency & Modernization Strategy
**Date:** March 26, 2026
**Status:** READY FOR EXECUTION
**Scope:** FULL normalization of all 95 UI files
**Owner:** Engineering (UX Focus)

---

## Executive Summary

**Audit Complete:** 95 UI files analyzed

**Current State:**
- ✅ **Compliant:** 44 files (46%) - Fully use theme system
- ⚠️ **Partial:** 30 files (32%) - Mix of theme + custom styling
- ❌ **Non-Compliant:** 21 files (22%) - Bypass theme entirely

**Target State:**
- ✅ **Compliant:** 85+ files (89%)
- ⚠️ **Partial:** 10 files (11%) - Only custom graphics widgets
- ❌ **Non-Compliant:** 0 files (0%)

**Critical Issues:**
1. **7 dialogs** have ZERO theme integration (checklist, startup, 5 settings dialogs)
2. **4 main windows** have partial/inconsistent theme usage
3. **12 widgets** use manual font sizing (bypasses theme variants)
4. **Setup time** still 60-90 minutes (violates friction reduction target)

**This plan provides:**
- 3 normalization approaches (progressive, focused, comprehensive)
- Automated linting/verification tools
- File-by-file migration templates
- Testing strategy for visual regression
- Timeline options (3 days to 4 weeks)

---

## Table of Contents

1. [Complete Audit Results](#1-complete-audit-results)
2. [Normalization Approaches](#2-normalization-approaches)
3. [Migration Templates](#3-migration-templates)
4. [Automated Verification](#4-automated-verification)
5. [Testing Strategy](#5-testing-strategy)
6. [Timeline Options](#6-timeline-options)
7. [Prevention Strategy](#7-prevention-strategy)

---

## 1. Complete Audit Results

### 1.1 Non-Compliant Files (ZERO Theme Usage) - 21 Files

**CRITICAL (7 Dialogs - Must Fix):**

| File | Issues | Lines | Effort |
|------|--------|-------|--------|
| `ui/dialogs/checklist_dialog.py` | No theme imports, raw QTextEdit, manual layout, unstyled buttons | 45 | 1h |
| `ui/dialogs/startup_dialog.py` | No theme imports, QFormLayout no spacing, raw buttons | 53 | 1h |
| `ui/dialogs/recording_settings_dialog.py` | No theme, manual form, unpolished inputs | 87 | 1.5h |
| `ui/dialogs/strike_zone_settings_dialog.py` | No theme, QDoubleSpinBox × 4 unpolished | 88 | 1.5h |
| `ui/dialogs/detector_settings_dialog.py` | No theme, 25+ fields, complex dialog (700×560) | 272 | 3h |
| `ui/dialogs/calibration_guide.py` | No theme, simple QTextEdit dialog | 67 | 45min |
| `ui/dialogs/plate_plane_dialog.py` | No theme, simple form | 78 | 1h |

**Subtotal:** 7 files, **10-12 hours** to migrate

---

**HIGH (4 Main Windows - Partial Theme):**

| File | Issues | Complexity | Effort |
|------|--------|-----------|--------|
| `ui/main_window.py` | Mixed GlassButton + raw QPushButton, inconsistent widget styling | Large (1465 lines) | 4-6h |
| `ui/coaching/coach_window.py` | Imports theme but inline style Line 140, complex UI | Large (938 lines) | 3-4h |
| `ui/review/review_window.py` | Menu bar unstyle

d, custom toolbars | Large (1142 lines) | 3-4h |
| `ui/setup/setup_window.py` | Mixed GlassButton + raw widgets | Medium (300 lines) | 2-3h |

**Subtotal:** 4 files, **12-17 hours** to normalize

---

**MEDIUM (10 Utility/Controller Files):**

Controllers (10 files): ui/controllers/*.py
- Minimal UI (service layer primarily)
- Any UI messaging uses inconsistent error display
- **Effort:** 1-2 hours total (just error messaging standardization)

---

### 1.2 Partial Compliance Files (Mix Theme + Custom) - 30 Files

| Category | Files | Primary Issue | Effort |
|----------|-------|---------------|--------|
| **Analytics** | 2 | Custom matplotlib styling, hardcoded chart colors | 2-3h |
| **Coaching Widgets** | 6 | Manual font sizing (setFont), some inline styles | 3-4h |
| **Game Widgets** | 4 | All use setFont(), custom text rendering | 2-3h |
| **Review Widgets** | 5 | Custom graphics, mixed theme usage | 3-4h |
| **Mode Widgets** | 4 | Broadcast/Progression/Game views, partial theme | 3-4h |
| **Setup Steps** | 3 | Calibration/ROI/Camera have custom graphics | 2-3h |
| **Other** | 6 | Export, qt_app, capture_validator, misc | 2-3h |

**Subtotal:** 30 files, **17-24 hours** to fully normalize

---

### 1.3 Fully Compliant Files (Reference Standard) - 44 Files

**GOLD STANDARD EXAMPLES (Learn From These):**

- `ui/dialogs/session_summary_dialog.py` - Perfect theme usage
- `ui/dialogs/pattern_analysis_dialog.py` - Complete integration
- `ui/dialogs/calibration_wizard_dialog.py` - Proper layout helpers
- `ui/coaching/dialogs/session_start.py` - Best practice reference
- `ui/coaching/dialogs/settings_dialog.py` - Complete theme system
- `ui/update_dialog.py` - Clean, modern implementation

**Pattern to Replicate:**
```python
from ui.themes import (
    get_style_manager,
    apply_standard_layout,
    build_dialog_header,
    style_dialog_button_box,
    show_message_dialog,
)

class MyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)  # ✓ 24px margins, 16px gaps

        header = build_dialog_header("Title", "Description")
        layout.addWidget(header)

        # ... form content with style_input() for all inputs

        button_box = QtWidgets.QDialogButtonBox()
        # Add buttons with semantic roles
        style_dialog_button_box(button_box, primary=True)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)  # ✓ Polish all inputs
```

---

## 2. Normalization Approaches

### Approach A: Progressive Migration (Low Risk, 4 Weeks)

**Week 1: Critical Dialogs (7 files, 10-12 hours)**
- Migrate all non-compliant dialogs
- Most visible to users during setup/session start
- Immediate visual improvement

**Week 2: Main Windows (4 files, 12-17 hours)**
- Normalize main_window, coach_window, review_window, setup_window
- High complexity but high impact

**Week 3: Widgets (20 files, 12-15 hours)**
- Analytics widgets (charts)
- Coaching widgets (games, stats)
- Review widgets (video, timeline)

**Week 4: Testing & Verification (8 hours)**
- Visual regression testing
- Theme switching verification
- Polish remaining edge cases

**Total: 4 weeks, 42-52 hours**

**Pros:**
- ✅ Low risk (incremental changes, test after each week)
- ✅ Can pause/resume anytime
- ✅ Delivers value weekly (each week improves consistency)

**Cons:**
- ⏱️ Slower (4 weeks total)
- ⚠️ UI inconsistent during migration period

---

### Approach B: Focused Sprint (Medium Risk, 1 Week)

**Focus on USER-VISIBLE files only:**

**Days 1-2: Dialogs (7 files, 10-12 hours)**
- All 7 non-compliant dialogs migrated
- Most visible during user workflows

**Days 3-4: Main Windows (4 files, 12-17 hours)**
- Main application windows normalized
- Most screen time spent here

**Day 5: Verification (4 hours)**
- Test all migrated files
- Fix any issues

**Defer: Widgets** (games, charts, graphics) - users see dialogs/windows more

**Total: 1 week, 26-33 hours**

**Pros:**
- ✅ Fast (1 week)
- ✅ Focuses on what users see most
- ✅ Defers less-visible widgets

**Cons:**
- ⚠️ Widgets still inconsistent (but less visible)
- ⚠️ Intensive (26-33 hours in 1 week)

---

### Approach C: Comprehensive Blitz (Higher Risk, 2 Weeks)

**Week 1: All Non-Compliant + Partial (37 files, 39-53 hours)**
- Day 1-2: Dialogs (7 files, 10-12h)
- Day 3-4: Main windows (4 files, 12-17h)
- Day 5: Partial files batch 1 (10 files, 6-8h)
- Weekend/overtime: Partial files batch 2 (16 files, 11-16h)

**Week 2: Testing & Verification (8 hours)**
- Comprehensive visual regression testing
- Theme switching (production ↔ setup mode)
- All dialogs, windows, widgets verified
- Fix any issues

**Total: 2 weeks, 47-61 hours**

**Pros:**
- ✅ Complete normalization (100%)
- ✅ Done quickly (2 weeks)
- ✅ No partial state

**Cons:**
- ⚠️ High risk (many simultaneous changes)
- ⚠️ Intensive (47-61 hours)
- ⚠️ Testing burden high (many files to verify)

---

### Approach D: Automated + Manual Hybrid (Best for Long-Term, 3 Weeks)

**Week 1: Build Linting Tools (12 hours)**
- Create automated checkers (see Section 4)
- Find ALL violations automatically
- Generate migration checklists

**Week 2: Manual Migration (24-30 hours)**
- Use linter output to guide migrations
- Fix all critical + high priority files
- Defer low-priority (graphics utilities)

**Week 3: Verification + Prevention (8 hours)**
- Run linters in CI/CD
- Pre-commit hooks prevent future violations
- Document theme system patterns

**Total: 3 weeks, 44-50 hours**

**Pros:**
- ✅ Systematic (linter finds ALL issues)
- ✅ Preventative (linter prevents future drift)
- ✅ Documentable (migration guided by tool output)
- ✅ Maintainable (linter runs on every commit)

**Cons:**
- ⏱️ Slower (3 weeks due to tool building)
- ⚠️ Requires linting infrastructure

---

## 3. Migration Templates

### 3.1 Template for Non-Compliant Dialogs

**Before (ui/dialogs/checklist_dialog.py):**
```python
class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        form = QtWidgets.QFormLayout()  # ❌ No apply_standard_layout
        # ... manual layout
        buttons = QtWidgets.QHBoxLayout()  # ❌ No style_dialog_button_box
        self.setLayout(form)
```

**After (Fully Compliant):**
```python
from ui.themes import (
    get_style_manager,
    apply_standard_layout,
    build_dialog_header,
    style_dialog_button_box,
)

class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        self._style_manager = get_style_manager()  # ✓ Get theme manager
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)  # ✓ Consistent 24px margins, 16px gaps

        # Add themed header
        header = build_dialog_header(
            "Pre-Record Checklist",
            "Verify all items before starting recording"
        )
        layout.addWidget(header)

        # Content (preserve existing logic)
        # ... existing form fields

        # Add themed button box
        button_box = QtWidgets.QDialogButtonBox()
        continue_btn = button_box.addButton("Continue", QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        style_dialog_button_box(button_box, primary=True)  # ✓ Semantic styling
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)  # ✓ Polish all inputs
```

**Changes Required:**
- Line 1: Add theme imports
- Line 8: Add `_style_manager` initialization
- Line 12-14: Replace manual layout with `apply_standard_layout()`
- Line 16-20: Add `build_dialog_header()`
- Line 26-32: Replace manual buttons with `style_dialog_button_box()`
- Line 35: Add `polish_form_controls()`

**Time:** 45-60 minutes per dialog

---

### 3.2 Template for Inline Style Removal

**Before (ui/coaching/coach_window.py Line 140):**
```python
self._switch_pitcher_btn.setStyleSheet(
    "font-size: 10pt; background-color: #bbdefb; padding: 2px 8px;"
)  # ❌ Hardcoded color, bypasses theme
```

**After (Theme-Aware):**

**Option 1: Use existing button variant**
```python
self._style_manager.style_button(self._switch_pitcher_btn, "ghost")
self._switch_pitcher_btn.setMaximumWidth(60)
self._switch_pitcher_btn.setMaximumHeight(24)
# Size constraints OK, but colors come from theme
```

**Option 2: Add new button variant to theme**
```python
# In ui/themes/glass_theme.py, add to button_variants:
"compact-info": {
    "fontSize": "10pt",
    "padding": "2px 8px",
    "backgroundColor": self.accent_primary_dim,  # ✓ Theme token
    "color": self.text_primary,
    "borderRadius": "4px"
}

# Then use:
self._style_manager.style_button(self._switch_pitcher_btn, "compact-info")
```

**Option 3: Use theme colors dynamically**
```python
theme = self._style_manager.theme
self._switch_pitcher_btn.setStyleSheet(f"""
    font-size: 10pt;
    background-color: {theme.accent_primary_dim};  # ✓ Theme token
    color: {theme.text_primary};  # ✓ Theme token
    padding: 2px 8px;
    border-radius: 4px;
""")
```

**Recommendation:** Option 2 (add variant) for reusability

---

### 3.3 Template for Font Standardization

**Before (ui/coaching/widgets/stats_panel_widget.py Lines 39-52):**
```python
font = title.font()
font.setPointSize(14)
font.setBold(True)
title.setFont(font)  # ❌ Manual font sizing

font = speed_label.font()
font.setPointSize(28)
font.setBold(True)
speed_label.setFont(font)  # ❌ Manual font sizing
```

**After (Theme Variants):**
```python
self._style_manager.style_label(title, "sectionTitle")  # ✓ 15px bold from theme
self._style_manager.style_label(speed_label, "metricAccent")  # ✓ 28px bold from theme
```

**Available Label Variants (from glass_theme.py):**
- `pageTitle`: 22px, bold (main page headers)
- `sectionTitle`: 15px, bold (section headers)
- `eyebrow`: 11px, uppercase (overline labels)
- `muted`: 12px, secondary color (hints/captions)
- `accent`: 13px, primary color (emphasis)
- `metric`: 24px, regular (large numbers)
- `metricAccent`: 28px, bold (highlighted metrics)
- `status`: 13px, semantic color (status messages)

**Time:** Search/replace pattern, 5-10 minutes per file

---

### 3.4 Template for Input Polishing

**Before (Any dialog with inputs):**
```python
def _build_ui(self):
    layout = QtWidgets.QVBoxLayout()

    # ... create QLineEdit, QComboBox, QSpinBox widgets
    self.name_input = QtWidgets.QLineEdit()  # ❌ Unpolished
    self.type_combo = QtWidgets.QComboBox()  # ❌ Unpolished

    self.setLayout(layout)
    # Missing polish_form_controls() ❌
```

**After:**
```python
def _build_ui(self):
    layout = QtWidgets.QVBoxLayout()
    apply_standard_layout(layout)  # ✓ Add if missing

    # Create inputs
    self.name_input = QtWidgets.QLineEdit()
    self.type_combo = QtWidgets.QComboBox()

    # Apply individual styling (optional but recommended)
    self._style_manager.style_input(self.name_input)
    self._style_manager.style_input(self.type_combo)

    # ... add to layout

    self.setLayout(layout)
    self._style_manager.polish_form_controls(self)  # ✓ Batch polish all inputs
```

**Impact:** Consistent input heights (36px min), borders, focus states

---

## 4. Automated Verification

### 4.1 Theme Compliance Linter (Build This)

**File:** `tools/theme_linter.py` (NEW)

```python
"""Theme system compliance linter for PitchTracker UI files.

Checks for:
- Missing theme imports
- Inline setStyleSheet() calls
- Manual font operations (setFont, setPointSize)
- Hardcoded colors/spacing
- Missing apply_standard_layout()
- Missing polish_form_controls()
"""

import re
from pathlib import Path
from typing import List, Tuple

class ThemeLinterViolation:
    def __init__(self, file_path, line_num, rule, message):
        self.file_path = file_path
        self.line_num = line_num
        self.rule = rule
        self.message = message

    def __str__(self):
        return f"{self.file_path}:{self.line_num} [{self.rule}] {self.message}"


class ThemeLinter:
    """Linter for theme system compliance."""

    RULES = {
        "THEME_IMPORT": "File should import get_style_manager from ui.themes",
        "INLINE_STYLE": "Avoid inline setStyleSheet() - use theme variants",
        "MANUAL_FONT": "Avoid setFont/setPointSize - use style_label variants",
        "HARDCODED_COLOR": "Avoid hardcoded colors (#RRGGBB) - use theme tokens",
        "MISSING_LAYOUT_HELPER": "Dialog should use apply_standard_layout()",
        "MISSING_POLISH": "Dialog should call polish_form_controls()",
        "RAW_QMESSAGEBOX": "Use show_message_dialog() instead of QMessageBox",
    }

    def lint_file(self, file_path: Path) -> List[ThemeLinterViolation]:
        """Lint a single UI file for theme compliance."""
        violations = []

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            content = ''.join(lines)

        # Check for theme imports
        if "from ui.themes import" not in content and "import ui.themes" not in content:
            if "QtWidgets" in content and "_ui" in content:  # Likely a UI file
                violations.append(ThemeLinterViolation(
                    file_path, 1, "THEME_IMPORT",
                    "Missing theme imports (add: from ui.themes import get_style_manager, ...)"
                ))

        # Check for inline setStyleSheet()
        for i, line in enumerate(lines, 1):
            if ".setStyleSheet(" in line and "ui/themes/" not in str(file_path):
                violations.append(ThemeLinterViolation(
                    file_path, i, "INLINE_STYLE",
                    f"Inline setStyleSheet() call: {line.strip()[:50]}..."
                ))

        # Check for manual font operations
        for i, line in enumerate(lines, 1):
            if re.search(r'\.(setFont|setPointSize|setPixelSize)\(', line):
                violations.append(ThemeLinterViolation(
                    file_path, i, "MANUAL_FONT",
                    f"Manual font operation: {line.strip()[:50]}..."
                ))

        # Check for hardcoded colors
        for i, line in enumerate(lines, 1):
            if re.search(r'#[0-9A-Fa-f]{6}', line) and "ui/themes/" not in str(file_path):
                color = re.search(r'#[0-9A-Fa-f]{6}', line).group()
                violations.append(ThemeLinterViolation(
                    file_path, i, "HARDCODED_COLOR",
                    f"Hardcoded color: {color}"
                ))

        # Check for missing layout helpers (dialogs only)
        if "QDialog" in content and "apply_standard_layout" not in content:
            violations.append(ThemeLinterViolation(
                file_path, 1, "MISSING_LAYOUT_HELPER",
                "Dialog should use apply_standard_layout() for consistent spacing"
            ))

        # Check for missing polish_form_controls
        if ("QLineEdit" in content or "QComboBox" in content or "QSpinBox" in content):
            if "polish_form_controls" not in content:
                violations.append(ThemeLinterViolation(
                    file_path, 1, "MISSING_POLISH",
                    "Dialog with inputs should call polish_form_controls()"
                ))

        # Check for raw QMessageBox
        for i, line in enumerate(lines, 1):
            if "QMessageBox." in line and "show_message_dialog" not in content:
                violations.append(ThemeLinterViolation(
                    file_path, i, "RAW_QMESSAGEBOX",
                    f"Use show_message_dialog() instead: {line.strip()[:50]}..."
                ))

        return violations

    def lint_directory(self, directory: Path) -> dict:
        """Lint all Python files in directory."""
        results = {}

        for file_path in directory.rglob("*.py"):
            if "__pycache__" in str(file_path):
                continue

            violations = self.lint_file(file_path)
            if violations:
                results[file_path] = violations

        return results

    def generate_report(self, results: dict) -> str:
        """Generate human-readable linting report."""
        total_violations = sum(len(v) for v in results.values())
        total_files = len(results)

        report = f"Theme Compliance Lint Report\n"
        report += f"=" * 60 + "\n\n"
        report += f"Total files with violations: {total_files}\n"
        report += f"Total violations: {total_violations}\n\n"

        # Group by rule
        by_rule = {}
        for violations in results.values():
            for v in violations:
                by_rule.setdefault(v.rule, []).append(v)

        report += "Violations by Rule:\n"
        for rule, violations in sorted(by_rule.items(), key=lambda x: -len(x[1])):
            report += f"  {rule}: {len(violations)} violations\n"

        report += "\n" + "=" * 60 + "\n\n"

        # Detailed violations
        for file_path, violations in sorted(results.items()):
            report += f"\n{file_path}:\n"
            for v in violations:
                report += f"  Line {v.line_num}: [{v.rule}] {v.message}\n"

        return report


# Usage
if __name__ == "__main__":
    linter = ThemeLinter()
    results = linter.lint_directory(Path("ui"))
    print(linter.generate_report(results))
```

**Run to find ALL violations:**
```bash
python tools/theme_linter.py > theme_violations_report.txt
```

**Time to Build Linter:** 2-3 hours
**Time to Fix Violations:** Guided by linter output

---

### 4.2 Pre-Commit Hook (Prevent Future Drift)

**File:** `.git/hooks/pre-commit` (or use pre-commit framework)

```bash
#!/bin/bash
# Pre-commit hook: Enforce theme system compliance

echo "Running theme compliance linter..."

python tools/theme_linter.py --strict

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Theme compliance violations detected!"
    echo "   Fix violations or use 'git commit --no-verify' to bypass"
    echo ""
    exit 1
fi

echo "✅ Theme compliance check passed"
```

**Install:**
```bash
chmod +x .git/hooks/pre-commit
```

**Prevents:**
- New code with inline setStyleSheet()
- New code with hardcoded colors
- New code with manual font operations

---

### 4.3 Visual Regression Testing

**File:** `tests/test_ui_theme_consistency.py` (NEW)

```python
"""Visual regression tests for theme system consistency."""

import pytest
from PySide6 import QtWidgets
from ui.dialogs.session_summary_dialog import SessionSummaryDialog
from ui.dialogs.checklist_dialog import ChecklistDialog
# ... import all dialogs

@pytest.fixture
def app(qtbot):
    """Create Qt application for testing."""
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

def test_all_dialogs_use_theme_manager(app, qtbot):
    """Verify all dialog classes have _style_manager attribute."""
    dialog_classes = [
        SessionSummaryDialog,
        ChecklistDialog,
        # ... all dialogs
    ]

    for dialog_class in dialog_classes:
        dialog = dialog_class()
        qtbot.addWidget(dialog)
        assert hasattr(dialog, '_style_manager'), \
            f"{dialog_class.__name__} missing _style_manager attribute"
        dialog.close()

def test_all_dialogs_use_standard_layout(app, qtbot):
    """Verify all dialogs have proper margin/spacing."""
    dialog_classes = [...]  # All dialog classes

    for dialog_class in dialog_classes:
        dialog = dialog_class()
        qtbot.addWidget(dialog)

        layout = dialog.layout()
        assert layout is not None, f"{dialog_class.__name__} has no layout"

        # Check margins (should be 24, 24, 24, 24 from apply_standard_layout)
        margins = layout.contentsMargins()
        assert margins.left() == 24, f"{dialog_class.__name__} left margin {margins.left()} != 24"
        assert margins.right() == 24, f"{dialog_class.__name__} right margin {margins.right()} != 24"
        assert margins.top() == 24, f"{dialog_class.__name__} top margin {margins.top()} != 24"
        assert margins.bottom() == 24, f"{dialog_class.__name__} bottom margin {margins.bottom()} != 24"

        # Check spacing (should be 16 from apply_standard_layout)
        assert layout.spacing() == 16, f"{dialog_class.__name__} spacing {layout.spacing()} != 16"

        dialog.close()

def test_no_hardcoded_colors_in_dialogs():
    """Scan dialog files for hardcoded color values."""
    import re

    ui_files = Path("ui").rglob("*.py")
    violations = []

    for file_path in ui_files:
        if "__pycache__" in str(file_path):
            continue

        with open(file_path, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            # Find hex colors
            if re.search(r'#[0-9A-Fa-f]{6}', line):
                # Allow in themes module
                if "ui/themes/" in str(file_path):
                    continue
                violations.append(f"{file_path}:{i}")

    assert len(violations) == 0, \
        f"Found {len(violations)} hardcoded colors:\n" + "\n".join(violations[:10])
```

**Run tests:**
```bash
pytest tests/test_ui_theme_consistency.py -v
```

**Result:** Automated verification that all dialogs comply

---

## 5. Complete Normalization Strategy

### 5.1 Systematic Audit Checklist

**For each UI file, verify:**

```
THEME SYSTEM INTEGRATION:
□ Imports get_style_manager from ui.themes
□ Initializes self._style_manager = get_style_manager() in __init__
□ Uses theme.* properties for any custom styling
□ No hardcoded colors (#RRGGBB) outside theme module
□ No manual font operations (setFont, setPointSize)
□ No inline setStyleSheet() (except using theme tokens)

LAYOUT CONSISTENCY:
□ Uses apply_standard_layout() for main layout (24px margins, 16px gaps)
□ Dialogs use build_dialog_header() for headers
□ Dialogs use style_dialog_button_box() for button rows
□ No hardcoded margins: setContentsMargins(0,0,0,0) or similar
□ No hardcoded spacing: setSpacing(10) or similar

WIDGET STYLING:
□ All buttons use style_button() with semantic variant
□ All labels use style_label() with semantic variant
□ All inputs use style_input() OR polish_form_controls() at end
□ All panels/cards use style_panel() with variant
□ All messages use show_message_dialog() (not raw QMessageBox)
□ All status indicators use style_status_indicator()

SEMANTIC CORRECTNESS:
□ Primary actions use variant="primary"
□ Destructive actions use variant="danger"
□ Secondary actions use variant="ghost" or "default"
□ Success states use tone="success"
□ Warnings use tone="warning"
□ Errors use tone="error"
```

---

### 5.2 File-by-File Migration Plan

**Priority 1: Critical Dialogs (10-12 hours)**

1. `ui/dialogs/checklist_dialog.py` (1h)
   - Add theme imports
   - Use apply_standard_layout()
   - Use build_dialog_header()
   - Use style_dialog_button_box()
   - Call polish_form_controls()

2. `ui/dialogs/startup_dialog.py` (1h)
   - Same pattern as #1

3. `ui/dialogs/recording_settings_dialog.py` (1.5h)
   - Add theme imports
   - Convert QFormLayout to themed layout
   - Style all QDoubleSpinBox inputs
   - Style browse button
   - Add polish_form_controls()

4. `ui/dialogs/strike_zone_settings_dialog.py` (1.5h)
   - Same pattern as #3
   - 4 QDoubleSpinBox widgets to polish

5. `ui/dialogs/detector_settings_dialog.py` (3h)
   - Complex (272 lines, 25+ fields)
   - Add theme imports
   - Group related fields with build_section_header() or separators
   - Style all 25+ inputs
   - Replace raw button box with style_dialog_button_box()
   - Add polish_form_controls()

6. `ui/dialogs/calibration_guide.py` (45min)
   - Simple dialog, quick migration
   - Add header, style close button

7. `ui/dialogs/plate_plane_dialog.py` (1h)
   - Add theme to form dialog

---

**Priority 2: Main Windows (12-17 hours)**

8. `ui/main_window.py` (4-6h)
   - Large file (1465 lines)
   - Audit all button/widget creation (lines 125-800)
   - Replace raw QPushButton with styled buttons
   - Replace raw QLineEdit/QComboBox with styled inputs
   - Ensure all widgets use semantic variants

9. `ui/coaching/coach_window.py` (3-4h)
   - Remove inline setStyleSheet (Line 140)
   - Audit all UI building
   - Ensure consistent button styling
   - Add missing style_label() calls

10. `ui/review/review_window.py` (3-4h)
    - Style menu bar items
    - Style toolbars
    - Ensure all actions use consistent patterns

11. `ui/setup/setup_window.py` (2-3h)
    - Normalize button usage (mix of GlassButton + raw)
    - Ensure step indicator uses theme

---

**Priority 3: Widgets (17-24 hours)**

12-43. Migrate 30+ partial compliance files:
- Analytics widgets (2-3h)
- Coaching widgets (3-4h)
- Game widgets (2-3h)
- Review widgets (3-4h)
- Mode widgets (3-4h)
- Setup steps (2-3h)
- Other widgets (2-3h)

---

### 5.3 Testing Strategy (Comprehensive)

**Level 1: Automated Linting (5 minutes)**
```bash
python tools/theme_linter.py
# Should report ZERO violations after migration
```

**Level 2: Unit Tests (pytest, 10 minutes)**
```bash
pytest tests/test_ui_theme_consistency.py -v
# All tests should pass
```

**Level 3: Visual Inspection (1-2 hours)**

**Checklist for visual verification:**

□ **Dialog Consistency:**
  - Open each dialog (Session Start, Settings, Calibration, etc.)
  - Verify: Same header style, same spacing, same button layout
  - Verify: Input fields same height (36px), same borders
  - Screenshot each for comparison

□ **Window Consistency:**
  - Launch MainWindow, CoachWindow, ReviewWindow
  - Verify: Menu bars styled consistently
  - Verify: Toolbars styled consistently
  - Verify: Status bars styled consistently

□ **Theme Switching:**
  - Switch theme mode (if applicable: production ↔ setup)
  - Verify: All widgets respond to theme change
  - Verify: No hardcoded colors remain static

□ **Responsive Behavior:**
  - Resize windows from 800×600 to 1920×1080
  - Verify: Layouts adapt properly
  - Verify: No widget clipping or overflow

□ **Button States:**
  - Test enabled/disabled states
  - Verify: Disabled buttons have visual feedback (grayed out)
  - Test hover states (buttons respond to mouse over)
  - Test pressed states (visual feedback on click)

**Level 4: User Acceptance (If Time)**
- Have someone unfamiliar use the app
- Ask: "Do all screens feel like the same application?"
- Note any visual inconsistencies

---

## 6. Timeline Options (Detailed)

### Option A: Quick Blitz (3 Days, Intensive)

**Day 1 (10-12 hours): Dialogs + Main Windows**
- Morning (6h): Migrate all 7 dialogs
- Afternoon (4-6h): Start main windows (main_window.py, coach_window.py)

**Day 2 (10-12 hours): Complete Windows + Start Widgets**
- Morning (4h): Finish review_window.py, setup_window.py
- Afternoon (6-8h): Migrate highest-visibility widgets (stats, analytics)

**Day 3 (6-8 hours): Finish Widgets + Test**
- Morning (4-6h): Remaining widgets
- Afternoon (2-3h): Testing & verification

**Total: 26-32 hours over 3 days**

**Pros:** ✅ Complete in 3 days
**Cons:** ⚠️ Very intensive, high error risk

---

### Option B: Focused Week (5 Days, Sustainable)

**Monday (6-8h): Critical Dialogs**
- Migrate all 7 non-compliant dialogs
- Test each after migration

**Tuesday (6-8h): Main Windows Batch 1**
- main_window.py (4-6h)
- coach_window.py (2-3h)

**Wednesday (6-8h): Main Windows Batch 2 + Widgets**
- review_window.py (3-4h)
- setup_window.py (2-3h)
- Start analytics widgets (1h)

**Thursday (6-8h): Widgets**
- All coaching widgets (4h)
- All review widgets (2-4h)

**Friday (4-6h): Testing & Verification**
- Run linter (should be clean)
- Visual inspection
- Fix any issues

**Total: 28-38 hours over 5 days**

**Pros:** ✅ Sustainable pace, ✅ Daily testing
**Cons:** ⚠️ Full week dedicated to UX

---

### Option C: Part-Time (2 Weeks, 3-4 Hours/Day)

**Week 1:**
- Mon-Tue: Dialogs (7 files, 10-12h)
- Wed-Thu: Main windows (4 files, 12-17h)
- Fri: Testing week 1 work (3h)

**Week 2:**
- Mon-Thu: Widgets (30 files, 17-24h)
- Fri: Final testing & verification (4h)

**Total: 46-60 hours over 2 weeks (3-4 hours/day average)**

**Pros:** ✅ Sustainable, ✅ Can do other work in parallel
**Cons:** ⏱️ 2 weeks timeline

---

### Option D: Hybrid (Best Quality, 2 Weeks)

**Week 1: Build Infrastructure + Critical Files**
- Day 1-2: Build theme linter (3h) + Run audit (1h)
- Day 3-5: Migrate all 7 dialogs + test (10-12h)

**Week 2: Systematic Migration**
- Day 1-3: Main windows (linter-guided, 12-17h)
- Day 4-5: High-priority widgets (linter-guided, 8-10h)

**Total: 34-43 hours over 2 weeks**

**Pros:** ✅ Systematic (linter-guided), ✅ Preventative (linter in CI), ✅ Sustainable
**Cons:** ⏱️ 2 weeks

---

## 7. Ensuring Full Normalization (Verification Strategies)

### Strategy 1: Automated Linting (RECOMMENDED)

**Build the theme linter (Section 4.1):**
- Scans ALL Python files in ui/
- Finds violations automatically
- Generates actionable report

**Run after each batch of migrations:**
```bash
python tools/theme_linter.py --directory ui/dialogs
# Should show decreasing violations
```

**Target:** ZERO violations before considering normalization complete

---

### Strategy 2: Visual Diff Testing

**Capture screenshots before/after migration:**

```python
# tools/screenshot_all_dialogs.py
from PySide6 import QtWidgets
from ui.dialogs import *

def capture_all_dialogs():
    app = QtWidgets.QApplication([])

    dialogs = [
        SessionSummaryDialog(),
        ChecklistDialog(),
        StartupDialog(),
        # ... all dialogs
    ]

    for i, dialog in enumerate(dialogs):
        dialog.show()
        app.processEvents()

        # Capture screenshot
        pixmap = dialog.grab()
        pixmap.save(f"screenshots/dialog_{i:02d}_{dialog.__class__.__name__}.png")

        dialog.close()

if __name__ == "__main__":
    capture_all_dialogs()
```

**Compare:**
- Before migration: screenshots/before/
- After migration: screenshots/after/
- Visual diff: Do all dialogs look consistent?

**Pixelmatch Comparison:**
```python
from PIL import Image, ImageChops

def compare_screenshots(before, after):
    img1 = Image.open(before)
    img2 = Image.open(after)

    diff = ImageChops.difference(img1, img2)
    # Show diff to verify changes are intentional
```

---

### Strategy 3: Checklist-Driven Review

**Create:** `ui_normalization_checklist.xlsx` or Google Sheet

**Columns:**
- File path
- Compliance status (before)
- Issues found
- Migration completed? (Y/N)
- Tested? (Y/N)
- Visual verified? (Y/N)
- Linter clean? (Y/N)
- Compliance status (after)

**Track progress:**
- Start: 21 non-compliant, 30 partial
- Target: 0 non-compliant, <10 partial

**Update after each file migration**

---

### Strategy 4: Pair Programming / Code Review

**For complex files (main_window.py, coach_window.py):**
- Have someone review changes before commit
- Verify: All widgets consistently styled
- Check: No visual regressions
- Confirm: Theme switching still works

**Benefits:**
- Catches errors early
- Ensures quality
- Knowledge transfer

---

## 8. Preventing Future Drift

### Prevention Strategy 1: Pre-Commit Hooks

**Prevent violations from being committed:**

```bash
# .git/hooks/pre-commit
python tools/theme_linter.py --strict --staged-only
```

**Benefits:**
- Catches violations before they reach codebase
- Developer gets immediate feedback
- Maintains 100% compliance

---

### Prevention Strategy 2: Theme System Documentation

**Create:** `docs/UI_THEME_SYSTEM_GUIDE.md`

**Contents:**
```markdown
# UI Theme System - Developer Guide

## Quick Start

All new UI code MUST use the theme system.

### Dialogs

```python
from ui.themes import get_style_manager, apply_standard_layout, build_dialog_header

class MyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        layout.addWidget(build_dialog_header("Title", "Description"))
        # ... content

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)
```

### Buttons

```python
# Primary action (blue)
self._style_manager.style_button(button, "primary")

# Destructive action (red)
self._style_manager.style_button(button, "danger")

# Secondary action (gray)
self._style_manager.style_button(button, "ghost")
```

### Labels

```python
# Page title (22px bold)
self._style_manager.style_label(label, "pageTitle")

# Section title (15px bold)
self._style_manager.style_label(label, "sectionTitle")

# Muted text (12px gray)
self._style_manager.style_label(label, "muted")

# Metric value (28px bold)
self._style_manager.style_label(label, "metricAccent")
```

### DO NOT

❌ setStyleSheet() with hardcoded colors
❌ setFont() or setPointSize()
❌ Manual margins: setContentsMargins(10, 10, 10, 10)
❌ Raw QMessageBox (use show_message_dialog)
❌ Hardcoded color values: "#2196F3"

### Examples

See these files for best practices:
- ui/dialogs/session_summary_dialog.py
- ui/coaching/dialogs/session_start.py
- ui/update_dialog.py
```

**Benefits:**
- New developers follow patterns
- Reduces learning curve
- Self-documenting standards

---

### Prevention Strategy 3: CI/CD Integration

**Add to GitHub Actions / CI pipeline:**

```yaml
# .github/workflows/theme-lint.yml
name: Theme System Compliance

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run theme linter
        run: python tools/theme_linter.py --strict
      - name: Run UI tests
        run: pytest tests/test_ui_theme_consistency.py -v
```

**Benefits:**
- Every commit/PR checked automatically
- Violations caught before merge
- Maintains long-term compliance

---

## 9. Migration Code Templates

### Template 1: Simple Dialog Migration

**File:** `ui/dialogs/checklist_dialog.py`

```python
# BEFORE (Lines 1-45):
class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # ... manual layout

# AFTER (Complete replacement):
from ui.themes import (
    get_style_manager,
    apply_standard_layout,
    build_dialog_header,
    style_dialog_button_box,
)

class ChecklistDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pre-Record Checklist")
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header(
            "Pre-Record Checklist",
            "Verify all items before starting recording"
        )
        layout.addWidget(header)

        # Content - Keep existing text edit
        self._checklist_text = QtWidgets.QTextEdit()
        self._checklist_text.setReadOnly(True)
        self._checklist_text.setProperty("role", "panelMessage")  # Theme-aware role
        self._style_manager.polish(self._checklist_text)
        layout.addWidget(self._checklist_text)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        continue_btn = button_box.addButton("Continue", QtWidgets.QDialogButtonBox.AcceptRole)
        cancel_btn = button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    # Keep existing load_checklist() method unchanged
    def load_checklist(self, items):
        # ... existing logic
```

**Changes:**
- Lines 1-5: Add imports
- Lines 11-12: Add _style_manager init
- Lines 14-39: Replace entire _build_ui() with themed version
- Keep: Existing methods (load_checklist, etc.)

**Time:** 45-60 minutes
**Risk:** Low (simple dialog, clear pattern)

---

### Template 2: Complex Form Dialog Migration

**File:** `ui/dialogs/detector_settings_dialog.py` (272 lines, 25+ fields)

**Strategy:** Don't rewrite - enhance incrementally

```python
# Add at top:
from ui.themes import (
    get_style_manager,
    apply_standard_layout,
    build_dialog_header,
    style_dialog_button_box,
)

# In __init__:
def __init__(self, parent=None):
    super().__init__(parent)
    self._style_manager = get_style_manager()  # ADD THIS
    self._build_ui()

# In _build_ui():
def _build_ui(self):
    layout = QtWidgets.QVBoxLayout()
    apply_standard_layout(layout)  # ADD THIS (replaces setContentsMargins/setSpacing)

    # ADD header
    header = build_dialog_header(
        "Detector Settings",
        "Configure ball detection parameters"
    )
    layout.addWidget(header)

    # Keep existing form building logic
    # ... (don't rewrite all 25 fields)

    # At end, REPLACE button creation:
    button_box = QtWidgets.QDialogButtonBox()
    ok_btn = button_box.addButton("OK", QtWidgets.QDialogButtonBox.AcceptRole)
    cancel_btn = button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
    style_dialog_button_box(button_box, primary=True)  # ADD THIS
    button_box.accepted.connect(self.accept)
    button_box.rejected.connect(self.reject)
    layout.addWidget(button_box)

    self.setLayout(layout)
    self._style_manager.polish_form_controls(self)  # ADD THIS (styles all 25 inputs at once)
```

**Changes:**
- Add imports (5 lines)
- Add _style_manager (1 line)
- Add header (4 lines)
- Replace button box (7 lines)
- Add polish_form_controls (1 line)

**Total additions: ~20 lines**
**Time:** 2-3 hours (complex dialog, but incremental approach)

---

### Template 3: Inline Style Removal

**File:** `ui/coaching/coach_window.py` Line 140-142

```python
# BEFORE:
self._switch_pitcher_btn.setStyleSheet(
    "font-size: 10pt; background-color: #bbdefb; padding: 2px 8px;"
)

# AFTER - Option 1 (Add to theme):
# In ui/themes/glass_theme.py, add button variant:
button_variants = {
    # ... existing
    "compact-info": ButtonStyle(
        backgroundColor=theme.accent_primary_dim,
        color=theme.text_primary,
        fontSize="10pt",
        padding="2px 8px",
        borderRadius="4px",
        border=f"1px solid {theme.border_glass}"
    )
}

# Then use:
self._style_manager.style_button(self._switch_pitcher_btn, "compact-info")

# AFTER - Option 2 (Use theme tokens):
theme = self._style_manager.theme
self._switch_pitcher_btn.setStyleSheet(f"""
    QPushButton {{
        font-size: 10pt;
        background-color: {theme.accent_primary_dim};
        color: {theme.text_primary};
        padding: 2px 8px;
        border-radius: 4px;
        border: 1px solid {theme.border_glass};
    }}
    QPushButton:hover {{
        background-color: {theme.accent_primary};
    }}
    QPushButton:pressed {{
        background-color: {theme.accent_primary_darker};
    }}
""")
```

**Recommendation:** Option 1 if style is reusable, Option 2 if unique to this widget

---

### Template 4: Font Standardization

**File:** `ui/coaching/widgets/stats_panel_widget.py` Lines 39-52

```python
# BEFORE (Manual font sizing):
font = title.font()
font.setPointSize(14)
font.setBold(True)
title.setFont(font)

font = speed_label.font()
font.setPointSize(28)
font.setBold(True)
speed_label.setFont(font)

# AFTER (Theme variants):
self._style_manager.style_label(title, "sectionTitle")  # 15px bold
self._style_manager.style_label(speed_label, "metricAccent")  # 28px bold
```

**Changes:**
- Remove 8 lines of manual font operations
- Add 2 lines using theme variants

**Time:** 2-5 minutes per occurrence

**Find all occurrences:**
```bash
grep -r "setFont\|setPointSize" ui/ --include="*.py" | grep -v "__pycache__"
# Manually review each and replace with theme variant
```

---

## 10. Recommended Execution Plan

### My Strong Recommendation: **Approach D (Hybrid)**

**Why:**
1. **Systematic:** Linter finds ALL violations (nothing missed)
2. **Preventative:** Linter in CI prevents future drift
3. **Documentable:** Clear audit trail
4. **Sustainable:** 2 weeks, 3-4 hours/day
5. **High quality:** Linter-guided, tested, verified

### Week 1: Foundation + Critical (15-17 hours)

**Monday (3-4 hours):**
- Build theme linter tool (3h)
- Run full audit, generate report (30min)
- Review report, prioritize files (30min)

**Tuesday (4-5 hours):**
- Migrate checklist_dialog.py (1h)
- Migrate startup_dialog.py (1h)
- Migrate recording_settings_dialog.py (1.5h)
- Test (30min)

**Wednesday (4-5 hours):**
- Migrate strike_zone_settings_dialog.py (1.5h)
- Migrate detector_settings_dialog.py (3h)
- Test (30min)

**Thursday (2-3 hours):**
- Migrate calibration_guide.py (45min)
- Migrate plate_plane_dialog.py (1h)
- Run linter on dialogs/ (should be clean) (15min)
- Visual inspection of all 7 dialogs (1h)

**Friday (2 hours):**
- Fix any issues from testing
- Commit week 1 work
- Prepare week 2 plan

**Week 1 Total: 15-19 hours**
**Result:** All 7 critical dialogs normalized ✅

---

### Week 2: Main Windows + High-Priority Widgets (19-24 hours)

**Monday (6-7 hours):**
- Migrate main_window.py (4-6h)
- Test (1h)

**Tuesday (3-4 hours):**
- Migrate coach_window.py (3-4h)

**Wednesday (3-4 hours):**
- Migrate review_window.py (3-4h)

**Thursday (3-4 hours):**
- Migrate setup_window.py (2-3h)
- Start analytics widgets (1h)

**Friday (4-5 hours):**
- Finish analytics widgets (1h)
- Migrate game widgets (2-3h)
- Run linter (should show <10 violations remaining)
- Visual inspection
- Commit week 2 work

**Week 2 Total: 19-24 hours**
**Result:** Main windows + analytics normalized ✅

---

### Week 3 (Optional): Remaining Widgets (12-16 hours)

**Only if pursuing 100% compliance:**
- Review widgets (4h)
- Coaching widgets (3h)
- Mode widgets (3h)
- Setup step custom graphics (2h)
- Final testing (2h)
- Documentation update (2h)

**Week 3 Total: 16 hours**
**Result:** 95%+ files normalized ✅

---

## 11. Options for You to Choose

### Question 1: Timeline

**How much time can you dedicate?**

**Option A:** 3-4 hours/day for 2 weeks (Recommended: Approach D)
**Option B:** Full days for 1 week (Approach B - Focused Week)
**Option C:** Intensive 3 days (Approach A - Quick Blitz)

---

### Question 2: Scope

**How complete do you want normalization?**

**Option A:** Critical only (7 dialogs + 4 windows = 22-29 hours)
- Addresses most visible issues
- Defers widget normalization

**Option B:** Critical + High Priority (11 files + 10 widgets = 34-43 hours)
- Normalizes what users see most
- Defers less-visible widgets

**Option C:** Everything (95 files = 47-61 hours)
- 100% normalization
- Zero technical debt
- Perfect consistency

---

### Question 3: Tooling

**Do you want to build automated linting?**

**Option A:** Yes - Build linter first (adds 3-4 hours upfront, saves time later)
- Systematic
- Prevents future drift
- CI/CD integration

**Option B:** No - Manual migration with checklist (faster start, manual verification)
- Start immediately
- Lower overhead
- Less preventative

---

### Question 4: TAG Sports Timeline

**How does UX work fit with TAG outreach?**

**Option A:** UX first, TAG later (2 weeks UX → then TAG outreach)
- Pros: Better screenshots, more polished for partnership
- Cons: 2-week delay on TAG outreach

**Option B:** TAG outreach this week, UX next week (Recommended)
- Pros: Don't delay partnership opportunity
- Cons: TAG sees current UI (still functional, just inconsistent)

**Option C:** Parallel (TAG outreach + UX quick wins simultaneously)
- Pros: Both progress at once
- Cons: More work in single week

---

## 12. My Specific Recommendation

### **Hybrid Parallel Approach**

**THIS WEEK (TAG Outreach Primary):**

**Monday-Tuesday: Quick UX Wins (4-6 hours)**
- Migrate 3 most-visible dialogs:
  - checklist_dialog.py (session start workflow)
  - startup_dialog.py (first-run experience)
  - detector_settings_dialog.py (setup workflow)
- Remove inline style from coach_window.py Line 140
- **Result:** Most visible UX cleaned up

**Wednesday-Friday: TAG Outreach**
- Convert PDFs
- Send partnership package
- (UX improvements done, can include in screenshots)

---

**NEXT WEEK (UX Normalization Primary):**

**Week of April 1-7: Comprehensive Normalization**
- Build linter tool (Monday, 3h)
- Migrate remaining 4 dialogs (Tuesday, 4h)
- Migrate 4 main windows (Wed-Thu, 12-17h)
- Test & verify (Friday, 4h)
- **Result:** All critical files normalized

---

**MONTH 2 (Widgets + Prevention):**
- Migrate widgets (ongoing, 2-3 hours/week)
- Add pre-commit hooks
- CI/CD integration
- Document theme system

---

## 13. Rollback & Risk Management

### Risk: UI Breaks During Migration

**Mitigation:**
- **Git branch:** Create `feature/ui-normalization` branch
- **Test after each file:** Don't batch commit
- **Keep backups:** Tag before starting (`git tag ui-normalization-start`)

**Rollback plan:**
```bash
# If issues occur:
git checkout main
git branch -D feature/ui-normalization
# Start over or fix specific file
```

---

### Risk: Visual Regressions

**Mitigation:**
- Screenshot before/after for each dialog
- Side-by-side comparison
- Test theme switching (production ↔ setup mode)
- Get second pair of eyes (code review)

**Verification:**
```python
# Before migration
python tools/screenshot_all_dialogs.py --output screenshots/before/

# After migration
python tools/screenshot_all_dialogs.py --output screenshots/after/

# Compare
python tools/compare_screenshots.py screenshots/before/ screenshots/after/
```

---

### Risk: Functionality Breaks

**Mitigation:**
- **Keep business logic unchanged** (only change styling/layout)
- **Test functional workflows** after migration:
  - Can start session? ✓
  - Can record? ✓
  - Can review? ✓
  - Can export? ✓
- **Run automated tests:** `pytest` (794 existing tests should still pass)

**If tests fail:**
- Revert specific file
- Fix issue
- Migrate again

---

## 14. Success Criteria

### Normalization Complete When:

**Automated Checks:**
- [ ] Theme linter reports ZERO violations
- [ ] UI consistency tests pass (pytest)
- [ ] All manual font operations removed (grep returns empty)
- [ ] All inline setStyleSheet() removed (grep shows only theme module)
- [ ] All hardcoded colors removed (grep shows only theme module)

**Visual Checks:**
- [ ] All dialogs have identical spacing (24px margins, 16px gaps)
- [ ] All dialogs have consistent header style
- [ ] All buttons use semantic variants (primary/danger/ghost)
- [ ] All labels use theme typography (no manual sizing)
- [ ] Theme switching works (all widgets respond)

**Functional Checks:**
- [ ] All workflows still work (session start, recording, review, export)
- [ ] No visual regressions (screenshots match or improve)
- [ ] All automated tests pass (pytest)

**Documentation:**
- [ ] Theme system guide created (prevents future drift)
- [ ] Migration completed, documented in changelog
- [ ] Pre-commit hooks installed (enforces compliance)

---

## 15. What Do You Want to Do?

**I can help you execute any of these approaches. What's your preference?**

### **Option 1: Quick Wins This Week (4-6 hours)**
- Migrate 3 most-visible dialogs
- Fix inline styles
- Good enough for TAG Sports outreach
- **When:** Monday-Tuesday (parallel with TAG prep)

### **Option 2: Comprehensive 2-Week Sprint (34-43 hours)**
- Build linter (Week 1)
- Migrate all critical files (Week 1-2)
- Full normalization
- **When:** Starting Monday, complete by April 7

### **Option 3: Focused 1-Week Sprint (26-33 hours)**
- All dialogs + main windows
- Defer widgets to later
- **When:** Starting Monday, complete by April 1

---

**Which approach aligns with your timeline and priorities?**

**Or should I:**
1. Start building the theme linter now (so you can run it tonight)?
2. Provide exact code changes for the 7 critical dialogs (copy/paste ready)?
3. Create a visual mockup showing before/after UI consistency?

Let me know how you want to proceed with full normalization!