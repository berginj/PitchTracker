# UX-07: Analytics and secondary surfaces

**Reviewed:** 2026-10-14. **Scope:** UX-07 in the
[workspace plan](../../UX_WORKSPACE_PLAN.md). [Roadmap](../../ROADMAP.md)
owns delivery status. Software and synthetic evidence are complete; UX-08
retains manual display/accessibility and complete journey qualification.

## Delivered behavior

- Session analytics presents recorded selection, speed source/reference, status
  counts, speed/call/location denominators and every rejected/unavailable row.
  Missing speed is unavailable; missing calls do not become balls. Speed charts
  preserve original pitch numbers and gaps. Incompatible source/reference groups
  have separate labeled series and no combined average/maximum. A Pitch table
  exposes the same values, reasons and provenance without relying on a chart.
- The zone display is a keyboard-readable count table using canonical zero-based
  coordinates: row zero is bottom, column zero is negative x. It does not guess
  one-based coordinates or clamp invalid values into edge cells. Negative and
  positive x do not imply a batter's inside/outside orientation. Movement remains
  unavailable without validation. Analytics no longer invokes heuristic pitch
  classification while loading; the explicit research analysis tool remains.
- Player comparison retains its legacy session aggregation basis and labels the
  missing speed provenance and eligible-call denominator. Empty history has
  unavailable metrics, rather than fabricated zero speed or strike rate. Charts
  have a Table equivalent and explicit unavailable annotations. Strike percentages
  use neutral chart colors without an invented performance threshold. Load failures
  retain the existing comparison and give a recovery message. Add/export/clear
  prerequisites are explained on disabled actions.
- Settings keeps persisted update preferences/About and an explicit rig-setup
  route. Opening it performs no rig command. Help now reads maintained local
  Markdown, starts on a relevant topic and follows local guide links. Missing
  documentation has a recoverable topic-selection state. The frozen application
  includes the four primary help guides; references outside that small shipped
  set may require the source documentation and report unavailable when absent.
  The daily-session runbook now uses the five-stage setup and current session controls.
- Summary/export controls stay visible at 800x600 while secondary summary content
  scrolls. Summary speed suppression and provenance agree with Live and analytics;
  unavailable calls remain unclassified. Comparison, detector research and batch
  refit dialogs use shared scrollable bodies with a reachable Close action.
  Worker cancellation/terminal ownership is retained. Timing-trial controls share
  headers, labels and actionable failure presentation.
- Shared controls use theme tokens for input height and visible boundaries.
  Disabled semantic buttons keep a distinct, readable appearance. Buttons and
  labeled research fields have accessible names and keyboard focus; tables and
  text guidance have descriptive labels and visible focus. About terminology
  now matches the workspace. Secondary constructors do not change the shared mode.

## Public contracts and compatibility

Runtime, setup admission, recording, trajectory and durable pitch/session schemas
are unchanged. `SessionDashboard.load_session` keeps its recorded-name/pitch-list
handoff and copies the input list without rewriting summaries. New shared
measurement helpers format existing contracts; they do not estimate measurements.

`PitcherStats` metrics can now be `None` when no eligible aggregate exists.
Comparison CSV preserves the original eight columns in order and **appends**
Aggregation Basis, Speed Source / Reference and Eligible Call Denominator.
Missing metrics export as `Unavailable`. Readers requiring exactly eight columns
must accept the appended columns. Legacy aggregate weights are unchanged;
this work does not recover missing measurement provenance from old summaries.

Applicable instructions: [root](../../../AGENTS.md), [shared UI](../../../ui/AGENTS.md),
[workspace](../../../ui/workspace/AGENTS.md), [analytics](../../../ui/analytics/AGENTS.md),
[themes](../../../ui/themes/AGENTS.md), [coaching](../../../ui/coaching/AGENTS.md)
and [review UI](../../../ui/review/AGENTS.md).

## Evidence

The [actual-widget gallery](ux07/index.html) contains **39 synthetic captures**
at 1366x768, 1024x768 and 800x600. It includes empty/partial analytics, chart/table
and zone views, unavailable comparison history, settings, loaded/missing Help,
recording settings, summary, failed detector opportunities and refit controls.
The [manifest](ux07/manifest.json) records source commit, dirty-worktree status,
state, viewport, button bounds and scroll ranges. All actual sizes match their
requested size and every PNG decoded successfully. Offscreen rendering was
visually inspected for the small analytics, settings, Help, summary, comparison
and failed research views. Content below the viewport remains reachable by
scrolling; the capture harness explicitly reveals failed-report details.

Before evidence is retained in the [UX-01 baseline](baseline/index.html), notably
its analytics and recording-dialog examples. Reproduce current evidence with
`python scripts/capture_secondary_surfaces.py`. It uses disposable configuration,
synthetic summaries and no camera acquisition, worker jobs, upload or private
recording access. Shared helper contrast calculations are 3.61:1 for the control
boundary on white, 7.24:1 for disabled text on the muted surface and 15.59:1 for
zone-count text on the pale surface. These do not prove rendered accessibility.

## Validation and pending checks

All runs used the supported local environments with `QT_QPA_PLATFORM=offscreen`.

- Python 3.13: shared accessibility/theme/import group A, workspace navigation,
  session commands and Live feedback: **83 passed**.
- Python 3.13: secondary surfaces, measurement claim gating, tooling lifecycle,
  workflows and comparison regressions (group F), plus comparison dashboard:
  **60 passed**.
- Python 3.13 and 3.14: secondary surfaces, comparison dashboard and GUI smoke:
  **18 passed, 1 skipped each**. The skip requires `PITCHTRACKER_PACKAGED_DIR`;
  source GUI smoke ran successfully. These groups overlap; do not add the counts.
- Python 3.13: detector comparison admission and timing-trial controls: **19 passed**.
- Repository-wide mypy passed **867 Python files** using an explicit Git source
  list; changed-source Flake8 passed. Public documentation and the 500-line
  convention checks passed. Git whitespace validation accounts for the repository's
  existing CRLF files using `git -c core.whitespace=cr-at-eol diff --check`.

Focused commands (use the supported environment's `python`; the final smoke
command ran under both Python 3.13 and 3.14):

```powershell
python -m pytest tests/test_ui_responsiveness_accessibility.py tests/ui/test_glass_theme.py tests/test_ui_imports.py tests/test_workspace_navigation.py tests/test_workspace_session_commands.py tests/test_live_pitch_experience.py -q --timeout=90
python -m pytest tests/test_secondary_surfaces.py tests/test_measurement_claim_gating.py tests/test_measurement_desktop.py tests/test_ui_workflows.py tests/test_comparison_review_regressions.py tests/ui/test_comparison_dashboard.py -q --timeout=90
python -m pytest tests/test_secondary_surfaces.py tests/ui/test_comparison_dashboard.py tests/test_gui_smoke.py -q --timeout=90
python -m pytest tests/test_comparison_admission.py -q --timeout=90
python scripts/check_public_docs.py
python scripts/check_file_length.py
```

An earlier broader run hit the existing blocked resume-test worker's five-second
wait while screenshot rendering ran concurrently. The complete 83-test group
passed on rerun without concurrent rendering; no lifecycle code or timeout was
weakened. An initial viewport test and capture also caught comparison/summary
height overflow; the final scroll layouts passed the size checks.

Pending: full regression/journey qualification in UX-08; real Windows 125/150/200%
DPI, keyboard-only and screen-reader review; a frozen installer with local Help;
and operator-run hardware setup/recording/recovery. Existing physical accuracy
and release gates remain independent. No manual result or physical approval is
inferred from tests, contrast calculations or synthetic screenshots.
