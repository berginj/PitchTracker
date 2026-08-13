# Hardware and Physical Validation Execution Checklist

**Last reviewed:** 2026-08-11
**Applies to:** v2.0.0 and current `main`

This checklist is a record-keeping tool for collecting evidence during physical
field testing. It does **not** claim any result. Each item records what was
done, what was observed, and what artifacts were captured.  No cell in this
checklist constitutes a validated accuracy claim until it passes the full
[Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md) and
receives an `ACTIVE` v2 approval with two independent trusted signatures.

---

## Pre-session evidence record

| Item | Recorded value / artifact hash | Date | Collector |
|---|---|---|---|
| Laptop hostname and OS build | | | |
| Python version (`python --version`) | | | |
| App commit hash (`git rev-parse HEAD`) | | | |
| Left camera serial | | | |
| Right camera serial | | | |
| Rig profile path and file hash | | | |
| Setup snapshot hash (from UI dashboard) | | | |
| Setup snapshot eligibility state | | | |
| Baseline measurement (ft) | | | |
| Calibration date and reprojection errors (px) | | | |
| Reference device identity | | | |
| Reference device calibration certificate hash | | | |
| Reference device calibration valid-until date | | | |
| Environment class (indoor/outdoor, lighting) | | | |
| Protocol document version in use | | | |
| Protocol hash (before first case) | | | |

---

## Camera qualification evidence

| Test | Result | Notes | Artifact |
|---|---|---|---|
| Both cameras detected by serial | ☐ observed / ☐ not observed | | |
| Achieved FPS (left) at target resolution | _____ fps | | |
| Achieved FPS (right) at target resolution | _____ fps | | |
| Exposure control readback matches set value | ☐ observed / ☐ not observed | | |
| Gain control readback matches set value | ☐ observed / ☐ not observed | | |
| Synchronization qualification passed | ☐ passed / ☐ failed / ☐ not run | | |
| Global-shutter timing optical test run | ☐ run / ☐ not run | | |
| Global-shutter timing test result | record raw observation | | |
| Unmatched frame count during 2-min capture | | | |

> Camera catalog recognition is a setup prerequisite. It does not prove
> physical global-shutter behavior. Timing/optical cases are required for any
> timing or shutter-type claim.

---

## Setup snapshot and calibration evidence

| Item | Recorded value | Notes |
|---|---|---|
| Intrinsics reprojection error — left (px) | | |
| Intrinsics reprojection error — right (px) | | |
| Stereo reprojection error (px) | | |
| Baseline estimate from calibration (ft) | | |
| Baseline measured (ft) | | |
| Baseline estimate vs measured delta | | Gate: ±2% |
| Field transform applied | ☐ yes / ☐ no | |
| ROI JSON hash | | |

---

## Physical accuracy comparison cases

Collect one row per evaluated case. Rejection and unavailability remain in the
denominator. Do not remove rows for bad outcomes.

| Case # | Stratum | PitchTracker raw value | PitchTracker corrected value | Reference reading | Reference uncertainty | Discrepancy | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | ☐ valid / ☐ rejected / ☐ unavailable |
| | | | | | | | ☐ valid / ☐ rejected / ☐ unavailable |
| | | | | | | | ☐ valid / ☐ rejected / ☐ unavailable |
| | | | | | | | ☐ valid / ☐ rejected / ☐ unavailable |
| | | | | | | | ☐ valid / ☐ rejected / ☐ unavailable |

Column definitions:
- **Stratum**: speed range, depth, location zone, or environment class.
- **PitchTracker raw value**: value before any correction, from `observations.json`.
- **PitchTracker corrected value**: value after applied correction policy; retain raw alongside it.
- **Reference reading**: independent reference device output.
- **Reference uncertainty**: declared uncertainty from reference device calibration.
- **Discrepancy**: |corrected − reference|; do not subtract reference uncertainty to improve appearance.
- **Status**: `valid` (meets sample and reference-quality gates), `rejected` (failed a gate — record why), `unavailable` (system did not produce output).

---

## Post-session artifacts

| Artifact | Location / hash | Captured |
|---|---|---|
| Session summary JSON | | ☐ yes / ☐ no |
| Pitch manifests (all pitches) | | ☐ yes / ☐ no |
| Setup snapshot JSON | | ☐ yes / ☐ no |
| Reference device raw export | | ☐ yes / ☐ no |
| Timing/global-shutter optical recording | | ☐ yes / ☐ no |
| Correction policy hash applied | | ☐ yes / ☐ no |
| Collector name and signature | | ☐ yes / ☐ no |

---

## Notes and open items

Record any deviations from the protocol, environmental anomalies, equipment
issues, or cases that were excluded and why.

```
[Free text — record here]
```

---

## Claim eligibility statement

> **This checklist records field evidence only.** Completing it does not
> constitute a `VALIDATED` accuracy claim. Claim eligibility requires all of
> the following to be satisfied and bound in a v2 approval artifact with two
> independent trusted signatures, an expiry date, and a lifecycle state of
> `ACTIVE`:
>
> - A locked and hashed v2 protocol authored before the first case.
> - A disjoint confirmation dataset (not used for any prior tuning).
> - Every independently valid case evaluated and in the denominator.
> - An independent reviewer distinct from the collector.
> - Runtime fingerprint and hash re-verification at claim time.
>
> See [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md)
> and [PT-001–PT-015 Traceability](PT_001_015_TRACEABILITY.md).
