# Canonical Setup Snapshot Requirements

## Requirement

Every completed physical setup must produce one immutable
`setup_system_snapshot.v2` artifact. The snapshot is the authoritative inventory
of the configuration that was actually measured. A wizard completion flag,
calibration residual, catalog match, or plausible pitch result is not equivalent
to a validated configuration.

Setup may create an operational profile when optional inventory probes are
unavailable, but physical accuracy claims fail closed unless the snapshot is
complete, its fingerprint and artifact hashes verify, an exact active physical
validation v2 approval exists, and current session preflight passes.

The snapshot is written atomically and content-addressed. Its SHA-256 is included
in the measurement-pipeline fingerprint, so an approval cannot be reused after
any captured setup fact changes.

## Required inventory

The snapshot records:

- Rig ID/revision, backend, site-facing camera serial assignment, and timestamps.
- Application version, source revision, dirty-worktree state, Python and critical
  dependency versions.
- Operating system, architecture, processor, and discoverable driver/USB data.
- Camera serial, friendly name, model, catalog recognition, global-shutter and
  synchronization capability, firmware/driver/USB identity, supported modes,
  controls, and recommendation provenance.
- Requested and negotiated mode for both cameras and physical control readback.
- Capture frame counts, achieved rates, drops, unmatched outcomes, jitter, pair
  skew tails, denominators, and the qualification assessment.
- Calibration, ROI, field transform, fixture provenance, holdout status, and
  content hashes.
- Detector configuration/model, pairing and association policy, tracking,
  trajectory mode, correction policy, and their versions/hashes.
- Artifact inventory, unavailable probes with explicit reasons, approval IDs,
  completeness blockers, and the canonical snapshot fingerprint.

Missing information is represented as unavailable and never replaced with an
assumption or zero. The normal setup UI shows the recommendation, health state,
and primary corrective action; the full inventory remains available in the
persisted snapshot and advanced diagnostics.

## Camera recommendation and preselection

When cameras are displayed, setup preselects exactly one recommended left/right
pair without removing manual override:

1. Prefer the exact connected pair and sides from the newest non-expired ACTIVE,
   claim-ready physical validation v2 profile. Runtime must still re-verify its
   signatures and artifact bindings.
2. Otherwise rank recognized global-shutter pairs by support for the requested
   mode, hardware synchronization, common modes, required controls, compatible
   throughput, and deterministic hardware identity.
3. If fewer than two recognized global-shutter cameras are present, make no
   production recommendation and explain why.

The recommendation reason and provenance are stored in the setup snapshot. An
operator must explicitly apply or change the assignment; preselection does not
silently persist hardware state.

## Eligibility gate

`validated_configuration_ready` is true only when all of the following hold:

1. Snapshot structure and required values are complete.
2. Snapshot fingerprint and all required artifact hashes verify.
3. Capture qualification, control readback, production calibration, and field
   alignment pass.
4. The exact measurement pipeline has an active physical validation v2 approval.
5. Runtime configuration and environment match the approved fingerprint.
6. Current session preflight and the individual pitch are not degraded.

Until then, results remain `ESTIMATED`, `DEGRADED`, `UNAVAILABLE`, or `REJECTED`.
