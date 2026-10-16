# UX-06: Setup and Players in the workspace

**Reviewed:** 2026-10-14. **Scope:** UX-06 in the
[workspace plan](../../UX_WORKSPACE_PLAN.md).
[Roadmap](../../ROADMAP.md) owns delivery status.

Setup now shows the current stage, saved revision, readiness and blocking action
in the workspace. Players separates roster browsing and recorded history from
an explicit active-pitcher command. A change requested during ramp-up or an
active pitch waits for that pitch's terminal boundary.

## Delivered behavior

- The five guided stages keep immediate saves, check invalidation, generations,
  re-entry, cancellation and explicit publication. Failed saves update the shell
  to show unsaved changes. The hosted layout removes its duplicate header and
  permits narrow stage content, leaving more room at 800x600. Navigation alone
  does not save or acquire cameras. Runtime capture blocks competing rig edits
  through both presentation and the existing service admission checks.
- Players supports keyboard selection, clear empty/duplicate/invalid-name
  feedback and atomic local roster saves. Renaming or removing a roster label
  preserves the active pitcher and recorded history. Preparation uses this same
  roster; cancelled preparation/selection does not create a player or dispatch a
  pitcher command. Fabricated sample names have been removed.
- **Use as active pitcher** is explicit. The coordinator serializes it with
  pitch lifecycle events and publishes an immutable active/pending snapshot.
  Ramp-up, active and ending pitches retain their original label. Rejected
  pitches and false starts also release pending changes. The latest request
  wins; requesting the active name cancels a pending change. Finalization blocks
  changes. UI labels follow confirmed service state.
- Pitch-start attribution travels through end events and delayed analysis to
  summaries, manifests and CSV. A worker finishing after a pitcher switch retains
  the original pitch's name. Comparison verdicts and measurement eligibility
  remain independent of player labels.
- **View Sessions** filters by exact recorded label and selecting a session
  retains that filter for its pitch list. **Show all players** removes it.
  Unattributed legacy pitches do not match a guessed player. Browsing and roster
  edits never rewrite artifacts or change runtime attribution.

## Public contracts and migration

`PitcherSelection` carries `active_name`, `pending_name` and `pitch_id`.
`RuntimeStatus.pitcher` publishes that snapshot; `change_pitcher(name)` on the
pipeline service returns a confirmed receipt. EventCoordinator owns the binding
under its existing tracking lock. `PitchStartEvent`, `PitchEndEvent` and
`PitchSummary` add optional `pitcher_name`. Analysis copies captured attribution
before summary publication. Recording remains the sole artifact writer.

The durable schema version is **1.3.0**. New manifests add the versioned
`pitcher_attribution.v1` block with an explicit operator-selection or unattributed
basis; summaries and CSV add an optional label. Old artifacts remain readable
without rewriting. This is label attribution, without stable player IDs,
automatic rename propagation or a historical-data migration.

`ReviewSelection` adds an optional player label; ReviewService supports recorded
player filtering. Guided setup exposes read-only `SetupPresentation` and a
presentation-change signal. SetupWorkflowService retains configuration,
generation, checks, publication and hardware admission ownership.

Applicable instructions: [root](../../../agents.md), [shared UI](../../../ui/AGENTS.md),
[workspace](../../../ui/workspace/AGENTS.md), [Players](../../../ui/team/AGENTS.md),
[setup](../../../ui/setup/AGENTS.md), [coaching](../../../ui/coaching/AGENTS.md),
[review UI](../../../ui/review/AGENTS.md), [review service](../../../app/review/AGENTS.md)
and [themes](../../../ui/themes/AGENTS.md).

## Evidence and remaining qualification

The [actual-widget gallery](ux06/index.html) contains 30 synthetic captures at
1366x768, 1024x768 and 800x600. States include empty/populated Players, duplicate
names, pending changes, filtered/unknown history, capture-owned Setup and saved
setup re-entry. The [manifest](ux06/manifest.json) records source and geometry.
`scripts/capture_setup_players.py` uses disposable configuration and synthetic
recorded artifacts/decoding; it does not access cameras, private recordings or
the operator roster. Earlier layouts remain in the [UX-02 gallery](ux02/index.html).

Focused attribution/UI checks cover ramp-up, rejected pitches, concurrent
commands, delayed analysis, finalization rejection, roster/history preservation,
cancelled selection, saved-edit failure and runtime/setup conflicts. Python 3.13
workflow/review/contract checks passed 77 tests. Python 3.14 checks including
source GUI smoke passed 82 tests with one packaged-build skip, which requires
`PITCHTRACKER_PACKAGED_DIR`. The later Python 3.13 durable-event/recording/review
group passed 90 tests; the final pipeline/analysis/recording/setup integration
group passed 44 tests. These runs overlap and must not be added together.
The final attribution/Players/session-command group passed 31 tests, including
UTF-8 names, failed atomic saves and malformed-roster preservation.
All nine final attribution tests also passed on Python 3.14.

Canonical Python 3.13 mypy and Flake8 passed all 861 repository Python files;
typing policy passed on a disposable copy of that source/configuration. Explicit
Git source lists avoid ignored local environments and inaccessible older pytest
scratch directories reached by bare recursive checks on this workstation.
Public documentation, the 500-line file convention and schema mirror checks
passed. All 30 gallery images matched requested dimensions and contained visible
content. Geometry and synthetic images do not prove screen-reader quality.

Full-suite CI belongs to the pushed revision. The predecessor UX-04 PR's CI is
green. UX-05's Python 3.14 job initially printed all tests passing but exited
unsuccessfully; the rerun succeeded, and
[its complete CI run](https://github.com/berginj/PitchTracker/actions/runs/38637785446)
is now green. This does not substitute for the new revision's CI.

Manual checks remain: all five setup stages on the target rig, busy tooling
cancellation/recovery, real pitch-boundary attribution, Windows DPI at
125/150/200%, keyboard/screen-reader journeys, packaged roster persistence and
real historical session playback. Setup readiness permits estimated research
recording; neither these tests nor the screenshots grant physical accuracy
approval. UX-07 covers remaining surfaces; UX-08 owns full journey qualification.

## Review follow-up — 2026-10-15

The unavailable-Live page's Open Sessions action now navigates directly to
history without requiring a finalized Live recording. Paired pitch playback
rejects unequal encoded camera frame counts, including pitches in their shared
prefix; independently valid timestamp files do not establish paired support.

The UX-05 review fixes are integrated. ReviewService and the public controller
handoff accept both an optional recorded-player filter and requested pitch ID.
The candidate is filtered and checked before replacing the prior session,
decoder, player filter or UI selection. Failed handoffs keep their previous
context and existing recovery message. Preparation and history share the
configured recording root, and independent history remains available during
recording startup while the active directory stays blocked.

The focused workspace, review, player, attribution, mapping and session-command
suite passed 92 tests on Python 3.13. Regressions exercise the actual fallback
button, both unequal-count directions, and a requested pitch removed by the
recorded-player filter. Existing synthetic galleries describe the unchanged
layouts; the manual qualification requirements above remain pending.
