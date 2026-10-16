# UX-05: Sessions and pitch review

**Reviewed:** 2026-10-14. **Scope:** UX-05 in the
[workspace plan](../../UX_WORKSPACE_PLAN.md).
[Roadmap](../../ROADMAP.md) owns delivery status.

Review Session now opens the successfully finalized session directly. Sessions
also lists local history from the configured recording directory and retains an
explicit Open Local action. Historical identity stays separate from the active
recording shown in the workspace header.

## Delivered behavior

- Selecting a pitch row updates its identity, recorded metrics, plate location,
  diagnostics, timeline and video together. Programmatic selection blocks list
  signals; old playback stops before replacement. Loading no longer pumps Qt
  events partway through a state change. Queued display refreshes read current
  service state rather than retaining an earlier pitch's frame.
- Pitch navigation replaces the old index-times-100 guess with encoded-frame
  timestamp checks. It requires accepted contiguous mappings, matching video
  counts, increasing timestamps, consistent capture epochs and a pitch interval
  inside both recorded streams. The current paired reader requires equal mapped
  camera indices; unsupported unequal mappings fail with an explicit reason.
- Missing video leaves metrics available. Invalid/legacy timestamp mapping clears
  pitch video and disables associated playback. Browse full session video is an
  explicit route to raw playback without pitch association. Unknown historical
  provenance/validity remains unknown; rejected/unavailable values do not become
  numeric coaching-speed, normal verdict or plate-location claims.
- Video is camera-tabbed and playback controls use two columns. At 800x600 the
  primary pitch feedback fits without horizontal workspace overflow; playback,
  pitch list and secondary tools have vertical scroll paths. Timeline keyboard
  controls support Left/Right and Home/End. Manual display checks remain pending.
- Detection parameters, scoring and trajectory diagnostics are expandable research
  tools. Existing comparison, annotation and explicit export routes remain.
  Browsing no longer runs detection; an explicit frame command checks capture
  admission. Detector construction is lazy. Missing recorded calibration disables
  projected overlays instead of using invented defaults.
- The exact active directory is blocked during recording/finalization. Completed
  sessions with the same name remain independent. Browsing does not stop capture,
  change the active pitcher or schedule offline processing. Exports still use the
  selected loaded session and explicit destination dialogs.

## Public interfaces and ownership

RuntimeStatus adds `active_session_dir`, published from RecordingAgent's public
session-directory accessor with confirmed lifecycle facts. Runtime status reads
remain cached. FinalizedSession and ReviewSelection retain their existing shapes.

ReviewService adds runtime admission, available-session access, immutable
PitchPlayback mapping, playback availability/issue accessors, copied pitch scores
and an explicit raw-session-video command. SessionLoader's keyword-only
`require_video=False` permits metadata-only review; its default validation remains
compatible. ReviewWindow's public open handoff returns success and honors pitch
identity. Coaching exposes the configured recording directory through a public
adapter. No durable schema, recording output or numerical analysis changes.

Applicable instructions: [root](../../../AGENTS.md), [shared UI](../../../ui/AGENTS.md),
[review UI](../../../ui/review/AGENTS.md), [workspace](../../../ui/workspace/AGENTS.md),
[coaching](../../../ui/coaching/AGENTS.md), [themes](../../../ui/themes/AGENTS.md)
and [review services](../../../app/review/AGENTS.md).

## Evidence and qualification

The [actual-widget gallery](ux05/index.html) contains 24 synthetic captures at
1366x768, 1024x768 and 800x600: no history, measured, empty, missing video,
invalid mapping, unknown legacy validity, rejected and browsing during capture.
The [manifest](ux05/manifest.json) records viewport/control geometry. Compare the
[UX-02 gallery](ux02/index.html) for the earlier hosted review layout. The script
uses disposable artifacts and an in-memory synthetic decoder; it never acquires
cameras, opens private recordings, admits offline processing or uploads data.

Focused tests cover session/pitch handoff, failed/pending finalization, active-path
admission, repeated frame reads, corrupt mapping, selected metrics, queued refresh,
configured history and recovery. The initial service/selection checks passed 22
tests; a subsequent review/workspace group passed 78 tests. These runs overlap.
The broader review/workspace/commands/comparison/workflow/source-smoke run passed
130 tests with one packaged-build skip. Packaged smoke requires
`PITCHTRACKER_PACKAGED_DIR`. These counts overlap and must not be added together.

Final Python 3.14 review/service/mapping/runtime checks passed 73 tests. Canonical
Python 3.13 mypy passed 46 files, and repository source Flake8 passed 853 files.
Public documentation and the 500-line file convention checks passed.
The final Python 3.13 selection/calibration/entrypoint run passed 24 tests.
All 24 gallery images matched their requested dimensions and contained visible
content; the durable schema mirror check passed.

The preceding UX-04 CI run exposed an older diagnostics fixture without a session
directory; its isolated nine-test fix was pushed to PR #45. This package also
updates those test doubles to the new public review accessors.
The next full CI run reached 1,859 passing tests on Python 3.13 and exposed an
outdated direct-setup entrypoint mock plus unwanted startup validation for
`--setup`. The mock and explicit startup routing were corrected separately in
PR #45; the Python 3.14 matrix job was cancelled after the 3.13 failure.

Full-suite CI, packaged playback, real codecs, actual session timestamp evidence,
Windows DPI at 125/150/200%, screen-reader/keyboard journeys and target-rig checks
remain separate qualification evidence. Synthetic decoder checks do not establish
codec behavior or physical speed/location accuracy. Unequal camera mappings are
explicitly unsupported for pitch-associated playback; raw video remains available.

UX-06 is next: setup/player workflow alignment and safe attribution integration.

## Review follow-up — 2026-10-15

Preparation now selects the configured recording root through the public pipeline
command. RecordingService creates a missing requested directory; the real
simulator journey verifies that finalized artifacts land in that same root.
Independent completed history remains browsable during recording startup while
the exact active directory remains blocked.

ReviewService.load_session accepts an optional requested pitch ID and checks it
before replacing the current session or decoder. The public UI/controller handoff
forwards that ID. A stale ID leaves the previous selection, feedback, video
position and scoring intact and shows the existing recovery message. Existing
artifact formats and measurement semantics are unchanged.

The focused review, mapping, command and recording-service regression group
passed 79 tests on Python 3.13. New regressions include custom-root preparation,
same-session and different-session stale IDs, retained service state, and
independent history with known or unavailable startup directory identity.
The existing synthetic gallery remains the layout reference; the manual codec,
display, accessibility and physical-rig qualification gates above still apply.
