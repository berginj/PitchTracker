# PitchTracker Documentation

This index distinguishes current sources of truth from historical or exploratory
material. If an active guide conflicts with the status or roadmap, use the
documents in the first section and open a documentation issue.

## Current sources of truth

- [CURRENT_STATUS.md](CURRENT_STATUS.md) — shipped software, release state, and
  evidence boundary.
- [ROADMAP.md](ROADMAP.md) — canonical open work and acceptance criteria.
- [TESTING_NEEDED.md](TESTING_NEEDED.md) — how external testers can help safely.
- [SETUP_SNAPSHOT_REQUIREMENTS.md](SETUP_SNAPSHOT_REQUIREMENTS.md) — validated
  configuration inventory and camera recommendation requirements.
- [EVIDENCE_FIRST_FIELD_ROBUSTNESS.md](EVIDENCE_FIRST_FIELD_ROBUSTNESS.md) —
  measurement evidence model.
- [PHYSICAL_VALIDATION_PROTOCOL_V2.md](PHYSICAL_VALIDATION_PROTOCOL_V2.md) —
  confirmation protocol and non-claim boundary.
- [PT_001_015_TRACEABILITY.md](PT_001_015_TRACEABILITY.md) — implementation and
  automated-test traceability.
- [ARCHITECTURE_CURRENT_STATE.md](ARCHITECTURE_CURRENT_STATE.md) — current service
  and agent boundaries.

## User and operator guides

- [QUICK_START.md](QUICK_START.md)
- [FAQ.md](FAQ.md)
- [user/TROUBLESHOOTING.md](user/TROUBLESHOOTING.md)
- [user/CALIBRATION_TIPS.md](user/CALIBRATION_TIPS.md)
- [SETUP_DOCTOR.md](SETUP_DOCTOR.md)
- [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)
- [CALIBRATION_TROUBLESHOOTING.md](CALIBRATION_TROUBLESHOOTING.md)
- [CAMERA_RECONNECTION.md](CAMERA_RECONNECTION.md)

## Developer guides

- [../CONTRIBUTING.md](../CONTRIBUTING.md)
- [../REQ.md](../REQ.md)
- [decisions/0001-core-pipeline.md](decisions/0001-core-pipeline.md)
- [DECISION_REPLAY_ARCHITECTURE.md](DECISION_REPLAY_ARCHITECTURE.md)
- [evidence_contracts.md](evidence_contracts.md)
- [TEST_SUITE_DOCUMENTATION.md](TEST_SUITE_DOCUMENTATION.md)
- [INTEGRATION_TESTS.md](INTEGRATION_TESTS.md)
- [PERFORMANCE_BENCHMARKS.md](PERFORMANCE_BENCHMARKS.md)

## Planning and context

- [PRODUCT_STRATEGY.md](PRODUCT_STRATEGY.md) remains a strategy framework; its
  dated task tables are not the current backlog.
- [PILOT_PROGRAM.md](PILOT_PROGRAM.md) remains a pilot-design reference; launch
  status comes from `CURRENT_STATUS.md`.
- `core_pipeline_workback_plan.md` and `implementation_plan.md` are superseded by
  ADR-0001, the PT/AR traceability record, and `ROADMAP.md`.
- TAG documents are partnership concepts until an agreement and implementation
  issue explicitly activate them.

## Historical material

- [archive/](archive/) and [`../archive/`](../archive/) preserve completed plans,
  investigations, session reports, and superseded status documents.
- Historical metrics, version numbers, and readiness claims must not be copied
  into current release communication without revalidation.

## Documentation maintenance

When changing behavior:

1. Update the relevant requirement or contract.
2. Update `CURRENT_STATUS.md` and `ROADMAP.md` if delivery status changes.
3. Add automated evidence to `PT_001_015_TRACEABILITY.md` where applicable.
4. Preserve non-claim language for hardware results until physical validation.
5. Move superseded point-in-time reports to an archive instead of leaving two
   competing status sources.

Last reviewed: **2026-07-21**.
