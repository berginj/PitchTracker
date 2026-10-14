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
- Session history uses the configured recording root; Open Local remains usable
  without a default recordings folder. Use ReviewSelection for direct session
  and pitch handoff, and retain the prior context on a failed load.
- Row selection updates the full review context. Block list signals during load
  and programmatic selection, stop old playback before replacement and avoid
  event-loop re-entry while loading. Queued refreshes read the current selection.
- Camera tabs and two-column playback controls keep the review reachable at
  800x600. Secondary feedback and research tools scroll vertically. Research
  panels start collapsed; browsing never runs frame detection automatically.
- Use the [review-service instructions](../../app/review/AGENTS.md) for playback
  mapping and degraded artifact semantics. Missing calibration disables projected
  trajectory overlays rather than substituting a default camera model.
