# PitchTracker documentation

Use the path that matches your task. You do not need to read the architecture
or validation documents before trying the simulator.

## Start here

- **I want to try the app without cameras:** [Quick Start](QUICK_START.md)
- **I operate a camera rig:** [Operator runbook](OPERATOR_RUNBOOK.md)
- **I am testing hardware:** [Testing Help Needed](TESTING_NEEDED.md)
- **I need to understand a term:** [Glossary](GLOSSARY.md)
- **I need help with a problem:** [Troubleshooting](user/TROUBLESHOOTING.md)
- **I want to contribute:** [Contributing](../CONTRIBUTING.md)
- **I need to report a security issue:** [Security policy](../SECURITY.md)

## Current sources of truth

These documents describe the current product. If an older document conflicts
with them, use these pages and open a documentation issue.

- [Current Status](CURRENT_STATUS.md) — release, test, and evidence state.
- [Roadmap](ROADMAP.md) — current open work and acceptance criteria.
- [Testing Help Needed](TESTING_NEEDED.md) — safe external testing tasks.
- [Setup Snapshot Requirements](SETUP_SNAPSHOT_REQUIREMENTS.md) — setup evidence
  and camera recommendation requirements.
- [Evidence-First Field Robustness](EVIDENCE_FIRST_FIELD_ROBUSTNESS.md) — what
  the system records and what it may claim.
- [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md) — the
  procedure for an accuracy claim.
- [Architecture](ARCHITECTURE_CURRENT_STATE.md) — service and agent boundaries.
- [PT-001–PT-015 Traceability](PT_001_015_TRACEABILITY.md) — implementation and
  automated-test evidence.

## User and operator guides

- [Installation](../README_INSTALL.md)
- [Quick Start](QUICK_START.md)
- [Operator daily-session runbook](OPERATOR_RUNBOOK.md)
- [FAQ](FAQ.md)
- [Troubleshooting](user/TROUBLESHOOTING.md)
- [Calibration tips](user/CALIBRATION_TIPS.md)
- [Setup Doctor](SETUP_DOCTOR.md)
- [Hardware profile](HARDWARE_PROFILE.md)
- [Camera reconnection](CAMERA_RECONNECTION.md)
- [Physical validation checklist](PHYSICAL_VALIDATION_EXECUTION_CHECKLIST.md)

## Developer guides

- [Requirements](../REQ.md)
- [Contributing](../CONTRIBUTING.md)
- [Testing and validation](TEST_SUITE_DOCUMENTATION.md)
- [Integration tests](INTEGRATION_TESTS.md)
- [Performance benchmarks](PERFORMANCE_BENCHMARKS.md)
- [Evidence contracts](evidence_contracts.md)
- [Decision replay architecture](DECISION_REPLAY_ARCHITECTURE.md)
- [ML training guide](ml/TRAINING.md)
- [Architecture decisions](decisions/0001-core-pipeline.md)

## Community and support

- [Support](../SUPPORT.md)
- [Security policy](../SECURITY.md)
- [GitHub feedback intake](GITHUB_FEEDBACK_INTAKE.md)

## Planning and historical context

- [Product strategy](PRODUCT_STRATEGY.md) is a strategy reference, not the
  current backlog.
- [Pilot program](PILOT_PROGRAM.md) is a pilot-design reference; launch status
  comes from [Current Status](CURRENT_STATUS.md).
- TAG and cloud documents are concept specifications, not shipped capability.
- [Archive](archive/) and [`../archive/`](../archive/) preserve historical
  plans, investigations, and point-in-time reports. Do not use their metrics or
  version numbers as current status.

## Documentation maintenance

When behavior changes:

1. Update the relevant contract or requirement.
2. Update [Current Status](CURRENT_STATUS.md) and [Roadmap](ROADMAP.md) when
   delivery status changes.
3. Add automated evidence to [PT traceability](PT_001_015_TRACEABILITY.md).
4. Preserve non-claim language for hardware results until physical validation.
5. Move superseded point-in-time reports to the archive instead of leaving two
   competing status sources.

Last reviewed: **2026-08-16**.
