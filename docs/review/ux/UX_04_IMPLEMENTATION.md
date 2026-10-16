# UX-04: Live pitch feedback

**Reviewed:** 2026-10-14. **Scope:** UX-04 in the
[workspace plan](../../UX_WORKSPACE_PLAN.md).
[Roadmap](../../ROADMAP.md) owns delivery status.

Live now opens Latest Pitch with recorded speed, visible source/reference,
result, measurement status and plate location ahead of the camera preview.
The preview shrinks and resizes with mouse or keyboard. Session Trends and
Games retain their existing behavior and have deliberate scrolling layouts.

## Delivered experience

- The compact toolbar shows session pitch count and tracking status. The
  workspace header retains session identity and recording controls. Duplicate
  session panels and the empty legacy control bar are hidden in hosted Live.
- Latest Pitch uses a split view with feedback first and preview second. At
  800x600, speed units, provenance, result and location remain readable; recent
  pitches and secondary details scroll. The previous 800x600 video minimum is gone.
- Preview selection persists across Latest Pitch, Session Trends and Games.
  The splitter supports Left/Right keys and exposes an accessible name/description.
- Speed provenance follows the recorded selected measurement; it does not
  automatically prefer an external measurement over vision. Unknown legacy source
  or reference stays explicitly unavailable.
- Unavailable/rejected pitches show their recorded status and reason without a
  numeric coaching-speed claim or normal strike/ball marker. Nonfinite locations
  and unavailable strike calls clear the marker. Eligible coordinates retain feet.
- Unvalidated movement stays unavailable. Ball/strike outcomes use a neutral
  treatment, separate from operational errors. No new spin/break claims or
  coaching algorithms are introduced.
- The last ten recent pitches show newest first, including ineligible evidence.
  Updates preserve an existing selection and scroll position; unchanged lists
  are not rebuilt. Incoming data does not switch views or request focus.
- Advanced Tools retains tracking diagnostics, detector trials, lane/rig controls
  and the existing fatigue research indicator. Latest pitch details exposes the
  recorded fields and raw displacement without upgrading their physical meaning.
  Service admission and pending-command guards remain enforced.

Applicable instructions: [root specification](../../../agents.md),
[shared UI](../../../ui/AGENTS.md), [coaching](../../../ui/coaching/AGENTS.md)
and [themes](../../../ui/themes/AGENTS.md). Existing public widget class names,
mode indexes, pitch contracts and service interfaces remain compatible. This
package changes presentation; no new runtime domain owner or durable schema is added.

## Evidence and validation

The [actual-widget gallery](ux04/index.html) contains 54 synthetic captures:
three views, six states and three sizes (1366x768, 1024x768 and 800x600).
States include empty, measured, unavailable, rejected, degraded and operation
error. The [manifest](ux04/manifest.json) records geometry and source identity.
Inputs are synthetic and configuration disposable; the script never starts
capture, recording, private-data loading or processing. Compare the
[UX-03 gallery](ux03/index.html) for the previous density and large preview.

Tests exercise viewport and wrapped-text reachability, visible provenance,
measurement/call gating, nonfinite locations, newest-ten history, stable selection,
camera selection, keyboard resizing and Advanced Tools admission. Source GUI
smoke and workspace command/shutdown regressions preserve the UX-03 boundary.
Automated geometry and synthetic rendering do not establish manual usability.

Recorded test runs overlap and must not be added together:

| Check | Result |
|---|---|
| Initial focused layout/measurement checks | 18 passed |
| Workspace/coaching/measurement/theme/accessibility/source-smoke regression group | 90 passed, 1 packaged-build skip |
| Final viewport/state/provenance checks, Python 3.13 | 19 passed |
| Canonical Python 3.13 mypy across coaching and evidence tools | Passed, 41 source files |
| Repository source Flake8, public docs, file length and schema mirror | Passed |
| Synthetic gallery dimensions and nonblank rendering | Passed, 54 captures |

The previous pushed revision's CI failed on three Flake8 formatting violations
in `scripts/render_ux_prototype.py`. This change fixes those violations and
checks repository source lint without the ignored local vendor directories.
Third-party deprecation warnings did not fail tests. Packaged smoke needs
`PITCHTRACKER_PACKAGED_DIR`; no packaged build was supplied.

The full repository test suite and physical qualification remain UX-08/release
gates. Windows DPI at 125%, 150% and 200%, screen-reader/keyboard journeys and
real-rig observation remain operator-run checks. These changes do not grant
physical speed/location or movement approval.

## Next work

UX-05 connects finalized-session and pitch selection directly to Sessions,
prioritizes playback and corresponding metrics, and preserves degraded/legacy
artifact handling. Player attribution and filtering remain UX-06.
