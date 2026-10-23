# Unified workspace UX action plan

**Last reviewed:** 2026-10-14
**Direction:** unified workspace first, then improve individual experiences.
**Delivery status:** [Roadmap](ROADMAP.md).

This document specifies application work and its acceptance criteria. Creating
the plan and agent instructions does not implement the redesign; the roadmap
and package evidence distinguish delivered work from remaining work. UIAgent owns presentation work;
MaintenanceAgent implements and verifies changes under the
[root agent specification](../AGENTS.md) and [UI instructions](../ui/AGENTS.md).
Other existing agent roles own changes to their service boundaries. These role
assignments do not require separate processes or automatic sub-agent delegation.

## Rationale and evidence

The October 13 source review found competing session/research controls, a large
minimum video pane, separate session-setup and recording actions, technical
panels above the review pitch list, and a review launch without current-session
context. It also found a shared light theme already in place. These findings
support improving hierarchy and continuity before changing the palette.

Source anchors are the active [coaching shell](../ui/coaching/coach_window.py),
[broadcast layout](../ui/coaching/widgets/mode_widgets/broadcast_view.py),
[session controller](../ui/coaching/session_controller.py),
[review shell](../ui/review/review_window.py), and
[theme tokens](../ui/themes/glass_theme_tokens.py).
The initial review did not run the UI, verify clipping, test real displays,
or use competitor hardware. UX-01 establishes the rendered baseline. Historical
UI findings in [the audit](review/UI_UX_REVIEW.md) have their own remediation
status; do not reopen completed fixes without reproducing a new regression.

Official product documentation supplies workflow references, not measurement
parity claims or hands-on usability evidence:

| Reference | Documented pattern | Design implication |
|---|---|---|
| [Rapsodo PRO 2.0](https://rapsodo.com/products/pro-2-ball-flight-monitor) | Basic/advanced displays, setup wizard, immediate video feedback | Make information depth optional and the latest pitch easy to understand. |
| [Trackman B1 software](https://www.trackman.com/baseball/Portable-B1/software) | Customizable dashboard, video alongside metrics, session/player reports | Keep pitch selection, video and measurements connected. |
| [Pocket Radar Smart Coach](https://www.pocketradar.com/pages/sc-signup) | Immediate speed feedback, video with speed, history/export | Prioritize a short, clear feedback loop. |

These references were consulted for the October 13 review. Recheck them before
making new competitive claims; no vendor assets or visual identity are copied.

## Shared target experience

### Workspace and ownership

- One PySide6 workspace provides Live, Sessions, Players and Setup. Settings,
  Help and advanced tools remain secondary. Keep familiar existing capabilities;
  do not introduce cloud sync, a web rewrite, dark mode or new measurement metrics.
- The shell owns navigation and selected-view context, not domain state. Retain
  QtPipelineService/PipelineOrchestrator for runtime work, SetupWorkflowService
  for rig state, and ReviewService for recorded-session access.
- Navigation never implicitly starts/stops cameras or recording. Runtime status
  remains visible on every page, including a direct route back to Live.
- Browsing a historical session/player does not change the active session or
  pitcher. Session/pitch IDs cross screens through narrow public typed interfaces;
  recorded artifacts remain the source for completed-session review.
- Setup is view-only while runtime capture owns the rig. Any acquisition or rig
  change requires explicit operator action and service-level admission. Offline
  analysis retains the existing pause-on-capture rule.
- Preserve `python launcher.py`, `python -m ui.qt_app`, `--setup`, backend/config
  forwarding and GUI smoke behavior. Inspect current parsers before adding routes;
  do not assume unsupported `--coach` or `--review` flags already exist.
- Default launch opens Live without acquiring cameras. Explicit `--setup` opens
  Setup. Invalid rig state supplies a clear Setup action and blocks recording
  through the existing service gate; Sessions remains usable without cameras.

### Session vocabulary and actions

These are presentation states derived from service facts, not a replacement
pipeline state machine. Preserve domain-specific states and structured errors.

| Display state | Meaning | Primary action |
|---|---|---|
| Idle | No camera preview or recording requested | Prepare Session |
| Preview | Cameras are live; required preparation/checks are incomplete | Complete the named prerequisite |
| Ready | Preparation passed; recording has not started | Start Recording |
| Recording | Service confirms recording is active | Pause |
| Paused | Recording paused; preview may remain live | Resume Recording |
| Finalizing | Accepted work is draining and artifacts are closing | Show progress; block duplicate start/end commands |
| Completed | Service confirms finalization succeeded | Review Session |
| Error | An operation failed | Show the failed operation and a supported recovery action |

Error presentation must retain the last confirmed lifecycle state. A stop failure
must not imply recording ended. Starting/resuming commands show pending feedback
until acknowledged. End Session remains an explicit secondary action while
recording/paused; Stop Preview is available when no recording owns capture.
Do not invent a cancel-finalization capability if the service cannot support it.

Changing pages is not shutdown. Closing with active recording offers End Session
and Exit or Cancel; cancellation leaves the session operating. After exit is
requested, show finalization and worker cleanup progress and keep owners alive
until completion. On failure retain the workspace and offer supported recovery.
During setup operations, use the existing cancellation/completion contract before
leaving the busy operation; never orphan a worker or silently cancel by hiding it.

### Presentation defaults

Latest Pitch, Session Trends and Games are the target Live view labels. Give
velocity, location, result and measurement status clear priority, with resizable
video and recent pitches nearby. Units stay adjacent; speed source/reference
remains accessible without hover. Unvalidated movement stays unavailable.

Use existing light-theme tokens, fewer enclosing panels, consistent controls and
strong numeric typography. Operational errors and pitch outcomes use distinct
semantics. Design empty, loading, rejected, unavailable, partial and error states.
Apply the [shared access requirements](../ui/AGENTS.md) across every surface.

## Work-package execution contract

Execute UX-01 through UX-08 in order. A package's focused automated checks and
reviewable deliverables must be complete before the next starts. Carry required
hardware/manual checks as pending evidence; they cannot be marked passed by CI.
UX-08 closes overall journey acceptance only after its required manual checks.

For every package, deliver a handoff containing: objective and affected journey;
changed public interfaces and compatibility impact (or none); focused test
commands/results and skips; synthetic screenshots or diagrams with state,
viewport and commit labels; remaining manual checks; and a roadmap status update.
Store durable UX evidence under `docs/review/ux/` when produced. Do not create
empty evidence reports now or commit recordings, private frames or athlete data.

Run the named test group below plus focused tests for new behavior. Existing
tests are regression starting points, not proof that new acceptance criteria
are covered. Document reasons for replacing obsolete window-specific assertions.
Do not remove lifecycle tests just because the shell changes.

### UX-01: Establish the shared experience specification

Delivered specification, rendered findings, target layouts and interface mapping:
[UX-01 evidence](review/ux/UX_01_SPEC.md). Runtime changes start with UX-02.

**Owner:** UIAgent; MaintenanceAgent verifies evidence. **Prerequisite:** none.
**Boundaries:** launcher, shared themes, representative live/setup/review views.

**Deliverables:** render a synthetic baseline; document target shell and page
layouts, action hierarchy, navigation/context handoffs and service-to-display
state mapping. Use the decisions above; record any implementation constraint
against its affected package before coding the shell.

**Acceptance:**

- Show current and target layouts for Live, Sessions/review, Players and Setup,
  plus a representative dialog and analytics view.
- Include Idle, Ready, Recording, Paused, Finalizing and error examples, with
  unavailable measurements and an empty session/roster.
- Verify the suspected control-density/minimum-size issues against rendered
  widgets. Label anything not reproduced as an observation or risk.
- Define shared component variants and the minimum public context needed to
  move between pages; identify service owners for missing interfaces.

**Validation:** test group A; manual synthetic layout review at the size matrix.
**Exclusions:** application redesign, physical validation and vendor UI cloning.

**Implementation prompt:**

> Implement UX-01 from docs/UX_WORKSPACE_PLAN.md. Read applicable AGENTS.md files,
> render the active UI with synthetic inputs and no real camera acquisition,
> and deliver the baseline, target layouts and public-interface mapping. Record
> evidence and update only the matching roadmap item when criteria are met.

### UX-02: Introduce the unified workspace

**Software evidence:** [implementation record](review/ux/UX_02_IMPLEMENTATION.md).
Detailed page redesign and manual qualification remain in later packages.

**Owner:** UIAgent; PipelineOrchestratorAgent and CalibrationToolingAgent own
service lifecycle adjustments. **Prerequisite:** UX-01.
**Boundaries:** launcher routing, hosted pages, shared session context and shutdown.

**Deliverables:** one persistent shell with the four destinations. Extract
hostable page content from existing windows; keep compatibility wrappers where
needed for supported entry points. Preserve service instances across navigation.

**Acceptance:**

- Normal page changes do not spawn extra primary windows or lose selection.
- Repeated navigation does not duplicate services, timers or subscriptions;
  no acquisition, recording, finalization or rig edit occurs from navigation.
- Every page displays the active recording state independently of historical
  selection; Setup cannot acquire cameras already owned by runtime capture.
- Preserve environment validation, updater ownership, backend/config routing,
  `--setup`, and shutdown/cancellation behavior with focused regression tests.
- Close/cancel/failed-stop tests prove accepted work drains and workers remain
  owned until cleanup. Page hiding never calls application shutdown.

**Validation:** groups A and B; add shell navigation/context lifecycle tests.
**Exclusions:** detailed page restyling and new domain-state ownership.

**Implementation prompt:**

> Implement UX-02 after checking UX-01 evidence. Build the persistent PySide6
> workspace around existing services, preserve entry routes and lifecycle
> contracts, and test navigation during active and pending operations. Include
> interface changes, synthetic screenshots and roadmap evidence in the handoff.

### UX-03: Clarify recording states and controls

**Software evidence:** [implementation record](review/ux/UX_03_IMPLEMENTATION.md).
Manual hardware/display qualification remains in later packages.

**Owner:** UIAgent with PipelineOrchestratorAgent for public status contracts.
**Prerequisite:** UX-02. **Boundaries:** live controller and global status/actions.

**Deliverables:** consistent state/action presentation using the vocabulary above;
explicit pending, failure and recovery feedback across the workspace.

**Acceptance:**

- Preparing a session cannot look like successful recording. Start Recording is
  explicit; Paused remains visible even while preview continues.
- Controls follow confirmed state and operation admission; repeated clicks do
  not create duplicate commands or conflicting start/end operations.
- Failed start, pause, resume and end retain truthful status and actionable
  recovery. Analysis/comparison failure does not masquerade as recording failure.
- Finalizing ends only after service confirmation; users cannot review the
  current recording as completed while its artifacts are still being written.

**Validation:** groups B and C; add transition/failure/global-status tests.
**Exclusions:** redesigning pipeline lifecycle or changing recording semantics.

**Implementation prompt:**

> Implement UX-03 using public service state and command acknowledgements.
> Align Live and workspace status, test pending/rejected/failed commands and
> finalization, and preserve explicit recording consent. Record acceptance evidence.

### UX-04: Prioritize live pitch feedback

**Software evidence:** [implementation record](review/ux/UX_04_IMPLEMENTATION.md).
Manual hardware/display qualification remains in later packages.

**Owner:** UIAgent. **Prerequisite:** UX-03.
**Boundaries:** live modes, pitch display, shared metric/location components.

**Deliverables:** Latest Pitch, Session Trends and Games views; resizable video;
prominent velocity/location/result/quality; accessible recent pitches and advanced tools.

**Acceptance:**

- Latest-pitch feedback and session controls fit the required viewports without
  an 800x600 video minimum forcing the overall window larger than the display.
- Speed source/reference and units are readable; unavailable/rejected results
  have an explanation, no fabricated values and no normal ball/strike marker.
- Research diagnostics/trials remain reachable under advanced tools with the
  same service admission rules; switching views preserves camera selection.
- Synthetic populated/empty/error screenshots demonstrate hierarchy and keyboard
  operation. Live updates preserve user navigation and avoid stealing focus.

**Validation:** groups A and C; metric/location and resize scenarios.
**Exclusions:** new spin/break claims, new algorithms and unvalidated coach advice.

**Implementation prompt:**

> Implement UX-04 using the approved shared components and layouts. Prioritize
> latest-pitch feedback, move research actions to advanced tools and preserve
> measurement validity. Verify all viewports with synthetic screenshots and tests.

### UX-05: Connect sessions and review

**Software evidence:** [implementation record](review/ux/UX_05_IMPLEMENTATION.md).
Manual display, codec and hardware qualification remains in later packages.

**Owner:** UIAgent; AnalysisAgent owns any review-service interface changes.
**Prerequisite:** UX-04. **Boundaries:** Sessions page, ReviewService and playback.

**Deliverables:** session browsing and direct completed-session/pitch handoff;
playback/results first; expandable technical tools.

**Acceptance:**

- Review Session after successful finalization selects that session without
  asking the user to locate its directory again. Existing local open remains available.
- Selecting a pitch updates video, location and metrics for the same identity;
  stale callbacks cannot overwrite a newer selection.
- Browsing completed sessions during capture preserves the active session and
  does not admit offline refitting/reprocessing or open active partial artifacts.
- Empty sessions, missing video, invalid timestamp mappings and unknown legacy
  provenance produce explicit degraded states. Export selection stays explicit.

**Validation:** group D; add session/pitch handoff and active-capture browsing tests.
**Exclusions:** rewriting recorded artifacts, cloud history and implicit uploads.

**Implementation prompt:**

> Implement UX-05 with public session/pitch context and ReviewService. Connect
> finalization to review, prioritize playback, preserve artifact validity and
> offline admission, and test missing assets and stale selection responses.

### UX-06: Align setup and player workflows

**Software evidence:** [implementation record](review/ux/UX_06_IMPLEMENTATION.md).

**Owner:** UIAgent; CalibrationToolingAgent owns setup-service changes and
PipelineOrchestratorAgent owns active-pitcher command integration.
**Prerequisite:** UX-05. **Boundaries:** guided setup, roster, session attribution.

**Deliverables:** consistent setup status/recovery and player selection in the shell.

**Acceptance:**

- Five setup stages preserve immediate saves, invalidation, rechecks, generations
  and publication. Reopening a stage retains saved values and truthful readiness.
- Runtime capture blocks competing setup acquisition/rig edits in both UI and
  services. Busy-operation navigation follows cancellation/completion contracts.
- Browsing Players or historical sessions cannot change the active pitcher.
  Explicit pitcher changes take effect at a service-confirmed safe pitch boundary
  and do not rewrite attribution for the pitch already underway or prior artifacts.
- Empty roster, invalid/duplicate names, cancelled selection and missing historical
  players have clear outcomes under existing validation/persistence rules.
- Setup success remains estimated research readiness, never accuracy approval.

**Validation:** groups B and E; add roster/attribution and cross-page admission tests.
**Exclusions:** player-ID migration, recording deletion and weakened setup gates.

**Implementation prompt:**

> Implement UX-06 within the existing setup and roster contracts. Preserve
> immediate-save/evidence gates, enforce capture conflicts and make player
> selection consistent without rewriting history. Test re-entry, cancellation
> and safe active-pitcher transitions; document physical checks still pending.

### UX-07: Normalize remaining surfaces

**Software evidence:** [implementation record](review/ux/UX_07_IMPLEMENTATION.md).
Manual display/accessibility qualification remains in UX-08.

**Owner:** UIAgent. **Prerequisite:** UX-06.
**Boundaries:** themes, analytics, dialogs, settings, help and secondary tools.

**Deliverables:** shared presentation/accessibility treatment and terminology audit.

**Acceptance:**

- All surfaces use shared typography, spacing, status semantics and control sizes.
  Technical chart outputs retain units, provenance, denominators and failures.
- Every visible action works or explains its disabled prerequisite; Help opens
  relevant maintained guidance. No placeholder or dead-end actions remain.
- Keyboard focus and accessible labels cover the affected surfaces. Charts have
  readable labels and a text/table equivalent for their key results.
- Synthetic screenshots cover analytics, settings, a dialog and an advanced tool,
  including unavailable/error states. Theme changes do not leak between pages.

**Validation:** groups A and F; focused tests for changed secondary components.
**Exclusions:** dark mode, a new design framework and new analytics algorithms.

**Implementation prompt:**

> Implement UX-07 across remaining UI surfaces using shared theme components.
> Resolve inconsistent labels, inaccessible controls and dead-end actions;
> preserve research semantics. Include focused tests and synthetic visual evidence.

### UX-08: Validate complete operator journeys

**Qualification in progress:** [automated evidence and manual worksheet](review/ux/UX_08_QUALIFICATION.md).
Required real-display, accessibility, packaged and hardware results remain pending.

**Owner:** MaintenanceAgent with UIAgent; operator supplies real-display/hardware evidence.
**Prerequisite:** UX-07. **Boundaries:** complete workspace journeys and release handoff.

**Deliverables:** an evidence report linking automated runs, synthetic screenshots,
manual results, outstanding defects and relevant existing physical release gates.

**Acceptance:**

- Exercise setup -> player selection -> preparation -> recording -> pause/resume
  -> end/finalize -> review, including navigation away from Live while recording.
- Exercise invalid rig, disconnect, rejected command, analysis failure, failed
  finalization, missing review assets, setup cancellation and application close/cancel.
- Verify 1366x768 and 1024x768; at 800x600 essential controls stay visible and
  secondary content has a reachable scroll path. Record real Windows checks at
  125%, 150% and 200%, plus keyboard-only and screen-reader results.
- Run the relevant full regression suite after focused tests pass. No skipped
  Qt test, synthetic camera run or contrast calculation is recorded as manual proof.
- Document setup/recording task completion, missteps and recovery observations;
  do not claim a usability improvement solely from appearance or test counts.

**Validation:** groups A-F, end-to-end simulator coverage, full `python -m pytest`,
manual display/accessibility checks and operator-run hardware lifecycle checks.
**Exclusions:** independent physical accuracy approval and automatic publication.

**Implementation prompt:**

> Complete UX-08 against the package acceptance criteria. Run focused and full
> regressions, collect synthetic journey evidence and record manual results.
> Keep unavailable hardware/display evidence pending and do not mark the package
> complete until its required checks are satisfied. Update the roadmap truthfully.

## Validation commands and evidence rules

Use the repository's supported Python environment and installed development
dependencies. In PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` for isolated
UI checks; use normal display settings for manual visual checks. Use adequate
timeouts for integration/trajectory work. These commands are starting groups:

```powershell
# A: shared UI/theme/accessibility baseline
python -m pytest tests/test_ui_responsiveness_accessibility.py tests/ui/test_glass_theme.py tests/test_ui_imports.py
# B: launcher and coaching lifecycle
python -m pytest tests/test_launcher_entrypoint.py tests/test_launcher_lifecycle.py tests/test_launcher_updates_lifecycle.py tests/test_coaching_shutdown.py
# C: coaching presentation and state
python -m pytest tests/test_coach_window_smoke.py tests/test_coach_window_metrics_lifecycle.py tests/test_coaching_strike_zone_mapping.py tests/ui/test_session_controller.py
# D: review and recorded-session access
python -m pytest tests/ui/test_review_window_refactor.py tests/app/review/test_review_service.py tests/app/review/test_session_loader.py tests/test_review_trajectory_diagnostics_panel.py
# E: guided setup
python -m pytest tests/test_guided_setup_workflow.py tests/test_guided_setup_desktop.py tests/test_guided_setup_tooling.py
# F: shared workflows and comparison regressions
python -m pytest tests/test_ui_workflows.py tests/test_comparison_review_regressions.py
# Documentation links, terminology and freshness
python scripts/check_public_docs.py
```

Changes to this plan require link, package/dependency, test-path, instruction-scope
and roadmap-consistency checks. Runtime packages require the behavior tests and
visual evidence above. Documentation changes alone do not establish redesign
completion. Do not add tests that merely mirror prose or token constants.
