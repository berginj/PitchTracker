# Recorded-session service instructions

Inherits the [root specification](../../agents.md). ReviewService owns local
artifact access, playback admission and recorded pitch mapping for UX-05 in the
[workspace plan](../../docs/UX_WORKSPACE_PLAN.md).

- Keep browsing read-only. Loading, selecting or playing recorded artifacts
  must not schedule detection, refitting, reprocessing, exports or uploads.
  Single-frame research detection requires an explicit command and service
  admission; batch research retains AnalysisAgent's existing worker ownership.
- Reject the active recording directory through public RuntimeStatus context,
  including finalization. Historical sessions with the same display name remain
  independent. Do not infer identity from a name prefix.
- Pitch navigation requires contiguous accepted encoded-frame mappings, matching
  video counts, increasing monotonic timestamps and one capture epoch per camera.
  Never restore the old `pitch_index * 100` approximation. Unsupported unequal
  camera mappings need an explicit unavailable reason; raw session playback must
  leave pitch association through an explicit caller command.
- Repeated frame reads for display, detection or overlays must return the same
  encoded position. Do not advance decoders behind an unchanged timeline index.
- Missing video preserves readable recorded metrics. Unknown legacy validity,
  provenance, nonfinite values and rejected evidence cannot become normal speed,
  ball/strike or location claims. Do not rewrite artifacts to fill missing values.
- Preserve loader compatibility defaults and safe artifact paths. Expose narrow
  public typed accessors rather than UI access to mutable service fields.
- Validate mapping corruption, missing assets, active-path admission, decoder
  positions, selected metrics and session/pitch handoffs at their useful boundary.
