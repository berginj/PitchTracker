# PitchTracker UX Modernization Plan

**Document Type:** UX Improvement Roadmap
**Date:** March 26, 2026
**Status:** ACTIONABLE - Ready for Implementation
**Owner:** Product + Engineering (UX Focus)

---

## Executive Summary

**Your instinct is correct.** The codebase analysis reveals:

✅ **GOOD NEWS:** You have an excellent theme foundation (GlassTheme, StyleManager, dialog helpers)
⚠️ **PROBLEM:** It's **inconsistently applied** - old dialogs don't use it, some code bypasses the system
🎯 **SOLUTION:** 2-tier plan: Quick wins (2-3 hours) + Strategic improvements (1-2 weeks)

**Current UX State:**
- **Modern code:** SessionDashboard, CoachWindow, ReviewWindow, SessionStartDialog (uses theme system ✅)
- **Legacy code:** ChecklistDialog, StartupDialog, StatsPanelWidget (raw Qt, bypasses theme ❌)
- **Biggest friction:** Calibration (15-20 minutes, manual, complex)

**Modernization Impact:**
- Quick wins: **Immediate visual consistency** (2-3 hours work)
- Strategic: **30-50% setup time reduction** (1-2 weeks work)
- Aligns with capability contract: "Friction Reduction" = 20% of scoring weight

---

## Current State Assessment

### What's Working Well ✅

**1. Theme System is Modern and Well-Designed**
- `ui/themes/glass_theme.py`: Modern color palette, semantic tokens, spacing system
- `ui/themes/style_manager.py`: Centralized styling, property-driven, singleton pattern
- `ui/themes/dialog_helpers.py`: Standardized patterns (headers, buttons, layouts, notices)

**Colors:** Light blue accent (#2563EB), semantic colors (success green, warning amber, error red)
**Typography:** Segoe UI Variable Text, sized variants (pageTitle 22px, sectionTitle 15px, eyebrow 11px)
**Spacing:** Consistent tokens (16px, 24px, 12px margins/gaps)

**2. Recent Code Uses Modern Patterns**
- CoachWindow: Multi-mode UI with mode selector, compact status indicators
- SessionDashboard: Card-based layout, matplotlib charts, heat map visualization
- ReviewWindow: Media player controls, timeline scrubber, dual video displays
- SessionStartDialog: Grouped form fields, standard headers, semantic buttons

### What's Broken/Inconsistent ❌

**1. Old Dialogs Don't Use Theme System**
- `ui/dialogs/checklist_dialog.py`: Raw Qt layouts, no theme
- `ui/dialogs/startup_dialog.py`: Raw Qt layouts, no theme
- Result: Different spacing, colors, fonts from modern dialogs

**2. Inline StyleSheets Bypass Theme**
- `coach_window.py` Line 140: Hardcoded color `#bbdefb` (not in theme palette)
- `comparison_dashboard.py`: Multiple inline styles
- `stats_panel_widget.py`: Manual font sizing (bypasses theme variants)
- Result: Can't change theme without hunting down hardcoded values

**3. Calibration is Complex and Manual**
- Requires: ChArUco board printing, 20-30 images, manual positioning, waiting for computation
- Time: 15-20 minutes
- No visual guidance on coverage ("Did I get enough angles?")
- Errors are technical ("Reprojection error 0.23px" - what does user do?)

**4. Missing Modern UX Patterns**
- No breadcrumb navigation (multi-step wizards)
- No empty states ("No pitchers yet - create your first")
- No skeleton loaders (charts pop in suddenly)
- No toast notifications (quick feedback)
- Limited micro-interactions (buttons static)

---

## 2-Tier Modernization Plan

### TIER 1: Quick Wins (2-3 Hours) - **DO THIS WEEK**

These create immediate visual consistency with minimal effort.

#### Quick Win 1: Migrate Old Dialogs to Theme System (1-2 hours)

**File:** `ui/dialogs/checklist_dialog.py` (45 lines, easy to fix)

**Current (Lines 38-53):**
```python
# Raw Qt layout - no theme
form = QtWidgets.QFormLayout()
form.addRow("Location profile", self._profile)
# ... manual layout
buttons = QtWidgets.QHBoxLayout()
apply_button = QtWidgets.QPushButton("Continue")
```

**Modern (Apply theme system):**
```python
from ui.themes import apply_standard_layout, build_dialog_header, style_dialog_button_box

def _build_ui(self):
    layout = QtWidgets.QVBoxLayout()
    apply_standard_layout(layout)  # ✓ Consistent 24px margins, 16px gaps

    # Add header
    header = build_dialog_header(
        "Pre-Record Checklist",
        "Verify all items before starting recording"
    )
    layout.addWidget(header)

    # ... form content

    # Add button box
    button_box = QtWidgets.QDialogButtonBox()
    button_box.addButton("Continue", QtWidgets.QDialogButtonBox.AcceptRole)
    button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.RejectRole)
    style_dialog_button_box(button_box, primary=True)  # ✓ Semantic styling
    layout.addWidget(button_box)
```

**Impact:** Immediately matches modern dialogs (spacing, colors, button styling)

**Also Apply To:**
- `startup_dialog.py` (same pattern, 10 lines to change)

**Time:** 1-2 hours for both dialogs

---

#### Quick Win 2: Replace Inline Styles with Theme Tokens (30-45 minutes)

**File:** `ui/coaching/coach_window.py` Line 140-142

**Current:**
```python
self._switch_pitcher_btn.setStyleSheet(
    "font-size: 10pt; background-color: #bbdefb; padding: 2px 8px;"
)
```

**Modern:**
```python
# Define in theme as button variant
self._style_manager.style_button(self._switch_pitcher_btn, "compact-info")

# OR use theme colors directly
color = self._style_manager.theme.accent_primary_dim
self._switch_pitcher_btn.setStyleSheet(
    f"font-size: 10pt; background-color: {color}; padding: 2px 8px;"
)
```

**Better:** Add to `glass_theme.py` as a proper button variant:
```python
# In GlassTheme definition
button_variants = {
    # ... existing variants
    "compact": {
        "fontSize": "10pt",
        "padding": "2px 8px",
        "backgroundColor": theme.accent_primary_dim
    }
}
```

**Impact:** Theme-aware, supports mode switching, consistent with system

**Also Fix:**
- `comparison_dashboard.py`: Multiple inline styles
- `stats_panel_widget.py`: Font sizing

**Time:** 30-45 minutes total

---

#### Quick Win 3: Standardize Font Scaling (15-20 minutes)

**File:** `ui/coaching/widgets/stats_panel_widget.py` Lines 39-52

**Current:**
```python
font = title.font()
font.setPointSize(14)
font.setBold(True)
title.setFont(font)

font = speed_label.font()
font.setPointSize(28)
font.setBold(True)
speed_label.setFont(font)
```

**Modern:**
```python
self._style_manager.style_label(title, "sectionTitle")  # 15px bold from theme
self._style_manager.style_label(speed_label, "metricAccent")  # 28px bold from theme
```

**Impact:** Uses theme system, consistent with other metrics displays, easier to maintain

**Time:** 15-20 minutes (search/replace pattern)

---

#### Quick Win 4: Add Missing `polish_form_controls()` Calls (10 minutes)

**Pattern:** At end of any dialog's `_build_ui()` method:

```python
def _build_ui(self):
    layout = QtWidgets.QVBoxLayout()
    apply_standard_layout(layout)

    # ... build form with inputs

    self.setLayout(layout)
    self._style_manager.polish_form_controls(self)  # ✓ Add this line
```

**Impact:** Consistent input styling (height, borders, focus states) across all forms

**Files to Fix:**
- Most setup step dialogs
- Some coaching dialogs

**Time:** 10 minutes (add one line per dialog)

---

### TIER 2: Strategic UX Improvements (1-2 Weeks)

These address the setup friction and modernization gaps.

#### Strategic 1: Simplify Calibration Workflow (3-5 days) ⭐ **HIGHEST IMPACT**

**Problem:** Calibration is the #1 friction point (15-20 minutes, complex, manual)

**Solution: Guided Calibration with Visual Feedback**

**New Flow:**
```
┌────────────────────────────────────────────────────────┐
│  Stereo Calibration - Guided Mode                     │
├────────────────────────────────────────────────────────┤
│                                                        │
│  [✓] Step 1: Board Detected                           │
│  [→] Step 2: Capture Image Pairs (7 of 15)            │
│  [ ] Step 3: Run Calibration                           │
│  [ ] Step 4: Review Results                            │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  CAMERA PREVIEW (800×600)                        │ │
│  │                                                  │ │
│  │  [ChArUco board visible, highlighted in green]  │ │
│  │                                                  │ │
│  │  💡 Move board to different angle               │ │
│  │  Suggested: Tilt board to the right             │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Progress: ████████░░░░░░░ 7/15 image pairs          │
│                                                        │
│  Coverage Status:                                     │
│  ✅ Front view (3 captures)                           │
│  ✅ Left angle (2 captures)                           │
│  ⚠️ Right angle (2 captures - need 1 more)           │
│  ❌ Top angle (0 captures - need 2)                   │
│                                                        │
│  [Auto-Capture] [Manual Capture] [Skip to Advanced]  │
└────────────────────────────────────────────────────────┘
```

**Key Improvements:**
1. **Visual guidance:** Show which angles are covered/needed
2. **Auto-capture mode:** Automatically capture when board in new position (reduces clicks)
3. **Real-time progress:** "7 of 15 pairs captured"
4. **Coverage feedback:** "Need more top-angle views"
5. **Simplified errors:** "Calibration quality: Fair - capture 3 more for better accuracy" (not "RMS error 0.42px")

**Expected Impact:**
- Setup time: 15-20 minutes → **8-12 minutes** (40-50% reduction)
- Success rate: Higher (users understand what's needed)
- Support burden: Lower (fewer "calibration failed" tickets)

**Implementation:**
- Modify `ui/setup/steps/calibration_step.py`
- Add `CalibrationGuide` widget (coverage tracker)
- Add auto-capture logic (detect new board pose, auto-trigger)
- Simplify error messages

**Time:** 3-5 days
**Priority:** ⭐⭐⭐⭐⭐ **CRITICAL** (addresses #1 friction point)

---

#### Strategic 2: Modernize Pitcher Selection (1 day)

**Problem:** Dropdown + "Add New" button is unclear mental model

**Solution: Card-Based Pitcher Selector**

```
┌────────────────────────────────────────────────────────┐
│  Select Pitcher                                        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│  │ John Doe  │  │Sarah Smith│  │ [+ New]   │         │
│  │ Right     │  │ Left      │  │  Pitcher  │         │
│  │ 23 sess.  │  │ 18 sess.  │  │           │         │
│  └───────────┘  └───────────┘  └───────────┘         │
│  [  Select  ]   [  Select  ]   [  Create  ]          │
│                                                        │
│  Recently Used:                                       │
│  • John Doe (2 days ago)                              │
│  • Sarah Smith (1 week ago)                           │
└────────────────────────────────────────────────────────┘
```

**Improvements:**
- Visual cards (click to select)
- Shows pitcher stats (throwing hand, session count)
- Recently used sorting
- Inline "Add New" (no dropdown confusion)

**Impact:** Faster selection, clearer mental model, modern feel

**Implementation:**
- Create `PitcherSelectorWidget` (card grid)
- Replace dropdown in SessionStartDialog
- Wire selection to existing logic

**Time:** 1 day
**Priority:** ⭐⭐⭐ **MEDIUM** (nice improvement, not critical)

---

#### Strategic 3: Add Modern UI Patterns (2-3 days)

**Pattern 1: Empty States (30 minutes)**

**Current:** Lists just show empty
**Modern:** Provide guidance

```
┌────────────────────────────────────────────┐
│  Pitcher Profiles                          │
├────────────────────────────────────────────┤
│                                            │
│         No pitchers saved yet              │
│                                            │
│    📝 Create your first pitcher profile    │
│    to start tracking performance           │
│                                            │
│         [+ Create Pitcher]                 │
│                                            │
└────────────────────────────────────────────┘
```

**Apply to:**
- Pitcher list (when empty)
- Session history (when empty)
- Analytics dashboard (no data yet)

**Time:** 30 minutes

---

**Pattern 2: Skeleton Loaders (1 hour)**

**Current:** Charts pop in suddenly (matplotlib takes 100-200ms to render)
**Modern:** Show skeleton while loading

```
┌────────────────────────────────────────────┐
│  Velocity Over Time                        │
├────────────────────────────────────────────┤
│                                            │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  ← Skeleton
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│                                            │
└────────────────────────────────────────────┘
```

**Implementation:**
```python
def _update_velocity_chart(self, pitches):
    # Show skeleton
    self._show_chart_skeleton()

    # Render in background thread
    QtCore.QTimer.singleShot(0, lambda: self._render_chart(pitches))

def _render_chart(self, pitches):
    # Matplotlib rendering (takes 100-200ms)
    # ...
    # Hide skeleton, show chart
    self._hide_chart_skeleton()
```

**Time:** 1 hour

---

**Pattern 3: Breadcrumb Navigation (1 hour)**

**Current:** Setup wizard shows "Step 2 of 6" but no breadcrumb
**Modern:** Show all steps with visual progress

```
┌────────────────────────────────────────────────────────┐
│  Setup Wizard                                          │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ● Camera ──> ● Calibration ──> ○ ROI ──> ○ Detector │
│  Done         Current         Next       Next         │
│                                                        │
│  [Step 2 of 6: Stereo Calibration]                    │
└────────────────────────────────────────────────────────┘
```

**Implementation:**
- Add `BreadcrumbWidget` to SetupWindow header
- Update on step changes
- Allow click-to-jump (if step completed)

**Time:** 1 hour

---

**Pattern 4: Toast Notifications (30 minutes)**

**Current:** Success messages via status bar (bottom, easy to miss)
**Modern:** Toast notification (top-right, temporary)

```
┌────────────────────────────────┐
│  ✅ Session Started            │
│  Recording in progress...      │
└────────────────────────────────┘
  (Fades out after 3 seconds)
```

**Implementation:**
```python
# ui/themes/toast.py (NEW)
class Toast(QtWidgets.QWidget):
    def __init__(self, message, tone="success", duration=3000):
        # Semi-transparent overlay
        # Auto-position top-right
        # Fade in/out animation
        # Auto-close after duration

def show_toast(parent, message, tone="success"):
    toast = Toast(message, tone)
    toast.show()
```

**Usage:**
```python
# Replace: self._status_bar.showMessage("Session started")
# With: show_toast(self, "Session started", "success")
```

**Time:** 30 minutes to implement, 30 minutes to apply throughout

---

#### Strategic 4: Setup Time Reduction (3-5 days) ⭐ **CRITICAL**

**Addresses capability contract violation:** Setup friction reduction required (30%+ target)

**Current Setup Time:** 60-90 minutes
- ChArUco board: 15-30 minutes (printing, mounting)
- Camera selection: 2-3 minutes
- Intrinsic calibration: 10-15 minutes (manual)
- Extrinsic calibration: 5-10 minutes (manual)
- ROI configuration: 5-10 minutes (manual drawing)
- Strike zone: 2-3 minutes
- Validation: 2 minutes
- **Total: 60-90 minutes**

**Target:** 30-45 minutes (40-50% reduction)

**Automation Opportunities:**

**A. Auto-ROI Suggestion (2 days implementation)**

**Current:** User manually draws ROI rectangles
**Improved:** Auto-detect and suggest ROI bounds

```python
def _suggest_roi_bounds(self, frame):
    """Analyze frame and suggest lane/plate ROI bounds."""
    # Simple edge detection
    edges = cv2.Canny(frame, 50, 150)

    # Find ground plane (bottom 1/3 of frame)
    # Detect lane markings or obvious boundaries
    # Suggest rectangle bounds

    return {
        "lane": {"x": 100, "y": 200, "width": 400, "height": 300},
        "plate": {"x": 250, "y": 350, "width": 100, "height": 150},
        "confidence": 0.85
    }
```

**UI:**
```
┌────────────────────────────────────────────┐
│  ROI Configuration                         │
├────────────────────────────────────────────┤
│                                            │
│  [Camera preview with suggested ROIs]     │
│  (Green boxes show auto-detected regions)  │
│                                            │
│  💡 Suggested ROI detected (85% confidence)│
│                                            │
│  [Accept Suggestion]  [Adjust Manually]   │
└────────────────────────────────────────────┘
```

**Time Saved:** 3-5 minutes (from manual drawing)

---

**B. Strike Zone Presets (30 minutes implementation)**

**Current:** User enters batter height manually (requires measurement)
**Improved:** Common height presets

```python
# In SessionStartDialog
strike_zone_preset = QtWidgets.QComboBox()
strike_zone_preset.addItems([
    "Youth (5'2\" / 157cm)",
    "High School (5'8\" / 173cm)",
    "College (5'10\" / 178cm)",
    "Adult (6'0\" / 183cm)",
    "Custom..."
])
```

**If "Custom" selected:** Show manual height input

**Time Saved:** 1-2 minutes (from measurement step)

---

**C. Calibration Guidance Overlay (1-2 days implementation)**

**Current:** User guesses which board positions are needed
**Improved:** Visual guidance shows where to move board

```
┌────────────────────────────────────────────┐
│  [Camera preview]                          │
│                                            │
│  ┌─────────┐   Board Position Guide:      │
│  │ Board   │   ✅ Front (3 captures)       │
│  │ Here    │   ⚠️ Left (1 capture - need 1 more)
│  └─────────┘   ❌ Right (0 - need 2)       │
│                 ❌ Top (0 - need 2)          │
│                                            │
│  💡 Suggestion: Tilt board to the right    │
│                                            │
│  [Auto-Capture: ON]  Progress: 7/15       │
└────────────────────────────────────────────┘
```

**Features:**
- Coverage tracker (which angles captured)
- Real-time suggestions ("Move board to right angle")
- Auto-capture when new angle detected (reduces clicks)
- Minimum threshold visible (15 captures minimum)

**Time Saved:** 5-10 minutes (fewer retries, faster understanding)

---

**D. One-Click Repeat Setup (1 day)**

**Problem:** Operators who've calibrated once still take 15-20 minutes on recalibration

**Solution: Load Previous Calibration Preset**

```
┌────────────────────────────────────────────┐
│  Quick Setup                               │
├────────────────────────────────────────────┤
│                                            │
│  📋 Previous Setup Found (Mar 20, 2026)    │
│                                            │
│  Cameras: Left (Serial ABC), Right (XYZ)  │
│  Calibration: Valid (RMS 0.18px)           │
│  ROI: Configured                           │
│  Strike Zone: 5'10" batter                 │
│                                            │
│  [Use Previous Setup]  [New Setup]        │
└────────────────────────────────────────────┘
```

**If cameras same + calibration fresh:**
- Skip calibration entirely
- Just verify ROI (1-click)
- Start session in 2-3 minutes

**Time Saved:** 12-15 minutes (for repeat operators)

---

**Combined Impact of All Setup Improvements:**
- First-time setup: 60-90 min → **35-45 minutes** (40-50% reduction) ✅ Meets capability contract target
- Repeat setup: 15-20 min → **2-5 minutes** (75-90% reduction)

**Aligns with:** Capability contract "Friction Reduction" (20% weight) + UX compliance requirement

---

#### Strategic 5: Visual Modernization Pass (2-3 days)

**Polish existing UI with modern touches:**

**A. Add Smooth Transitions (1 day)**

```python
# When switching coaching modes (Broadcast → Progression)
def _on_mode_changed(self, index):
    # Add fade transition
    animation = QtCore.QPropertyAnimation(self._mode_stack, b"opacity")
    animation.setDuration(200)  # 200ms
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.finished.connect(lambda: self._switch_mode(index))
    animation.start()

def _switch_mode(self, index):
    self._mode_stack.setCurrentIndex(index)
    # Fade back in
    # ...
```

**Impact:** Smoother, more polished feel

---

**B. Add Hover States (1 day)**

```python
# In theme system, define hover states
button_hover = {
    "primary": theme.accent_primary_darker,
    "success": theme.accent_success_darker,
    # etc.
}

# Apply in setStyleSheet with :hover pseudo-state
```

**Impact:** Buttons feel more interactive

---

**C. Add Loading States (1 day)**

**Current:** Long operations freeze UI
**Modern:** Show progress

```python
# During session export
progress = QtWidgets.QProgressDialog("Exporting session...", "Cancel", 0, 100)
progress.setWindowModality(QtCore.Qt.WindowModal)
progress.show()

# Update progress as export proceeds
for i, pitch in enumerate(pitches):
    export_pitch(pitch)
    progress.setValue(int(i / len(pitches) * 100))
```

**Impact:** User knows system is working (not frozen)

---

## Prioritized Implementation Plan

### Week 1: Quick Wins (2-3 hours) - **DO THIS WEEK**

**Aligns with: TAG Sports outreach timeline (don't delay partnership)**

| Task | Time | Impact | Files |
|------|------|--------|-------|
| Migrate ChecklistDialog to theme | 1 hour | High visibility | `ui/dialogs/checklist_dialog.py` |
| Migrate StartupDialog to theme | 30 min | Medium visibility | `ui/dialogs/startup_dialog.py` |
| Remove inline styles | 30 min | Consistency | `coach_window.py`, `comparison_dashboard.py` |
| Standardize font scaling | 20 min | Consistency | `stats_panel_widget.py` |
| Add `polish_form_controls()` | 10 min | Input consistency | 5-6 dialogs |

**Result:** Immediate visual consistency across all dialogs

---

### Weeks 2-3: Setup Simplification (1 week) - **CRITICAL**

**Aligns with: Capability contract friction reduction requirement (30%+ target)**

| Task | Time | Time Saved | Priority |
|------|------|-----------|----------|
| Guided calibration (coverage tracker) | 2 days | 5-10 min | ⭐⭐⭐⭐⭐ |
| Auto-ROI suggestion | 2 days | 3-5 min | ⭐⭐⭐⭐⭐ |
| Strike zone presets | 30 min | 1-2 min | ⭐⭐⭐⭐ |
| One-click repeat setup | 1 day | 12-15 min | ⭐⭐⭐⭐ |

**Result:** Setup time 60-90 min → 35-45 min (meets 30%+ reduction target)

---

### Month 2: Visual Modernization (1 week) - **POLISH**

**Aligns with: Post-pilot iteration based on feedback**

| Task | Time | Impact | Priority |
|------|------|--------|----------|
| Modernize pitcher selection (cards) | 1 day | Modern feel | ⭐⭐⭐ |
| Add empty states | 30 min | Guidance | ⭐⭐⭐ |
| Add skeleton loaders | 1 hour | Perceived performance | ⭐⭐ |
| Add breadcrumb navigation | 1 hour | Clarity | ⭐⭐ |
| Add toast notifications | 1 hour | Better feedback | ⭐⭐ |
| Add smooth transitions | 1 day | Polish | ⭐ |
| Add hover states | 1 day | Interactivity | ⭐ |
| Add loading progress | 1 day | Transparency | ⭐⭐ |

**Result:** Modern, polished UI that feels cohesive and professional

---

## Capability Contract Evaluation

### Do UX Improvements Pass Contract?

**Quick Wins (Theme Consistency):**
- ✅ User Value: Improves perceived quality, reduces cognitive load
- ✅ Validation: Easy to validate (does UI look consistent?)
- ✅ Workflow Fit: Neutral (doesn't change workflows, just improves visual)
- ✅ Setup Impact: Positive (better UX during setup)
- ✅ Architecture: Follows existing pattern (use theme system)
- ✅ Supportability: Reduces confusion, easier to support
- ✅ Commercial Relevance: Professional appearance attracts facilities
- ✅ Release Readiness: Low risk, high return

**Score: 85/100** (Strong candidate - Approved)

---

**Setup Simplification:**
- ✅ User Value: Directly reduces #1 friction point
- ✅ Validation: Measurable (time operators from start to session ready)
- ✅ Workflow Fit: Improves pre-session workflow significantly
- ✅ Setup Impact: **REDUCES setup complexity** (30-50% time reduction)
- ✅ Architecture: Service layer (auto-ROI), UI layer (guided calibration)
- ✅ Supportability: Reduces setup-related support tickets
- ✅ Commercial Relevance: Critical for facility adoption
- ✅ Release Readiness: Can be piloted, measured, iterated

**Score: 92/100** (Strong candidate - HIGH PRIORITY)

---

## Immediate Recommendations

### Option A: Quick Wins This Week (Don't Delay TAG Outreach)

**Monday-Tuesday (2-3 hours total):**
1. Migrate old dialogs to theme system (1-2 hours)
2. Remove inline styles (30 min)
3. Standardize font scaling (20 min)
4. Add polish_form_controls() (10 min)

**Result:** Immediate visual consistency, ready to show TAG Sports improved UI

**Don't block TAG outreach** - these are quick, parallel work

---

### Option B: Setup Simplification After TAG MOU (1-2 Weeks)

**Once TAG Sports MOU signed (Week 4-5):**
- Build guided calibration (2-3 days)
- Build auto-ROI suggestion (2 days)
- Add strike zone presets (30 min)
- Add one-click repeat setup (1 day)

**Why wait:**
- TAG partnership discussions take priority (don't delay)
- Pilot feedback will inform which simplifications matter most
- Capability contract requires validation before scaling (pilots provide this)

**But:** Can start design/mockups now, implement after MOU

---

### Option C: Parallel Track (Recommended)

**This Week (Quick Wins):**
- Visual consistency fixes (2-3 hours)
- Shows TAG Sports you care about UX quality
- Low risk, immediate improvement

**Weeks 2-3 (Setup Simplification):**
- Guided calibration + auto-ROI (1 week)
- Addresses critical UX compliance gap (friction reduction)
- Ready for pilot launch (April 2026)

**Month 2 (Polish):**
- Modern patterns (empty states, loaders, breadcrumbs)
- Based on pilot feedback
- Continuous improvement

---

## What I Recommend You Do

### THIS WEEK (Before TAG Outreach):

**Priority 1: Quick Visual Consistency (2-3 hours)**
- Migrate ChecklistDialog to theme system
- Migrate StartupDialog to theme system
- Remove inline styles from coach_window.py
- Standardize font scaling in stats_panel_widget.py

**Why:** Shows TAG Sports you have professional, consistent UI (strengthens partnership credibility)

**When:** Tuesday-Wednesday (parallel with PDF conversion and outreach prep)

---

### NEXT 2 WEEKS (After TAG Outreach Sent):

**Priority 2: Setup Simplification (1 week)**
- Guided calibration with coverage tracker
- Auto-ROI suggestion
- Strike zone presets
- One-click repeat setup

**Why:** Addresses critical UX compliance gap (setup friction = top adoption blocker)

**When:** Week of April 1-7 (while waiting for TAG response)

---

### MONTH 2 (Based on TAG/Pilot Feedback):

**Priority 3: Modern Patterns (1 week)**
- Pitcher card-based selection
- Empty states
- Skeleton loaders
- Breadcrumbs
- Toast notifications

**Why:** Polish based on actual user feedback (don't guess what matters)

**When:** After pilot feedback or TAG partnership progresses

---

## Code Examples for Quick Wins

Want me to:
1. ✅ Create specific code changes for dialog migration?
2. ✅ Show exactly how to remove inline styles?
3. ✅ Generate guided calibration widget code?
4. ✅ Build auto-ROI suggestion algorithm?

**I can provide ready-to-implement code for any of these improvements.**

Which UX improvements do you want to tackle first?
- Quick wins (2-3 hours, this week)?
- Setup simplification (1 week, critical)?
- Or both in parallel?