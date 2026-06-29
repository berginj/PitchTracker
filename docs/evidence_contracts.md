# Evidence Contracts

PitchTracker now has durable evidence records in `contracts/evidence.py`.

Purpose: keep the chain from 2D candidates to final pitch verdict replayable without relying on in-memory state.

## Records

- `Candidate2DEvidence`: one detector candidate in one camera frame.
- `StereoMatchEvidence`: one left/right candidate pairing attempt.
- `Observation3DEvidence`: one triangulated 3D point with quality, confidence, covariance, and rejection reasons.
- `PitchVerdictEvidence`: final pitch-level verdict linking fitted output back to observation IDs.

All records include:

- `schema_version`
- stable IDs
- status or verdict labels
- rejection/warning reason codes where applicable
- JSON-compatible `to_payload()` / `from_payload()` helpers

## Runtime Wiring Target

The recording path should eventually persist:

```text
evidence/
  candidates_2d.jsonl
  stereo_matches.jsonl
  observations_3d.jsonl
  pitch_verdict.json
```

Do not use these contracts to make accuracy claims until the field fixture validator has passed on real rig data. The immediate goal is traceability: every accepted 3D observation should identify the source detections and stereo match diagnostics, and every rejected candidate or match should preserve a reason.
