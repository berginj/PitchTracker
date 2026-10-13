# Measurement research acceptance ledger

Initial research baseline: `main` at `e8287a9`. Desktop research tooling and the
eight October software follow-ups are implemented. Acceptance reconciliation
against `6b4bdd5` is recorded in
[the October 12 closeout](PLATFORM_AND_ISSUE_CLOSEOUT_2026_10_12.md).
Physical collection, accuracy approval and signed release qualification remain
separate from software issue completion.

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

The original checklists have been reconciled against code, fresh regression
checks and operator evidence requirements. Criterion numbers below refer to
those original checklists; incomplete physical/conditional gates remain open.

| Issue | Existing software evidence | Remaining acceptance |
|---|---|---|
| #34 timing | Criteria 1–3/5; receipt/exposure, clock/uncertainty/epoch checks | 4/6: verified rig timing model, optical procedure and permitted skew |
| #35 distortion | Criteria 1–4; raw/ideal coordinates, covariance and accepted-but-wrong old gate control | 5: physical pipeline/artifact revalidation under #10 |
| #36 drag | Criteria 1/3–7; exact 60 mph reproduction, independent truth, whitening, seed/prior sweep and identifiability | 2: a declared physical model for any opt-in prior |
| #37 swept strike | All six software criteria; phase/FPS/speed/radius/miss/gap/uncertainty checks | Closed as completed; physical location confirmation remains #10 |
| #38 uncertainty | Criteria 1/2/4/5/7; unavailable prediction error, heuristic score, all failure gates | 3/6: physical uncertainty synthesis if introduced and empirical interval coverage |
| #39 speed | All six provenance criteria; cropped/manual/radar, durable fields and independent matching-plane validation | Closed as completed; physical matched-plane comparison remains #10 |
| #40 model limits | Criteria 1/2/4/6; lift/control/cropped-window bias, stereo default, unavailable RPM | 3/5/7: physical envelope/model, any future movement baseline and expanded-claim confirmation |

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
