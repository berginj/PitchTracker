# Controlled facility pilot: evidence gates

Prepared 2026-09-08. No physical or clean-machine checks below are claimed as
completed by software tests. A trained operator controls camera operation.

## Before capture

- Record the exact commit/bundle hash, Windows/driver versions, rig revision,
  serials, USB paths, calibration/field-transform hashes, negotiated modes,
  and verified control readbacks.
- Use a fixed rig and independent calibrated reference. Specify the same speed
  reference plane for both systems. Unspecified manual speed and radar-assisted
  estimates are not independent vision validation.
- Qualify optical timing at the relevant speed, exposure, and load. Identical
  host receipt timestamps do not prove exposure synchronization. Preserve
  timing source, clock domain, semantics, uncertainty, and evidence ID.
- Keep unverified results estimated; no automatic accuracy promotion.

## Engineering shadow run

- Cover intended speeds, ball sizes, image regions, track windows, lighting,
  blur, baseline, and representative transverse movement.
- Exercise disconnect/reconnect, USB contention, missed detections, interrupted
  analysis, pause/stop/restart, disk-write failures, and recovery.
- Retain every attempt and outcome/reason. Record queue age, handler latency
  p95/sample count, drops, actual pre-roll duration/bytes, achieved FPS,
  unmatched counts, and end-to-end operator wait.
- Compare vision speed at the matched location and plate location against the
  reference. Report accepted-case bias/MAE/tail errors with rejected/unavailable
  rates and reference uncertainty. Inspect short, low-residual arcs for bias.
- Use shadow data for proposed operating limits and fixes, not an accuracy
  approval. Freeze corrected software/configuration before confirmation.

## Independent confirmation

- Lock the v2 protocol, scope, strata, sample counts, exclusions, uncertainty,
  and thresholds before confirmation capture.
- Use a separate dataset, not tuning data. Bind results to exact hardware,
  software, calibration, snapshot, and correction-policy fingerprints.
- Require every threshold/denominator check and collector/independent-reviewer
  signatures. Failed strata restrict the envelope; never silently exclude them.
- Follow [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md).

## Clean Windows installer gate

- Without a development checkout/Python, test install, first launch, simulator,
  setup entry/cancel/re-entry, recording/review, uninstall, and reinstall.
  Any camera checks must be explicitly operator-initiated.
- Confirm `PitchTrackerWorker.exe` ships beside `PitchTracker.exe`. Probe,
  setup, tooling, and fitting must not reopen the GUI or flash console windows.
- Test failed/stalled workers, bounded stop, and a successful subsequent task.
- Check that private recordings, profiles, and runtime configs are absent from
  the bundle. Record signing/security warnings and final bundle provenance.
- Do not publish an installer or accuracy claim until applicable gates pass.
