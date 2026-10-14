# Guided setup instructions

Inherits [shared UI instructions](../AGENTS.md). Primary package: UX-06 in the
[workspace plan](../../docs/UX_WORKSPACE_PLAN.md); UX-02 changes hosting.

- Preserve Cameras, Image checks, Calibration, Field and regions, and Ready.
  Keep SetupWorkflowService as the owner of saved edits, generations, checks,
  readiness and publication; widgets issue explicit commands.
- Preserve immediate saving of valid edits and invalidation of affected checks.
  Navigation alone must not edit or publish a rig. Display saved/unchecked state
  and blockers with concrete next actions.
- During runtime capture, Setup may show status but must not acquire competing
  cameras or change the rig. Route the operator back to explicit session/capture
  controls; enforce admission in services as well as disabling UI actions.
- Preserve supervised capture and cancellable tooling. Leaving an idle stage is
  distinct from cancelling an operation; retain ownership until cancellation or
  completion, and prevent stale callbacks from changing a reopened stage.
- Readiness permits estimated research recording; it is not physical accuracy
  approval. Never inherit approval after a rig revision or weaken evidence gates
  to reduce setup steps.
- Make prerequisites, progress, recovery and final publication understandable
  at every viewport. Test edit/recheck/reopen, cancellation, busy navigation and
  capture conflicts using the guided setup group in the workspace plan.
