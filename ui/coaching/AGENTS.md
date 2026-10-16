# Live coaching instructions

Inherits [shared UI instructions](../AGENTS.md). Primary packages: UX-03 and UX-04
in the [workspace plan](../../docs/UX_WORKSPACE_PLAN.md); UX-02 changes hosting.

- Keep the shell, session controller and pitch presentation responsibilities
  separate. QtPipelineService remains the public route to pipeline operations.
- Make latest-pitch velocity, location, result and measurement status prominent.
  Allow video to shrink; keep recent pitches accessible. Use Latest Pitch,
  Session Trends and Games as the target view labels.
- Present service-confirmed Preview, Ready, Recording, Paused and Finalizing
  states. A preview is not recording; paused cameras may remain live. Failures
  must retain the last known lifecycle state and expose the affected operation.
- Keep source/reference information available for speed. Movement remains
  unavailable without existing validation evidence. Never convert rejected or
  unavailable locations into normal strike/ball markers.
- Match speed provenance to the selected recorded measurement. Preserve known
  provenance when a rejected value is suppressed; ambiguous legacy references
  remain unavailable. Keep recent-pitch selection stable on incoming updates.
- Latest Pitch uses a keyboard-resizable preview and scrollable feedback. Check
  wrapped headline, units, provenance and location at 800x600; secondary view
  minima must not enlarge the entire workspace.
- Move detector trials and detailed diagnostics into advanced tools without
  removing research functionality or relaxing its admission requirements.
- Navigation must preserve timers/subscriptions needed for an active session;
  application shutdown must stop them and retain workers until cleanup completes.
- Test session actions, rejected commands, repeated navigation, measurement
  updates and shutdown. Begin with the coaching test group in the workspace plan.
- The hosted controller uses immutable command/receipt contracts and one retained
  worker. Keep dialogs and widgets on Qt, skip service polling while commands
  own lifecycle locks, and derive progress/retry from service facts. Preparation
  uses saved rig camera identity; discovery and assignment belong in guided Setup.
