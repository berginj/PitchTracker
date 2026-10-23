# Guided setup

Setup is designed for repeated local rig research. Every visit follows five
stages with saved values prefilled. Valid edits save immediately; there is no
separate Save button. Changes mark their dependent checks incomplete.

Start directly with `python launcher.py --setup --backend uvc`. The
[rig validation walkthrough](RIG_VALIDATION_WALKTHROUGH.md) breaks calibration,
physical qualification and independent reference collection into discrete steps.

## Operator workflow

1. **Cameras:** choose a saved rig or unfinished setup. Discover devices,
   explicitly use a distinct left/right pair, and set the capture mode and
   controls. Preview is an explicit action. If color capture samples white
   balance, use the observed locked value and rerun image checks.
   Gain uses the camera's native device units, which may exceed 30; use its
   reported range and check readback. The configuration accepts 0–65535, but
   that does not establish which values the connected camera supports.
   A native query confirming that focus control is unsupported can establish
   autofocus absence for a manual lens. A failed or unavailable query cannot;
   image sharpness must still pass separately.
   For manual lenses, choose **Focus cameras in large view**. Select one camera,
   use Fit or 100%–400% zoom, and drag to inspect the board. **Start live preview**
   opens the cameras once. Double-click the board to select the measured patch.
   Looking at the front of the lens, select **Test clockwise** or
   **Test counterclockwise** before a small turn, then hold still for a second.
   Relative feedback reports sharper, softer/reverse, or no clear change; it
   cannot infer an absolute turn direction from a still image. Washed-out/dark
   patches and stale frames do not establish a useful comparison. The stream
   retains only the latest display frames and saves no calibration evidence.
   Stop or close drains the supervised worker; stalls and the ten-minute limit
   require an explicit restart. Scores do not pass calibration. After moving either lens,
   select **I adjusted the lens / focus**, then rerun the affected checks.
2. **Image checks:** keep the rig fixed and run the combined checks. Review
   pairing/cadence, focus, controls, overlap, and coarse alignment. Details
   retain negotiated modes, timing tails, denominators, and recommendations.
3. **Calibration:** check a compatible saved full calibration, import a local
   NPZ with its adjacent .identity.json, or capture at least ten distinct
   ChArUco board pairs and run full calibration. Confirm the measured square
   size in millimeters. Vary board position, angle, and depth.
4. **Field and regions:** capture images of surveyed targets. Add at least
   three fitting targets and one separate holdout. Select each target row,
   click the same target in both views, and enter measured field X/Y/Z in feet.
   Mark holdout rows before checking alignment. The holdout is excluded from
   fitting. Draw lane and plate regions separately for both cameras, then
   check regions. Blank survey coordinates remain unavailable.
5. **Ready:** resolve the displayed blockers and Finish setup. A passing
   configuration enables research recording with estimated measurements.

Use Details for full evidence. Going backward displays saved state without
opening cameras again. Cancellation and closure wait for workers to exit.

## Saved configuration and recovery

Working state is stored under calibration/setups. Configuration and captured
images use content-addressed files; state.json is atomically replaced after its
referenced files exist. Invalid values or failed writes leave the previous
durable state intact and prevent completion until corrected.

Completed revisions under calibration/rigs contain effective_config.yaml,
stereo_calibration.npz, its identity record, roi.json, target images, the field
transform and setup snapshot. Changes produce a new completed profile and keep
the earlier revision. Existing global calibration and configuration files are
copied only through explicit legacy import and remain unchanged.

Rig settings belong to Setup. Coaching presents them read-only with Open setup;
session settings, including trajectory compute selection, remain separate.
Recording admission checks pending edits even
when capture was started earlier. An active recording prevents edits and setup
capture; idle runtime capture is drained before changing settings or acquiring
setup images.

Unchanged settings append a fresh preflight report without replacing their
approved snapshot. A new measurement revision does not copy an accuracy approval.
Runtime also verifies the running source/build identity against approved
provenance. Frozen GUI and worker artifacts carry build_identity.json.

## Quality boundaries

Coarse targetless alignment does not provide metric scale. A full calibration
needs compatible camera identities, image dimensions/transforms, board settings,
finite matrices, and passing residual checks. Imports without that provenance
remain diagnostic until full calibration establishes the missing evidence.

The existing field gate is 0.1 ft for both fit residual and holdout error.
It is a setup check, not a physical accuracy interval. The holdout cannot reuse
a fitting observation. Pixels are image coordinates; field coordinates are feet.

Pairing health does not prove optical exposure timing. Independently validated
accuracy remains subject to camera qualification, disjoint physical confirmation,
and trusted independent approval.

## Validation

The [October 11 validation record](review/GUIDED_SETUP_VALIDATION_2026_10_11.md)
records the supported-runtime test results and remaining manual checks.

Automated coverage includes fresh setup publication, synthetic image checks,
calibrated target triangulation, holdout failures, regions, atomic saves,
stale-result rejection, revision preservation, admission guards, desktop actions,
and calibration output isolation.

Manual validation on the intended rig must confirm actual negotiated modes,
control readback, left/right identity, target selection, region overlays,
cancel/close and reconnect behavior, and persistence after restarting the app.
Clean Windows qualification must also verify installed writable paths and
bundled build identity.
