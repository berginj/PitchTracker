# Pending work and GitHub response audit — 2026-10-05

Reviewed local `main` at `e1df60d` with a clean worktree, current GitHub issues,
all 22 pull requests and their reviews/inline threads, repository issue comments,
recent CI runs, release assets, and the current status/roadmap/validation records.
GitHub Discussions is disabled and contains no discussions. This audit changes
documentation and responses, not runtime code or physical qualification status.

## Current state

- Ten open issues: #9–#11 and #34–#40. No open pull requests.
- Latest main CI [run 37162376775](https://github.com/berginj/PitchTracker/actions/runs/37162376775)
  completed successfully for `e1df60d`.
- October consolidation/remediation is implemented; prior finding lists are
  historical evidence, not an additional unimplemented backlog.
- Public `v2.0.0` still has no release assets. The fresh installer documented in
  [the remediation record](REMEDIATION_VALIDATION_2026_10_03.md) is unsigned and
  has not completed clean-machine install/update/uninstall qualification.
- No independently reviewed physical accuracy confirmation is approved.
- No production Python TODO/FIXME markers were found in the searched active
  source; this does not imply all defects or planned work are complete.

## Software follow-ups confirmed in current source

These eight findings remain valid despite their PRs being closed. Each original
review thread now has a direct response. They require focused implementation and
regressions before resolution; none was fixed as part of this audit.

| Priority | Request | Remaining action |
|---|---|---|
| P1 | [Native/capture identity, PR #31](https://github.com/berginj/PitchTracker/pull/31#discussion_r3793399091) | Align the friendly-name-resolved DirectShow index with the capture target, or reject mismatched native evidence. Cover differing enumeration orders. |
| P2 | [Autofocus capability, PR #31](https://github.com/berginj/PitchTracker/pull/31#discussion_r3793399093) | Distinguish successful manual focus queries from the DirectShow autofocus capability flag. Cover manual-only devices. |
| P2 | [Unknown focus presentation, PR #31](https://github.com/berginj/PitchTracker/pull/31#discussion_r3793399095) | Present true/false/unknown observed autofocus capability instead of inferring it from webcam/industrial classification. |
| P2 | [Release version binding, PR #22](https://github.com/berginj/PitchTracker/pull/22#discussion_r3630569172) | Refuse an installer whose version differs from the requested release tag before publication. A matching checksum alone is insufficient. |
| P2 | [Legacy lane ROI mapping, PR #21](https://github.com/berginj/PitchTracker/pull/21#discussion_r3630269462) | Preserve saved left/right lane entries when the OpenCV CLI defaults to runtime IDs 0/1. |
| P2 | [Typing policy bypass, PR #30](https://github.com/berginj/PitchTracker/pull/30#discussion_r3793296752) | Detect commented `ignore_errors = true` settings through configuration-aware parsing/checking. |
| P2 | [Export cancellation, PR #32](https://github.com/berginj/PitchTracker/pull/32#discussion_r3793658824) | Remove the nonfunctional Cancel control or propagate cancellation through training-report and ZIP exports. |
| P2 | [Measurement status labels, PR #29](https://github.com/berginj/PitchTracker/pull/29#discussion_r3793071623) | Render durable enum values in the UI, rather than `MeasurementStatus.REJECTED`-style implementation names. |

## Open issue reconciliation

The seven September correctness issues have committed software remediation
described in [DEVELOPMENT_PLAN.md](../../DEVELOPMENT_PLAN.md),
[TRAJECTORY_PHYSICS.md](../TRAJECTORY_PHYSICS.md), and the September/October
validation records. They had zero comments before this audit. Each now has an
implementation/evidence/remaining-work response. Keep them open until each
acceptance criterion is explicitly mapped to code, regressions, and any required
physical evidence; status documents alone are not closure evidence.

| Issue | Implemented software direction | Remaining decision/evidence |
|---|---|---|
| [#34](https://github.com/berginj/PitchTracker/issues/34) Timing provenance | Separate receipt health from acquisition timing; persist provenance/uncertainty. | Reconcile acceptance tests; qualify optical timing and permitted rig skew. |
| [#35](https://github.com/berginj/PitchTracker/issues/35) Distortion | Undistort once before calibrated matching/triangulation; preserve raw pixels/covariance. | Reconcile acceptance and regression evidence; physical location confirmation. |
| [#36](https://github.com/berginj/PitchTracker/issues/36) Drag bias | Treat default drag as a seed, whiten residuals, reject ineligible fits. | Reconcile reproduction/regressions and eligibility criteria. |
| [#37](https://github.com/berginj/PitchTracker/issues/37) Swept strike | Continuous swept-sphere geometry; unsupported gaps/coverage unavailable. | Reconcile boundary/gap regressions and physical plate evidence. |
| [#38](https://github.com/berginj/PitchTracker/issues/38) Uncertainty | Preserve fit eligibility and explicit unavailable physical uncertainty. | Reconcile failure/uncertainty acceptance; no physical error interval established. |
| [#39](https://github.com/berginj/PitchTracker/issues/39) Speed provenance | Keep vision/external speed, estimator, timestamp, reference location distinct; preserve exports. | Reconcile durable/UI acceptance; independent matching-plane comparison. |
| [#40](https://github.com/berginj/PitchTracker/issues/40) Model limits | Document omitted transverse physics; synthetic sensitivity sweep; spin unavailable. | Reconcile model-limit acceptance; representative shadow/confirmation evidence and operating envelope. |

## Operator and release gates

1. [#9 — Camera and setup qualification](https://github.com/berginj/PitchTracker/issues/9):
   real global-shutter camera pairs, controls/modes, optical acquisition timing,
   USB load, poor-setup recovery, disconnect/reconnect, backend switches, and
   repeated setup/launcher close. Record identifiers, denominators, timing,
   queue/pre-roll telemetry, and exact rig/software/snapshot provenance.
2. [#10 — Independent physical confirmation](https://github.com/berginj/PitchTracker/issues/10):
   lock protocol/thresholds/strata/exclusions/sample counts before a disjoint
   confirmation dataset; retain all attempts; report speed/location errors and
   reference uncertainty; obtain collector and independent-reviewer signatures.
3. [#11 — Signed clean-machine installer](https://github.com/berginj/PitchTracker/issues/11):
   sign the intended artifact and test standard-user install, launch, setup,
   simulator, update, uninstall/reinstall, and sentinel operator-data retention
   across the Windows matrix. Bind results to exact hashes. Publish only after
   applicable release gates pass, including release-helper version binding.
4. Use qualifying reports to publish a hardware matrix and operating envelope,
   then run controlled facility pilots with measured setup time, rejection rate,
   intervention, and repeatability. Follow [the pilot checklist](../CONTROLLED_PILOT_CHECKLIST.md).

## Response coverage

Posted 30 responses through the connected GitHub tools:

- 18 direct replies to every previously unanswered unresolved inline review
  thread across PRs #2, #6, #8, #21, #22, #29–#33. Ten describe current fixes or
  clarified behavior; eight acknowledge remaining software work above.
- Ten status comments on every open issue (#9–#11 and #34–#40).
- A completion acknowledgment to the contributor recommendation on closed #18.
- A current status correction on closed #16, whose previous comment still said
  implementation was in progress; its three PR #31 follow-ups remain explicit.

Four other review threads were already marked resolved (one on #4, three on
#23). No additional substantive requests were found in review submission bodies.
Issues and thread resolution state were preserved. A reply records disposition;
it does not mean the underlying request has been implemented or validated.

## Deferred work and branch history

- Ray-mode promotion requires separate confirmation; keep `stereo_3d` primary.
- ML default expansion requires representative labeled data and regression gates.
- TAG/cloud integration remains conditional on partnership scope, privacy review,
  and dedicated implementation issues; concept-document checklists are not an
  authorized active sprint backlog.
- Broader EventBus/adaptive queue/calibration UI work and new dashboards remain
  evidence-driven deferrals. Preserve production queue/pre-roll defaults pending
  telemetry.
- Remote branch history includes the old development plan, production-readiness
  review, and Python 3.9 compatibility proposals. The
  [consolidation review](BRANCH_CONSOLIDATION_2026_10_02.md) and subsequent
  validation records document incorporation/rejection decisions. They are not
  pending wholesale merges. No branches or user artifacts were deleted.

Suggested order: fix identity/evidence gaps and remaining software reviews,
reconcile #34–#40 acceptance, execute camera/shadow and clean-machine gates,
collect independent confirmation, then publish evidence-backed release/support
claims. Continue mypy, suppression-policy, schema, lint, file-length, docs, and
focused changed-area checks throughout.
