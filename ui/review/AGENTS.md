# Session review instructions

Inherits [shared UI instructions](../AGENTS.md). Primary package: UX-05 in the
[workspace plan](../../docs/UX_WORKSPACE_PLAN.md); UX-02 changes hosting.

- Prioritize the selected session, pitch list, playback and corresponding metrics.
  Put parameter tuning, annotations for research and trajectory diagnostics in
  expandable advanced tools while preserving their capabilities.
- Receive session/pitch context through a public typed handoff. Load recorded
  artifacts through ReviewService; do not depend on a live window's private state.
- Show which historical session/pitch is selected while the workspace separately
  shows any active recording. Changing selection must update video, metrics and
  location together; suppress stale asynchronous results.
- Offer review of the just-ended session only after finalization succeeds.
  Do not open a partially written active session as a completed recording.
- Preserve timestamp mapping checks and artifact provenance. Missing video,
  missing calibration, legacy unknown provenance and rejected measurements need
  explicit degraded states, not fabricated overlays or silently substituted data.
- Offline processing stays in AnalysisAgent services and pauses admission during
  capture. Browsing completed sessions must not implicitly schedule reprocessing.
- Keep exports limited to explicitly selected artifacts. Navigation must not
  delete sessions or upload data. Test context handoff, missing assets, playback,
  cancellation and service-owned processing admission.
