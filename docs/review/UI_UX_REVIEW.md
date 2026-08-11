# UI/UX Review

## Method and limits

Qt was exercised with `QT_QPA_PLATFORM=offscreen`, simulator inputs, synthetic session fixtures, and programmatic widget inspection at requested 1920×1080, 1366×768, 1024×768, and 800×600 sizes. Screenshots were temporary and deleted. Accessible names, focus policies, shortcuts, minimum sizes, and theme-token contrast were inspected.

The native Windows computer-control runtime was unavailable. Physical-camera interaction, screen-reader announcements, hands-on navigation feel, installed fonts, and DPI configurations outside the offscreen environment are **Cannot verify**. Qt warned that its font directory was missing and screenshots rendered square glyphs; geometry findings are valid, typography findings are not.

## UI-001 — Coaching window cannot be constructed

- **Finding:** The primary coaching UI raises `AttributeError` during simulator construction.
- **Evidence:** Reproduction: create `QApplication`, then `CoachWindow(backend="sim")`; `tic_tac_toe_game.py:70` calls nonexistent `StyleManager.apply_standard_layout`. The same call appears in all four coaching game widgets.
- **Impact:** The core coaching workflow is unavailable through this entry point.
- **Confidence:** High; deterministic offscreen exception and source trace.
- **Recommendation:** Replace the stale style call with the supported layout API and add an unguarded constructor smoke test.
- **Dependencies:** Style-manager contract decision.
- **Effort:** Small fix; medium verification.
- **Definition of Done:** All four game widgets and `CoachWindow(backend="sim")` construct in CI; a workflow test reaches capture controls without environment opt-in.

## UI-002 — Setup is wider than the tested displays

- **Finding:** The worktree `StereoSetupWindow` has a 1,998-pixel minimum width. The new outer scroll wrapper does not make 1920, 1366, 1024, or 800-pixel windows fit.
- **Evidence:** Reproduction: construct the worktree setup window offscreen and request each target size; Qt forces width 1,998. No useful horizontal scrollbar was visible.
- **Impact:** Setup actions and content can be inaccessible on common laptop displays.
- **Confidence:** High for geometry; manual usability cannot verify.
- **Recommendation:** Make preview panes and step content shrinkable, cap minimum sizes, and test actual viewport geometry.
- **Dependencies:** Worktree camera/setup delta; preview design.
- **Effort:** Medium.
- **Definition of Done:** At 1024×768 every step's primary action is reachable without clipping; 800×600 has an intentional, tested scroll path; no window is forced beyond requested desktop bounds.

## UI-003 — Review and launcher are not responsive

- **Finding:** Review forces 1,764×1,073 and launcher forces 1,012×686.
- **Evidence:** Reproduction: construct each window and request the four target sizes; Qt reports/uses those minima. Review therefore exceeds even 1366×768; launcher exceeds 800×600.
- **Impact:** Review is unusable on many laptop displays and launcher fails the narrow stress case.
- **Confidence:** High for geometry.
- **Recommendation:** Replace fixed/minimum content assumptions with splitters, scroll areas, and compact breakpoints.
- **Dependencies:** Product decision for minimum supported desktop size.
- **Effort:** Medium-large.
- **Definition of Done:** Launcher and review pass automated geometry assertions at the documented minimum resolution; all primary actions are visible or keyboard-reachable.

## UI-004 — Accessible names are incomplete

- **Finding:** Programmatic accessible names are absent from 21 setup buttons, launcher auto-update, review navigation, and recording-settings controls.
- **Evidence:** Widget-tree inspection found missing names on setup persistence/calibration/navigation actions, `Install updates automatically`, `Go to Selected Pitch`, and Browse/Apply/Cancel. One enabled icon/blank review button has `NoFocus`.
- **Impact:** Assistive technology and automation may expose ambiguous or unreachable controls.
- **Confidence:** High for properties; real screen-reader behavior cannot verify.
- **Recommendation:** Add stable accessible names/descriptions and intentional focus policies; test unique names and tab reachability.
- **Dependencies:** None.
- **Effort:** Small-medium.
- **Definition of Done:** Every interactive control has a nonempty, context-specific accessible name; icon-only controls have descriptions; automated tab traversal reaches all primary actions; a manual screen-reader check is recorded.

## UI-005 — Token contrast passes the programmed checks

No contrast defect was demonstrated. Ratios against the dark base were: primary text 17.85:1, secondary 7.58:1, muted 4.76:1, primary 4.51:1, success 4.55:1, warning 4.60:1, error 5.76:1, and white-on-primary 5.17:1. This does not verify rendered fonts, overlays, images, disabled states, or screen-reader behavior.
