# GitHub Feedback and Validation Intake

**Last reviewed:** 2026-07-22
**Applies to:** `v2.0.0` and current `main`

Use structured GitHub issues for setup friction, hardware compatibility,
validation results, repeatable bugs, and documentation gaps.

## Forms

| Form | Use for | Labels |
|---|---|---|
| Pilot Feedback | Operator experience, workflow friction, bugs, and suggestions | `pilot-feedback`, `needs-triage` |
| Validation Report | Installer, camera, capture, setup recovery, speed/location, and replay tests | `validation`, `needs-triage` |

- [Open Pilot Feedback](https://github.com/berginj/PitchTracker/issues/new?template=pilot_feedback.yml)
- [Open Validation Report](https://github.com/berginj/PitchTracker/issues/new?template=validation_report.yml)

Before reporting, read [TESTING_NEEDED.md](TESTING_NEEDED.md).

## Required evidence quality

- Identify the exact version or commit.
- Provide counts and denominators, including rejected and unmatched attempts.
- Describe the hardware, OS, USB path, environment, and reference device.
- Report unavailable information explicitly.
- Distinguish observed facts from interpretation.
- For physical accuracy, lock the protocol and thresholds before confirmation.

Do not upload athlete video, identifying information, private facility data,
secrets, trust keys, raw recordings, or unreviewed logs. Use snapshot IDs,
fingerprints, hashes, and anonymized summaries.

## Triage

Maintainers should:

1. Review `needs-triage` issues.
2. Separate software defects, compatibility observations, workflow feedback, and
   claim-bearing validation evidence.
3. Add subsystem and `pilot-blocker` labels where appropriate.
4. Request missing denominators or protocol details before interpreting results.
5. Update [ROADMAP.md](ROADMAP.md) only when evidence changes priority or scope.

A camera compatibility report may inform the hardware matrix without granting a
physical accuracy approval.
