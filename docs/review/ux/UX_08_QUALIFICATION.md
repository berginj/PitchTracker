# UX-08: Operator journey qualification

**Reviewed:** 2026-10-14. **Status:** in progress. UX-08 remains unchecked in
[Roadmap](../../ROADMAP.md) until the required manual evidence exists. Scope and
acceptance are in the [workspace plan](../../UX_WORKSPACE_PLAN.md).

## Automated journey and fixes

The new complete-workspace test uses real QtPipelineService/PipelineOrchestrator,
SetupWorkflowService, capture workers, recording writers and ReviewService.
It inspects all five setup stages, publishes synthetic checked inputs through
Finish, chooses a roster player explicitly, prepares simulator preview, records,
navigates to Sessions/Players/Setup, pauses/resumes from Setup, finalizes, opens
the exact completed session and explicitly stops preview. Shutdown retains
workers until terminal cleanup. It uses a disposable local rig/roster/output;
no physical camera or operator recording is opened.

The simulator produces a neutral surface, not measured pitches. This journey
does not establish ball detection, pitch accuracy, physical calibration, target
rig operation or a usability improvement. Recorded pitch feedback and review
failure presentations use separately labeled synthetic fixtures.

Two reproducible gaps were fixed during this work:

- An offscreen recovery-layout test forced the completed-session workspace to
  1013 pixels wide at the 800x600 target. Global actions now use two columns at narrow
  widths. Progress/recovery text is a bounded, keyboard-readable scroll area
  retaining the complete message. The primary action's accessible name follows
  its current command. Tests check actual visibility as well as geometry.
- Grayscale simulator frames were all zero, and the existing capture validity
  gate rejected them indefinitely. The simulator now generates a nonzero neutral
  grayscale surface, as its color mode already did. All three supported simulator
  formats pass the normal frame-validity gate; physical frame admission is unchanged.

The GitHub review also exposed a validation defect: the old ChArUco test returned
`False` for a missing workstation-local image and pytest counted it as passing.
The test now renders a board using shared calibration helpers and asserts all
40 inner corners. It has no dependency on a private/local board artifact.

## Acceptance and evidence map

| Journey / condition | Automated evidence | Remaining manual evidence |
|---|---|---|
| Setup → player → prepare → record → pause/resume → finalize → review | `tests/test_workspace_simulator_journey.py`, real services with synthetic rig/cameras | Target rig, representative pitches and operator observations |
| Navigation while recording; capture/rig ownership; historical identity | Workspace navigation, session-command, attribution and Sessions tests | Keyboard-only cross-page recording journey |
| Invalid config/rig; rejected commands; failed finalization and retry | Workspace navigation/session-command tests; setup admission tests | Target-rig failure injection and recovery |
| Analysis failure retains unavailable verdict and artifacts | `tests/integration/test_analysis_failure_durability.py`, measurement claim gating | Representative failed pitch and report review |
| Disconnect / worker failure | Capture process/runtime and integration recovery tests; labeled UI fixture | Actual camera removal/reconnection while previewing/recording |
| Missing review assets and mappings | ReviewService/session-loader tests and review capture fixtures | Real selected-session playback and export |
| Setup cancellation and busy navigation | Guided setup and `tests/test_setup_capture_ui.py`, including bounded subprocess cancellation | Cancel/re-enter on the target rig during capture and calibration |
| Application close, cancel, failed cleanup and retry | Workspace navigation/session-command, coaching shutdown and pitch-terminal integration tests | Operator-run close/cancel during real capture/recording |
| Viewport reachability including long failure details | `tests/test_workspace_journeys.py` at 1366x768, 1024x768 and 800x600 | Real Windows scaling and assistive technology checks below |

The [UX-07 gallery](ux07/index.html) and previous package galleries retain the
before evidence. The current [operator journey gallery](ux08/index.html) records
actual widgets, viewport/state labels, source revision and dirty-worktree status
in its [manifest](ux08/manifest.json). These are display fixtures; the real-service
simulator journey is a separate automated test. No gallery image is manual proof.
All **57 captures** decoded successfully. The 54 current captures match their
requested viewport sizes, and essential global actions fit their requested bounds.
Three before captures render the prior header implementation at the base commit
with the current shared theme and loaded Windows fonts. Their long message consumes
most of the review area; their dimensions do not reproduce the separate 1013-pixel
offscreen-font test result. The current bounded message area preserves review space.

## Validation record

The supported local Python environments run offscreen Qt. Required groups A–F
passed **150 tests** before the additional UX-08 layout/simulator fixes.
The focused real-service simulator journey and three simulator-format contracts
passed **4 tests** after the grayscale fix. Final affected/full-suite results
are recorded below once the terminal process statuses have been observed.
The final viewport/recovery group passed **13 tests** with both pytest and the
process returning zero; it checks visible controls and the full long-error state.
The full Python 3.13 run passed **1,936 tests, 37 skipped**, in 281.85 seconds.
Its pytest return and final process exit were both **0**; only MainThread remained
at pytest return in the controller. Skips and warnings are retained in the local
JUnit/log output; they are not counted as successful qualification.
The 37 skips comprise 10 opt-in soak/marathon tests (their reason also notes
API rework), six offscreen codec probes, seven frozen-artifact/GUI checks,
three standalone numerical-worker checks, eight future cloud/Bluetooth tests,
one ONNX dependency check, one privileged Windows symlink check and one
operator-supplied video test. None is reported as passed.

Full-suite execution uses `scripts/qualify_tests.py`, which runs pytest without
retrying or suppressing failures, enables faulthandler and prints the pytest
session/return status and remaining Python thread names. The calling shell must
also record the final process exit code. This helps investigate the historical
Python 3.14 runs that printed passing summaries but exited unsuccessfully; it
does not establish that their unidentified cause has been fixed.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PITCHTRACKER_UVC_NATIVE_PROBE = '0'
python scripts/qualify_tests.py -q --tb=short --junitxml=screenshots/ux08-tests.xml
$qualificationExitCode = $LASTEXITCODE
Write-Output "Qualification process exit: $qualificationExitCode"
python scripts/capture_operator_journeys.py
python scripts/check_public_docs.py
python scripts/check_file_length.py
```

## Manual qualification worksheet — partial evidence

### Reconciliation validation — 2026-10-19

The staged UX-07/UX-08 work was preserved in local checkpoint `151f645`, then
reconciled with `main` at `3639247` and documentation PR #49 at `2704bd1`.
Documentation-map and relocated runtime-contract conflicts were resolved while
retaining the UX evidence and the canonical maintenance/documentation structure.
The unfinished release assessment and task prompt remain local and in the
checkpoint; they are excluded from the reviewed source snapshot.

The reconciled source at `2ccc3b6` passed the full Python 3.14.8 Windows x64 suite:
**1,953 passed, 37 skipped**, in 1,219.20 seconds. Pytest returned zero and the
final process exit was zero. The existing skip categories above remain unverified.
Daemon log, analysis-worker and worker-reader threads remained at pytest return;
this result does not establish real-camera or packaged shutdown qualification.

The earlier concurrent focused run had 84 passes, one packaged skip and one
five-second blocked-resume test-double timeout. That test passed in isolation,
and the subsequent complete serial suite passed without changes to lifecycle
code, test deadlines or assertions. Both results are retained in ignored local
validation output. Repository mypy passed 874 source files with Python 3.13.
Lint, typing policy, schema, documentation and file-length gates passed using a
clean source snapshot, excluding ignored workstation environments from source
analysis. Synthetic evidence and all physical/manual limits remain unchanged.

### Camera-free desktop follow-up — 2026-10-19

Scope: UX-08 qualification, the empty-setup journey, and simulator lifecycle.
The source baseline is `5114234`; follow-up changes fix the application palette,
scope Review shortcuts to its own widget tree, and explain disabled preparation
when a physical camera pair is unassigned. Public service contracts are unchanged.
Applicable instructions are the root, shared UI, workspace, themes, coaching,
Review, Players and guided-setup instructions linked above and below.

The Windows platform plugin ran on the LP150UD171878 display at device-pixel ratio
2.0 (the current 200% desktop setting). Fifteen synthetic page/recovery captures
matched 1366x768, 1024x768 and 800x600 logical viewports without capture ownership.
The [desktop gallery](ux08/desktop-2026-10-19/index.html) contains representative
window-only evidence and its provenance. Captures and native key probes are
automated observations; the operator confirmations below are recorded separately.

On 2026-10-19 the operator confirmed readable text and Tab/Shift+Tab/Space page
navigation at 200%. The operator then reported readable text at actual Windows
125% and 150% settings and clear Narrator announcements for navigation buttons
and the main session action. These are operator-reported observations of the
synthetic source-run window; intermediate display settings and spoken output
were not instrumented or recorded. They do not cover a complete keyboard-only
recording journey or every changing status, chart and recovery announcement.

The desktop check exposed dark native palette surfaces underneath light-theme
text. Explicit shared palette roles correct the rendered contrast; the regression
checks actual rendered surface contrast after starting with a dark system palette.
The initial native keyboard probe also reproduced a cross-page defect: Review's
Space shortcut intercepted navigation after Sessions opened. A regression failed
before the fix; both navigation activation and Review-local playback pass after
scoping its actions. A subsequent guarded Windows Tab/Space probe activated
Sessions, Players and Setup with no capture ownership. Enter alone did not activate
the navigation buttons; this observation is retained rather than called a pass.

Focused evidence:

- Shared theme, viewport, accessibility and recovery group: 30 passed.
- Empty setup, workspace navigation, Players and Review group: 46 passed.
- Unassigned preparation and session-command admission group: 19 passed.
- Shortcut regression: one failed/one passed before; two passed after correction.
- Real-service simulator journey, frame formats and analysis-failure durability:
  eight passed. Setup publication, player selection, prepare/preview, recording,
  navigation, pause/resume, finalization, Review and capture shutdown are exercised.
  Synthetic recording manifests and a complete evidence journal were retained
  locally; no physical camera assignment or operator recording was used.

Controlled offscreen Qt scale-factor runs at 1.25 and 1.5 each passed 15 viewport
and recovery cases. They simulate Qt scaling and do not qualify the actual Windows
125%/150% settings. Changed-source lint and canonical Python 3.13 typing passed
three modules; documentation, schema mirror and file-length checks passed.

These counts name focused runs, not unique tests or full-suite totals. Original
failures and all local logs remain in ignored qualification output. Full regression
validation is tracked by the follow-up pull request's required CI checks.
Complete operator journeys, the remaining assistive-technology surfaces and
packaged/hardware gates remain pending. UX-08 remains open.

Record the tested revision, application build, Windows version, display model,
effective viewport, scaling, operator and date with each result. Use synthetic
sessions for shared screenshots; keep private recordings and athlete names local.

| Check | Procedure | Status |
|---|---|---|
| Display matrix | At 1366x768 and 1024x768, verify every page and its essential controls; repeat the reachable 800x600 layout | Pending |
| Scaling | Repeat relevant journeys on actual Windows displays at 125%, 150% and 200%; inspect clipping, text, dialogs and error recovery | Operator confirmed readability at all three scales; complete journeys/dialogs pending |
| Keyboard | Use Tab/Shift+Tab, Enter/Space, Escape and arrow keys to prepare, record, navigate, pause/resume, finalize and review; verify focus remains visible and safe | Operator confirmed Tab/Shift+Tab/Space page navigation at 200%; complete recording journey pending |
| Screen reader | With Narrator or the target reader, verify current page, recording status, changing command labels, disabled prerequisites, chart tables and complete recovery text | Operator confirmed navigation and main session action labels; other surfaces pending |
| Setup / runtime ownership | Complete five-stage setup, cancel/re-enter busy work, publish explicitly, and attempt competing edits while capture owns the rig | Pending |
| Hardware recovery | Disconnect/reconnect the qualified pair, reject a command, interrupt a writer safely, and verify ownership, retry and accepted-work draining | Pending |
| Frozen application | Check local Help, roster persistence, video playback, close/cancel and recovery in the installed build on a clean machine | Pending |
| Operator observations | Record task completion, time/missteps, confusing labels, recovery actions and unresolved defects for each journey | Pending |

Existing [physical validation](../../PHYSICAL_VALIDATION_PROTOCOL_V2.md),
[camera qualification](../../ROADMAP.md#physical-validation-and-tester-feedback)
and [controlled-pilot gates](../../CONTROLLED_PILOT_CHECKLIST.md) remain independent.
No physical accuracy approval or publication is granted by this UX work.

Applicable instructions: [root](../../../AGENTS.md), [shared UI](../../../ui/AGENTS.md),
[workspace](../../../ui/workspace/AGENTS.md), [coaching](../../../ui/coaching/AGENTS.md),
[review](../../../ui/review/AGENTS.md), [setup](../../../ui/setup/AGENTS.md),
[Players](../../../ui/team/AGENTS.md) and [themes](../../../ui/themes/AGENTS.md).
Public service and durable artifact contracts are unchanged; the simulator
background correction affects generated pixels only.
