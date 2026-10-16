# Pitch lifecycle

Status: current developer reference. Last reviewed: 2026-10-16.

PitchStateMachineV2 owns lifecycle state in
[app/pipeline/pitch_tracking_v2.py](../../app/pipeline/pitch_tracking_v2.py).
[PitchConfig, PitchPhase and PitchData](../../app/pipeline/pitch_snapshot.py)
define configuration, phases and callback snapshots.

## State and evidence

The phases are INACTIVE, RAMP_UP, ACTIVE, ENDING and FINALIZED.
Frame counts, detection gates and configured duration/observation requirements
control admission. Inspect the state machine for the exact transition conditions;
a state transition is not a physical-quality verdict.

- Buffer each camera frame before pitch admission for pre-roll. Retention is
  bounded by a timestamp window and a per-camera safety cap; it is not a promise
  of zero frame loss. Capture/recording diagnostics establish retained evidence.
- Stereo and ray observations collected during ramp-up are retained for a
  confirmed pitch. Rejected or too-short attempts retain their rejection outcome.
- Snapshots copy state-owned collections before callbacks. Locks protect state;
  callbacks and downstream analysis must not reach into its mutable buffers.
- Detection and frame times use monotonic nanoseconds. Fit or recording failure
  must not silently invent a valid pitch or rewrite its recorded attribution.

## Service ownership

The orchestrator forwards observations and wires callbacks. Recording owns
writers, timestamp mappings and manifests. Analysis owns finalized summaries
and optional comparison work. Accepted analysis drains before final journal
publication. Player attribution is bound at the pitch boundary and travels with
the captured pitch through delayed analysis.

See [runtime contracts](agent-contracts.md), the
[architecture overview](../ARCHITECTURE_CURRENT_STATE.md) and
[recording schema](../../MANIFEST_SCHEMA.md).
Tests under tests/ cover state transitions, ramp-up, pre-roll, callbacks and
concurrency; current CI is the validation source.

## Historical migration

The original V1/V2 comparisons and integration notes are indexed in
[the archive](../../archive/docs/ARCHIVE_INDEX.md). Their old line numbers,
pipeline_service.py wiring and blanket data-loss claims are historical.
