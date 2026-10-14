# UX-03: Session state, progress and recovery

**Reviewed:** 2026-10-14. **Status:** implemented and checked in software.
**Scope:** UX-03 in the [workspace plan](../../UX_WORKSPACE_PLAN.md).
The [roadmap](../../ROADMAP.md) owns delivery status.

The workspace now has one set of essential session controls. Preparation starts
preview only; recording still requires Start Recording. Slow lifecycle commands
run in a retained worker while the header shows the last service-confirmed state,
operation progress and supported recovery. Navigation remains available.

## Delivered behavior

- Idle, Preview, Ready, Recording, Paused, Finalizing and Completed come from
  RuntimeStatus plus acknowledged preparation context. Pending commands cannot
  be mistaken for successful recording. Paused explicitly says cameras remain live.
- Session details and end confirmation remain Qt dialogs. The preparation dialog
  uses the saved rig assignment and performs no camera discovery. Missing hardware
  assignment directs the operator to guided Setup; simulator labels remain synthetic.
  Session fields scroll at smaller viewports while confirmation/cancel stay visible.
- One SessionCommandRunner admits one request at a time and retains its QThread
  until it terminates. Immutable request/result contracts carry correlation,
  preparation inputs, terminal service status, errors and separate summary notices.
- Duplicate and conflicting actions are rejected immediately, before the service
  worker can publish its first status event. Timers skip service polling during
  an admitted command so they cannot wait on the same lifecycle lock.
- Start, pause, resume and end failures keep the service's ownership and state.
  Inline feedback names the failed operation and offers a state-supported retry.
  Failed finalization now exposes an enabled Retry End Session action.
- Finalizing blocks duplicate session commands and the completed-session action
  until service completion; historical browsing remains available. A failure
  reading the final summary after successful drain is a summary notice, not a
  recording failure. Measurement unavailability remains separate from recording.
- Completed offers Review Session, New Session and explicit Stop Preview if
  cameras remain live. Review Session still navigates to Sessions; automatic
  session/pitch loading remains UX-05.
- Hosted Live hides its duplicate recording/review/help buttons and status footer.
  The shell controls stay visible across all destinations. Capture/setup controls
  and update installation are guarded while commands are pending.
- Exit closes command admission and waits for the admitted command before starting
  pipeline shutdown. It retains workers and services through drain and failed
  cleanup. Cancelling end or exit preserves recording and Live timers.

SessionCommandRunner owns UI request admission, not domain state. Algorithms,
recording consent checks, rig admission, lifecycle transitions and persistence
remain in QtPipelineService/PipelineOrchestrator and their services. Standalone
compatibility windows retain their existing controller; the default workspace
uses AsyncSessionController.

## Instructions and public contracts

Applicable instructions are the [root specification](../../../agents.md),
[shared UI instructions](../../../ui/AGENTS.md),
[coaching](../../../ui/coaching/AGENTS.md) and
[workspace](../../../ui/workspace/AGENTS.md) instructions. Existing setup, review
and theme instructions continue to govern those hosted experiences.

PrepareSession captures configuration, local config path, camera identities and
session presentation identity. SessionCommand and SessionCommandResult link
request and receipt. SessionOperation describes UI progress/errors only;
SessionPresentation derives labels, next action and explanation from public
RuntimeStatus. The existing service status contract remains unchanged.

CoachWindow exposes `session_operation()`, `session_command_busy()`,
`begin_session_shutdown()` and `apply_runtime_status()` alongside its existing
action handoff. Pages communicate through public adapters and Qt signals; no
private service state was added to the UI path.

## Evidence and verification

The [actual-widget state gallery](ux03/index.html) has 60 synthetic captures at
1366x768, 1024x768 and 800x600. It covers preparation, starting, all confirmed
states and failed prepare/start/pause/resume/end, including status on Sessions,
Players and Setup. The [manifest](ux03/manifest.json) records source identity,
requested/actual geometry and controls. No capture, recording or command worker
is started by the evidence script. Compare the [UX-02 gallery](ux02/index.html)
for the earlier shell and duplicate Live controls.

Inspection confirms visible recovery actions, readable Paused/Finalizing state,
and reachable global controls at the target sizes. Live and Sessions still have
dense scrolling content; UX-04 and UX-05 own those layouts. Synthetic rendering
does not establish improved usability, physical accuracy or Windows DPI quality.

Focused checks used Python 3.13.16 and 3.14.8 with installed PySide6. They prove
responsive navigation during blocked commands, duplicate rejection, truthful
failure/retry, explicit preparation, cancellation and retained exit ownership.
A real simulator test exercises all commands through QtPipelineService and
confirms finalization receipt and session-directory persistence. Existing
accepted-pitch terminal-delivery tests preserve the drain guarantee.

Recorded runs overlap and must not be added together:

| Check | Result |
|---|---|
| Workspace command/navigation/status tests on Python 3.13 before the added simulator integration case | 38 passed |
| Launcher/coaching/source GUI regression group | 46 passed, 1 packaged-build skip |
| Command tests with real simulator integration, Qt pipeline bridge and accepted-pitch terminal delivery | 32 passed |
| Broad desktop regression suite, including shared UI, setup and review | 168 passed, 1 packaged-build skip |
| Final command/navigation/accessibility/source-smoke check after preparation-layout changes | 50 passed, 1 packaged-build skip |
| Changed-code mypy on canonical Python 3.13 across UX-01 through UX-03 | Passed, 41 source files |
| Changed-code lint, public docs, tracked/new Python lengths, UX links and 60 capture geometry checks | Passed |

Third-party deprecation warnings did not fail tests. The packaged smoke test
requires `PITCHTRACKER_PACKAGED_DIR`; no packaged build was supplied. The full
repository suite and clean-machine qualification remain UX-08/release gates.
The local ignored-vendor suppression-scan condition documented in
[UX-02](UX_02_IMPLEMENTATION.md) remains outside this change.

## Next work and manual checks

UX-04 should reduce Live density, shrink video deliberately, prioritize the
latest pitch and recent pitches, and move research controls into advanced tools.
UX-05 connects finalized-session and pitch identities directly to review.

Windows scaling at 125%, 150% and 200%, keyboard/screen-reader journeys,
real-rig disconnect/retry, camera-start and writer-drain timing, and packaged
installation remain operator-run checks. No hardware or physical measurement
approval is inferred from the simulator or screenshots.
