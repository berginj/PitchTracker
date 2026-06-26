# PitchTracker Contracts

Shared contracts for PitchTracker apps (desktop and cloud).

This directory holds machine-readable schemas plus the contract-specific human
context needed to use them well. Canonical product personas live in
`../docs/USER_PERSONAS.md`; this package keeps schema mappings and workflow
notes close to the contracts.

## Files
- `PERSONAS.md` - Contract mapping to canonical personas in `../docs/USER_PERSONAS.md`.
- `schema/version.json` - Contract schema version (semver).
- `schema/session_summary.schema.json` - JSON Schema for session summaries.
- `schema/session_upload.schema.json` - JSON Schema for session uploads to analytics.
- `schema/training_report.schema.json` - JSON Schema for local training/telemetry reports (no video payloads).
- `schema/marker_spec.schema.json` - JSON Schema for marked-ball specs.
- `examples/session_summary.sample.json` - Example session summary payload.
- `examples/marker_spec.json` - Example marking/ball spec for vision expectations.
- `examples/training_report.sample.json` - Example training report with logs, errors, and capture stats.
- `examples/generate_marker_spec.py` - Helper to regenerate marker spec for baseball/softball.

## Runtime schema mirror

This directory is the **single source of truth** for published schemas. The
running desktop app loads a small subset from the repository-root `schema/`
directory so it does not depend on this package's layout. That root directory is
a generated mirror, not a second source of truth.

After editing `schema/version.json` or `schema/session_summary.schema.json`
here, regenerate the mirror:

```powershell
python scripts/sync_schema.py            # update the root schema/ mirror
python scripts/sync_schema.py --check    # CI: fail if the mirror is stale
```

`tests/test_contracts.py` asserts the mirror matches this source, so a stale
mirror fails the test suite.

## Persona and Workflow Context

See `../docs/USER_PERSONAS.md` before changing schemas, then use
`PERSONAS.md` for schema-specific persona and workflow mapping.

## Contract Map

| Contract | Primary producer | Primary consumer | Primary workflow |
| --- | --- | --- | --- |
| `session_summary.schema.json` | Coach / Session Operator | Coach, pitcher review flow, downstream exports | End-of-session recap and lightweight analytics |
| `session_upload.schema.json` | Coach / Session Operator or upload integration | Cloud analytics and dashboards | Session upload and remote analysis |
| `training_report.schema.json` | Setup Technician / Installer or advanced operator | Support, engineering, troubleshooting | Validation, diagnostics, and training telemetry |
| `marker_spec.schema.json` | Vision engineer or advanced setup operator | Detection and marked-ball tooling | Marked-ball experiments and vision expectations |

## Guidance
- Keep machine-readable schemas focused on portable payload structure.
- Put canonical persona definitions, jobs-to-be-done, and discovery questions in `../docs/USER_PERSONAS.md`.
- Put schema-specific persona mappings in `PERSONAS.md`.
- Prefer schema `description` and `$comment` fields for workflow context before adding new required persona fields.
- If a workflow introduces a new durable artifact, add a contract for that artifact instead of overloading an unrelated schema.

## Runtime Snippet (Marker Spec)
```python
import json, math
import numpy as np

def load_expectations(spec_path: str):
    spec = json.load(open(spec_path, "r"))
    r_mm = spec["ball"]["diameter_mm"] / 2.0
    index_sep_mm = spec["marking"]["index_sep_mm"]

    # Expected angular separation between the two index dots on the sphere
    # arc length s = r * angle  => angle = s/r
    index_angle_rad = index_sep_mm / r_mm

    # Expected chord length on *unit sphere* between the two index dots:
    # chord = 2*sin(angle/2)
    index_chord_unit = 2.0 * math.sin(index_angle_rad / 2.0)

    markers = np.array([m["v"] for m in spec["markers"]], dtype=float)
    return {
        "spec": spec,
        "markers_unit": markers,             # Nx3
        "index_chord_unit": index_chord_unit # multiply by ball_radius_px for expected pixel spacing (approx)
    }

def find_index_pair(dots_uv, ball_center_uv, ball_radius_px, index_chord_unit, tol=0.35):
    """
    dots_uv: list of (u,v) dot centroids detected in image
    Returns indices (a,b) of the index pair in dots_uv.
    Uses expected separation ~ ball_radius_px * index_chord_unit (approx when dots are near the front).
    """
    pts = np.array(dots_uv, float)
    if len(pts) < 2:
        return None

    # Expected separation in px (rough but effective with tolerances)
    expected_px = ball_radius_px * index_chord_unit

    # Pairwise distances
    best = None
    for i in range(len(pts)):
        for j in range(i+1, len(pts)):
            d = np.linalg.norm(pts[i] - pts[j])
            score = abs(d - expected_px) / (expected_px + 1e-6)
            if score < tol and (best is None or score < best[0]):
                best = (score, i, j)

    return None if best is None else (best[1], best[2])
```
