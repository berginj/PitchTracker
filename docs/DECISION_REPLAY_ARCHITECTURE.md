# Decision Replay Architecture

PitchTracker now preserves the detector-to-triangulation decision chain in a
session-scoped evidence journal. The legacy observation and
`StereoFrameProcessedEvent` APIs remain available; the new evidence events are
parallel contracts and do not change the default trajectory or association mode.

## Conservation invariants

Every frame offered to `DetectionThreadPool` receives one opportunity ID and
exactly one terminal outcome. Terminal outcomes include ordinary completion,
input-queue displacement, detector failure, result-queue displacement, result
processing failure, and stop-time cancellation. Late worker completion is
de-duplicated. Runtime diagnostics expose offered, terminal, outstanding, and
per-outcome counts without clamping an inconsistent rate.

Every successfully processed camera frame then receives exactly one terminal
pairing outcome. A frame is either part of one `PAIRED` outcome or has one
`UNMATCHED` outcome. Timestamp/index displacement, explicit stereo-buffer
eviction, and stop-time buffer flush have distinct reason codes.

## Candidate and association evidence

Detector-returned candidates receive content-derived IDs without changing
detector return order. Tracklet ID, start/continue action, ramp-up eligibility,
and rejection reasons remain attached to the terminal frame record. Each
processed pair records the complete lane-gated candidate edge graph, cost
components, gate result, primary assignment, optional shadow assignment, and a
terminal triangulation outcome linked by edge and observation IDs.

`stereo.association_mode` defaults to `greedy_v1`. `shadow_v2` keeps greedy
results primary and records the deterministic global assignment for comparison.
`global_v2` is opt-in and fails closed if its solver is unavailable. This mode
must remain non-default until field validation approves it.

## Journal and replay

Recording sessions write required decision events through a bounded asynchronous
journal at `evidence_journal/decisions.jsonl`. Its manifest includes a SHA-256
digest, record counts, required/optional drop counts, write status, and a
completeness flag. The session manifest links to this journal. Required evidence
that cannot be queued makes the journal incomplete rather than silently implying
a replayable measurement.

The decision replay verifier checks frame and pairing conservation, one-to-one
assignment, assigned-edge validity, global primary/shadow optimality, and
triangulation coverage. It derives exact numerator/denominator payloads and
returns `None` when a denominator is zero.

This is candidate-level decision replay, not pixel-to-detector bitwise replay.
Reproducing detector inference still requires source frames, preprocessing,
model/runtime hashes, configuration and ROI artifact hashes, and a declared
numeric tolerance for nondeterministic backends.
