# Optional BaseballCV integration: software validation

Date: 2026-10-13. Implementation branch: `codex/baseballcv-comparison`, based on
`42be76e` (the platform and issue closeout change). This is local software
evidence, not a release or an approval of physical measurements.

## Delivered behavior

Classical MODE_A, greedy stereo and `stereo_3d` trajectory fitting remain
defaults. Review's **Compare approaches** runs the twelve declared detector /
association controls on immutable local recordings. Detection failures,
rejected fits, missing pitches, multiple attempts and extra attempts remain
visible against independently labeled opportunities. Complete detector caches
can be reused across association controls; changed or corrupt inputs invalidate
them. Live and replay use the same candidate identity and eligibility processor.

Supplied YOLO11 ONNX bundles declare their preprocessing, classes, output layout,
localization basis, covariance and licenses. CPU workers warm and validate their
graphs before admission, retain frame identity, enforce deadlines, recover once
and close after repeated failure. No upstream weights or code are included.

The experimental stereo control propagates localization covariance through
undistortion and triangulation, uses causal motion predictions and global
assignment, and rejects ambiguous matches. These covariance estimates exclude
calibration and acquisition uncertainty. Geometry, timing and depth outer gates
remain in place.

The separately supervised BaseballCV monocular adapter uses local assets and
video copies, denies network calls, and retains its image-zone-at-glove-arrival
measurement basis. It cannot populate stereo speed, plate crossing or strike
fields. Its pinned dependency set resolves for Windows x64 / Python 3.12;
actual upstream execution still requires supplied assets and that environment.

An operator can request a bounded shadow trial during an existing recording.
It collects detector and candidate/stereo pipeline timing, queue losses and
frame identity without publishing results into the primary pipeline. A live
selection requires held-out quality, twelve distinct surveyed targets, matching
strata and a fifteen-minute recorded run at the existing mode. Its receipt binds
the code, libraries, hardware, model, configuration, calibration, effective
regions, field matrix, camera identities and recorded timestamp evidence.
Selection and restoration create pending revisions through SetupWorkflowService;
runtime independently checks admission. Experimental settings cannot switch
during capture. Standalone global_v3 remains comparison-only.

## Automated evidence

The exact local outputs remain ignored under `validation_output/`.

| Check | Evidence |
|---|---|
| Python 3.13 full suite | `baseballcv-accepted313.xml`: 1,984 passed, 47 optional skips |
| Python 3.14 full suite | `baseballcv-accepted314.xml`: 1,983 passed, 48 optional skips |
| Frozen Windows worker suite | `baseballcv-final-packaged.xml`: six passed, including actual OpenCV ONNX execution and all twelve comparison cells |
| Final affected-code checks | `baseballcv-final-focused.xml`: 80 passed; `baseballcv-final-domain314.xml`: 39 passed, one optional ONNX skip, two desktop tests excluded from this focused run |
| Repository-wide mypy | Clean across 862 source files |
| Static gates | Schema mirror, public documentation, 500-line cap, Flake8, typing policy and whitespace checks |

The full matrix test uses generated stereo clips, separately computed synthetic
centers/world coordinates and controlled detector outputs. The ONNX worker test
uses a generated graph and checks both source and frozen frame identities.
Additional tests cover supervised cancellation/recovery, changed evidence,
quality/coverage regressions, distinct target counts, label revisions, cache
corruption, saved setup generations, recording edit admission and desktop task
startup. Synthetic fixtures are not admissible field validation.
Final review additionally bound the optional compiled CPU kernel bytes and
blocked promotion of offline ML covariance overrides; affected comparison and
admission tests were rerun after those focused changes.
Classical comparison detectors also use runtime's full-frame input; the shared
processor applies the ROI instead of applying an extra detector-side crop.

The final local frozen artifacts under
`dist/baseballcv-2026-10-13/PitchTracker/` have SHA-256 values:

- `PitchTracker.exe`: `00cee5d5d3ede7dcda51349e35145743b64dae6a09256f41fb3d37aab848987f`
- `PitchTrackerWorker.exe`: `7a3ba38c9dd110295fd91b06f654b1485c1a5d21b738bdb7234dd195d9e8990b`

They were built from the working tree before the implementation commit and
report the base revision with a dirty-tree marker. They are unsigned local
test artifacts, not published release assets.

Validation also corrected two existing test assumptions: rig startup's provenance
fixture now supplies a typed configuration, and disk-monitor stop testing uses
explicit healthy space and a synchronization event. The latter previously raced
against the host's real low-space emergency stop. Production disk protection is
unchanged. An earlier run mixed imported module generations while files were
being edited; acceptance runs used fixed source. A focused Python 3.14 run
reported passing tests but exited abnormally after its summary, so the full
serial acceptance run is the compatibility gate.

## Operator work still required

1. Supply compatible weights, clarify upstream code/weight/data licensing, and
   test the real export and monocular environment. Do not redistribute unknown
   assets.
2. Collect six dedicated sessions: two development and one evaluation session
   for each ball type, with forty opportunities per session and twelve distinct
   surveyed targets per ball type. Review pixel labels and the required negative,
   lighting, background, edge and occlusion cases. Freeze covariance models before
   evaluation. No profile currently has qualifying field evidence.
3. Run actual sustained capture/recording on the target machine and preserve its
   journal. Slower models remain offline. Simulator and paced replay results
   cannot qualify live capture.
4. Complete clean-machine installation, lifecycle and camera checks. The local
   frozen smoke test does not establish clean-machine or ARM64 compatibility.
5. Add independent speed and plate references using physical-validation v2 and
   disjoint confirmation evidence before publishing accuracy claims.

The collection scaffold is intentionally empty and unreviewed. See
[the operator/developer workflow](../BASEBALLCV_COMPARISON.md) for commands and
schemas. Recordings, manifests, models and generated outputs remain local.
