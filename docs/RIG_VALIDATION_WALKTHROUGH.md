# Rig setup, calibration and quality-reference walkthrough

Complete one row at a time with the operator present. A missing measurement is
unavailable, not a pass. Preserve every run and failure. The first outcome is a
rig ready for controlled research recording; the second is an empirical quality
baseline; physical accuracy approval follows separate confirmation.

Start the supported guided workflow:

```powershell
python launcher.py --setup --backend uvc
```

Use `opencv` only for a rig configured for that backend. Use `sim` for rehearsal;
simulator results cannot validate the physical rig. Opening setup performs no
camera acquisition. Discovery, preview, board capture and checks are explicit
operator actions. Keep source/build, configurations and private media local.

## Before the first action

Record ball type, the two camera/lens identities, mount/baseline, intended
lighting and speed range, USB paths, measured calibration board dimensions,
independent speed reference, independently surveyed location reference and
optical timing reference. Record each reference's uncertainty, confidence basis,
calibration validity and raw export format. Do not invent instrument uncertainty
from a vendor name, a low fit residual or PitchTracker's own output.

Choose the intended physical capture mode and a recording destination with
sufficient free space. Check disk/writer readiness before recording; preserve
existing recordings and configs. Do not enable uploads.

## Discrete setup steps

| Step | Operator action | Evidence required before proceeding |
|---|---|---|
| 1 — Freeze the physical layout | Fix mounts, lens settings, baseline and the survey frame. Photograph/document the rig locally. | Camera/lens identities, baseline, mount and environment inventory. |
| 2 — Assign cameras | In Cameras, discover and explicitly assign distinct left/right devices. Preview and verify the physical side of each image. | Stable identities, correct sides and common field coverage. |
| 3 — Set capture mode | Select resolution/FPS/color mode and explicit controls. Adjust focus, exposure and gain. Sample/lock white balance if needed. | Requested and negotiated mode, verified control readbacks or an explicit unavailable state. |
| 4 — Warm and inspect | Warm the rig, then run Image checks. Repeat under intended load; inspect cadence, skew tails, drops, focus and overlap. | Saved check details with counts, timing source and p50/p95/p99 where available. Host pairing alone does not prove exposure synchronization. |
| 5 — Specify the board | Measure the printed square size in millimeters; verify columns/rows and board identity. | Actual board values and capture provenance. |
| 6 — Capture calibration poses | Capture at least ten distinct valid paired board poses, varying angle, depth and image coverage. Exclude failures explicitly. | Both original images and identities/timestamps for every retained pose. |
| 7 — Fit full metric calibration | Run full calibration or verify a compatible NPZ and adjacent identity record. Inspect residuals and both cameras' dimensions/transforms. | Full matrices, metric scale, quality checks and exact artifact hashes. Coarse alignment cannot replace this step. |
| 8 — Establish field coordinates | Capture surveyed targets; use at least three non-collinear fitting targets and a separate holdout. Click the same target in both views; enter measured X/Y/Z in feet. | Independent survey and fit/holdout identity. Holdouts never enter the fit. |
| 9 — Verify regions and publish | Draw each camera's lane/plate regions, check alignment/regions, revisit blockers in Ready and Finish setup. | Fit and holdout error within the existing 0.1 ft setup gate; saved completed rig revision, effective config and snapshot. |

Step 9 enables estimated research capture. It does not provide an error interval
or an accuracy approval. Any settings or rig change creates a new revision and
invalidates affected evidence.

## Controlled qualification before athlete field collection

| Step | Operator action | Evidence/outcome |
|---|---|---|
| 10 — Optical timing | Record independently timed pulses/coded fiducials and controlled motion after warm-up, in both cameras and across rows. Repeat at the intended exposure/FPS/load. | Shutter behavior, exposure duration, timestamp semantics and actual inter-camera exposure skew with uncertainty. |
| 11 — Static repeatability | Repeat independent holdouts at plate and near/middle/far depths and image edges across warmed sessions. Reinstall/recheck the rig in a separate run. | Signed XYZ errors by target/depth/session, bias and repeatability; survey uncertainty retained. Calibration/fit targets cannot substitute for holdouts. |
| 12 — Lifecycle and recording | Explicitly record a controlled target/motion session; exercise pause/stop/restart, reconnect and USB/load scenarios. End recording and inspect artifacts in Review. | Clean drain, videos and frame mappings, manifests, journal conservation, unavailable/rejected outcomes and recoverability. |
| 13 — Freeze the reference study | Choose tolerances, reference uncertainties, scope/strata, counts, exclusions and speed reference plane before collection. Save the v2 protocol and a shadow dataset. | Real device identities/certificates and exact rig/build/calibration/ROI/correction fingerprints. Blank values remain blockers. |
| 14 — Collect the shadow baseline | Collect the initial 100 independent attempts across at least three sessions for one ball/environment, spanning attainable speeds and plate regions. Retain every attempt and invalid reference. | Independent speed at the same plane as vision speed; independent plate X/Y at the actual plate plane. This starting count is diagnostic, not a confirmation power claim. |
| 15 — Establish quality references | Review → Tools → Measurement Validation: import cases/references, evaluate and save the study/report outside captured sessions. Inspect each stratum and session. | Bias, MAE/RMSE, tails, sample spread/covariance, reference uncertainty and rejected/unavailable rates. Restrict scope where data are insufficient. |
| 16 — Confirm independently | Freeze changes and collect a disjoint confirmation study under the locked protocol. Obtain collector and independent reviewer attestations. | Every physical-validation v2 gate, exact binding and signature must pass before an ACTIVE accuracy approval. Shadow data never becomes confirmation. |

## Interpreting measured variance

The v2 evaluator now includes `metrics.residual_spread` and
`metrics.residual_spread_by_stratum`. They report sample speed-error variance
in mph², speed-error standard deviation in mph, and a 2x2 plate X/Y residual
covariance in ft², using the sample denominator n − 1. Fewer than two paired
samples produce unavailable values. A short sample with zero observed variance
does not establish a zero-error instrument.

These are signed errors against independent references, conditional on accepted,
reference-valid results. Speed spread uses unassisted vision at the matched
reference plane; radar/manual/unknown-plane results cannot establish it.
Reference error remains included. Bias and rejection denominators remain
separate, and the report never promotes sample spread into physical prediction
uncertainty or grants a new approval. Group different environments, speeds,
depths and sessions separately before treating pooled statistics as a reference.

Near/mid-depth XYZ repeatability belongs in the static holdout record; it is not
a plate-plane measurement and must not be mislabeled as one in the v2 dataset.
Use a predeclared method and confidence basis for uncertainty bounds. Retain
raw and corrected results separately, and do not subtract reference noise merely
to make an acceptance gate pass.

## Next walkthrough action

Start with steps 1–3. Confirm the available camera pair, ball type, board and
independent reference instruments. Then use the saved workflow to progress one
check at a time. No physical step in this document is marked complete by a
software test or by opening the app.

See [Guided Setup](GUIDED_SETUP.md), [Desktop Measurement Research](MEASUREMENT_RESEARCH.md)
and [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md).
