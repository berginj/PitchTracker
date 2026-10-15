# Workspace shell instructions

Inherits [shared UI instructions](../AGENTS.md) and the
[root specification](../../agents.md). UX-02 establishes hosting; UX-03 through
UX-08 own subsequent behavior, page presentation and qualification.

- Keep one QtPipelineService and one retained instance of each destination.
  Page navigation changes presentation context only. Do not acquire cameras,
  persist rig edits, start processing or finalize a session from page activation.
- Read immutable RuntimeStatus through its public API and signal. Do not infer
  domain success from widget state or access private service state.
- Keep active recording identity independent of browsed player and historical
  ReviewSelection. Use public adapters for action and selection handoffs.
- Setup acquisition/edit admission belongs to SetupWorkflowService. An explicit
  Stop Preview action is required before workspace rig edits; navigation cannot
  stop runtime capture. Preserve busy-stage cancellation and ownership.
- Retain shutdown workers and page controllers until terminal cleanup. Failed
  shutdown exposes an explicit retry; cancelling exit preserves Live timers.
  Include validation and updater workers in close handling and update admission.
- Keep global status and essential session actions visible at all target sizes.
  Secondary page content may scroll. Startup must remain camera-free.
- Dispatch slow session commands through the retained SessionCommandRunner.
  Its admission state is UI progress only; RuntimeStatus owns confirmed facts.
  Wait for an admitted command before pipeline shutdown. Never cancel finalization
  by destroying its thread or offer review from a pending/failed finalization.
- Validate navigation, historical context, command failures, setup conflicts,
  exit/cancel/retry, updater admission and source GUI smoke. Record synthetic
  captures separately from manual Windows DPI, accessibility and hardware checks.
- Review Session hands off RuntimeStatus.finalized_session only after confirmed
  success; a pending/failed end cannot trigger it. Pass the exact active directory
  to ReviewService admission while browsing independent completed artifacts.
- Players history passes an optional recorded label in ReviewSelection. Keep
  that filter visible and clearable, and never infer it from the active pitcher.
  The header shows confirmed active/pending pitcher context across destinations.
