# Measurement research acceptance ledger

Baseline: `main` at `e8287a9`. This change adds desktop research tooling and
addresses the eight October 5 software follow-ups. No issue is closed, physical
dataset collected, approval activated, or signed release published by this work.

## October software follow-ups

| Finding | Implementation | Regression evidence |
|---|---|---|
| Native/capture identity | Reject differing native indices; discard mismatched composed evidence | `test_uvc_native_probe.py`, `test_uvc_probe.py` |
| Manual focus versus autofocus | Use native auto-capability bit | `test_camera_capabilities.py` |
| Unknown focus presentation | Present observed autofocus independently of classification | desktop capability regressions |
| Release/tag binding | Verify embedded product version before publication | `test_installer_artifact.py` |
| Legacy ROI sides | Preserve side-specific ROIs for numeric IDs | `test_pipeline_cli_args.py` |
| Typing-policy bypass | Parse effective INI/TOML settings with inline comments | `test_typing_policy_configuration.py` |
| Export cancellation | Cancellable subprocess, retained Qt worker, atomic export | `test_export_cancellation.py`, `test_measurement_desktop.py`, `test_tooling_cancellation.py` |
| Measurement labels | Render durable enum values | desktop measurement-status regressions |

## Existing correctness issues

September/October fixes already implement these directions. Reconcile the
original acceptance criteria against software and operator evidence separately.

| Issue | Existing software evidence | Remaining acceptance |
|---|---|---|
| #34 timing | Capture/timing contracts distinguish receipt from acquisition | Optical semantics, skew and rig envelope |
| #35 distortion | Stereo uncertainty/geometry regressions preserve calibrated pixels | Surveyed holdouts and location confirmation |
| #36 drag | `test_trajectory_physics.py`; drag seed, weighting and fit eligibility | Original reproduction and field bias |
| #37 swept strike | `test_strike_zone_accuracy.py`, `test_strike_uncertainty.py` | Independent boundary/gap/plate evidence |
| #38 uncertainty | Stereo/strike uncertainty and fit failure tests | Physical error budget and operating envelope |
| #39 speed | `test_speed_provenance.py`; separate vision/external records and exports | Independent matching-plane/time comparison |
| #40 model limits | `test_trajectory_model_envelope.py`; plate error, noise, timing, prior sensitivity | Representative shadow and confirmation data |

The expanded synthetic model sweep is implemented; the old 12-case benchmark
finding is historical. Synthetic success does not establish physical accuracy.

## Research and external gates

- Desktop research: inspection, v2 editing/evaluation, source preservation,
  new-file exports and cancellation. Tests: `test_research_tooling.py`,
  `test_measurement_desktop.py`.
- #9: actual camera/mode/control/timing/USB/recovery qualification remains
  operator-run, bound to exact rig/software and complete denominators.
- #10: collect shadow baseline, then lock protocol and collect disjoint
  confirmation; verify raw references and obtain independent signatures.
- #11: sign and qualify install/update/uninstall/data retention on clean Windows.
- Public `v2.0.0` has no installer at this baseline; publication retains its gates.

Priority: one developer, local desktop measurement research. Facility pilots
follow evidence. Cloud/TAG, ML defaults, ray promotion and dashboards remain
conditional. Automated results and local limitations are recorded in
[the dated validation record](RESEARCH_VALIDATION_2026_10_10.md).
