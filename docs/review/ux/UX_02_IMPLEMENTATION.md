# UX-02: Persistent workspace implementation

**Reviewed:** 2026-10-13. **Status:** implemented and checked in software.
**Scope:** UX-02 in the [workspace plan](../../UX_WORKSPACE_PLAN.md).
The [roadmap](../../ROADMAP.md) owns delivery status.

The default launcher now opens one PySide6 workspace with Live, Sessions,
Players and Setup destinations. Session identity, recording state and explicit
session actions stay visible while the operator browses another page. Existing
page content remains hosted inside the shell; detailed visual changes belong
to subsequent packages. This is a working-tree implementation, not a release.

## Delivered behavior

- One QtPipelineService and Live controller persist across navigation. Pages are
  created once and retained; hiding a page does not close services or restart timers.
- Startup validation checks the environment without probing cameras, for every
  backend. Preparation and guided setup retain explicit camera actions.
- Navigation to Setup is read-only during runtime capture. Opening the wizard
  is an explicit action. SetupWorkflowService rejects edits/acquisition while
  capture owns the rig, and runtime capture reserves the rig before camera I/O.
- Browsed player and historical session/pitch selection are separate from the
  active session. Browsing a player does not change the active pitcher.
- Backend/config arguments and `--setup` still route through the default
  launcher. Settings retains update preferences; rig editing routes to Setup.
- Exit retains validation, update, setup, review and pipeline workers through
  cancellation/drain. Cancelling exit preserves Live timers. Failed pipeline
  shutdown retains the owner and exposes Retry Exit.
- Invalid Live configuration leaves Sessions and Players accessible and gives
  a corrective message. Explicit new preparation reloads saved configuration.
- The updater checks workspace operation admission before installation.

## Public boundaries and instructions

`PipelineOrchestrator.runtime_status()` returns an immutable, nonblocking
RuntimeStatus snapshot. RuntimeStatusEvent carries sequence, correlation and
monotonic timestamp metadata; QtPipelineService bridges it through
`runtime_status_changed`. State is projected from orchestrator facts at lifecycle
boundaries. FinalizedSession is available only after successful recording drain.
Failed operations preserve ownership and publish an actionable failure.

NavigationContext, ReviewSelection and SessionPreparation describe presentation
context. They do not own pipeline state. CoachWindow and ReviewWindow expose
public hosting/action/selection adapters. Setup admission stays in services;
workspace pages do not run camera, detection, calibration or fitting algorithms.

Applicable instructions are the [root specification](../../../AGENTS.md),
[shared UI instructions](../../../ui/AGENTS.md), and the scoped
[coaching](../../../ui/coaching/AGENTS.md),
[review](../../../ui/review/AGENTS.md), [setup](../../../ui/setup/AGENTS.md),
[team](../../../ui/team/AGENTS.md) and [workspace](../../../ui/workspace/AGENTS.md)
instructions. Standalone window wrappers retain their existing close behavior;
the default launcher uses WorkspaceWindow.

## Evidence

The [actual workspace gallery](ux02/index.html) contains 27 captures at
1366x768, 1024x768 and 800x600: all four destinations in Idle and Recording,
plus an explicitly opened guided setup. The [manifest](ux02/manifest.json)
records geometry and source identity. Inputs, roster and frames are synthetic;
configuration is disposable and no camera or recording is started.
Compare the [UX-01 baseline](baseline/index.html) and
[target layouts](workspace.html). Targets describe later presentation work.

Inspection confirmed that shell navigation, status and session actions remain
visible. Live and Sessions retain dense legacy content and deliberate scroll
paths, including horizontal scrolling at smaller sizes. The new shell does not
establish completion of those page redesigns or a measured usability improvement.

Validation used Python 3.14.8, PySide6/Qt 6.10.1 and offscreen Qt with installed
Windows fonts. Test groups overlap; their counts must not be added together.

| Check | Result |
|---|---|
| Final workspace/status, source GUI smoke, launcher, coaching shutdown/metrics/location tests | 45 passed, 1 packaged-build skip |
| Shared UI/theme/import, launcher lifecycle/updater, coaching, guided setup, review and GUI regression group | 103 passed, 1 packaged-build skip |
| Orchestrator lifecycle, simulator integration, Qt bridge and accepted-pitch terminal shutdown | 37 passed |
| Hosted workspace, responsiveness and review regression run | 43 passed |
| Workspace/status on canonical Python 3.13.16 | 23 passed |
| Final setup publication-admission and guided setup regression check | 29 passed |
| Changed-code mypy on Python 3.13 | Passed, 29 source files |
| Changed-code Flake8, public docs, diff whitespace and tracked/new Python file lengths | Passed |

The final focused command was:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest tests/test_workspace_navigation.py tests/test_workspace_runtime_status.py tests/test_gui_smoke.py tests/test_launcher.py tests/test_coaching_shutdown.py tests/test_coach_window_metrics_lifecycle.py tests/test_coaching_strike_zone_mapping.py --basetemp screenshots/pytest-ux02-complete -q -p no:cacheprovider
```

Python 3.14 mypy traversal reports two redundant casts in unchanged
`trajectory/camera_model.py` under the installed Python 3.14 NumPy stubs; the
canonical Python 3.13 changed-code check passes. The suppression-policy scan also
encounters pre-existing vendored pip files in ignored `.codex/doc-cleanup-314/`.
These local conditions remain unresolved; no new suppression was added.
Third-party asyncio deprecation warnings appeared without failing tests.

## Next implementation and manual checks

UX-03 should consolidate the hosted Live controls, dispatch slow session commands
without blocking the GUI, and clarify Preview/Ready/Recording/Paused/Finalizing
progress and recovery. UX-04 then reduces Live density and prioritizes pitch
feedback; UX-05 adds direct completed-session/pitch handoff and review hierarchy.
Player-history filtering and safe active-pitcher attribution remain UX-06.

The completed-session header action currently navigates to Sessions; the operator
still opens the recording through existing review controls. It does not
automatically load the finalized session. Page navigation does not begin offline
research processing.

Windows scaling at 125%, 150% and 200%, keyboard/screen-reader evaluation,
real-rig cancellation/disconnect/retry and packaged/clean-machine smoke remain
operator-run checks. The full repository suite was not rerun for UX-02; focused
and cross-boundary regressions above establish this package's software evidence.
UX-08 retains full journey and regression qualification. Physical accuracy and
release approval remain separate gates.
