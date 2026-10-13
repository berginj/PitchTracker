# Optional BaseballCV detector and stereo comparison

Classical MODE_A and greedy stereo remain defaults. This integration adds local
research and an explicitly selected experimental live profile; it grants no
physical accuracy approval. CPU is the inference default. Ray comparison and
existing setup, timing and measurement approval gates remain in force.

## Import supplied models

The application does not install BaseballCV, download checkpoints or upload
recordings. Its YOLO11 adapter uses OpenCV ONNX with RGB letterboxing, declared
class IDs, raw-frame coordinate recovery, NMS and a maximum of twenty proposals.
GRAY8 inputs expand to three channels. Box sizes describe image proposals, not
physical ball radius. A refined profile uses native-resolution component
localization; failure explicitly retains the box center and its error model.

The optional Windows x64 Python 3.12 environment in
`research/requirements-baseballcv.txt` is separate from app requirements. Export
an explicitly supplied checkpoint in that environment. Keep supplied inputs in their own
folder, separate from the new export directory:

```powershell
python research/export_baseballcv_onnx.py --checkpoint research_output/supplied/supplied.pt --output research_output/export --source-revision c3c26c979766b28e0c78c3fee2edc2aa3dad571e
python -m scripts.import_detector_bundle --model research_output/export/supplied.onnx --metadata research_output/export/export_metadata.json --output research_output/bundle
```

Metadata must declare `name`, `class_names`, `ball_class_id`, `source_revision`
and `licenses` with `code`, `weights` and `data`. Optional fields include
`localization` (`box`/`refined`), input size, output layout, thresholds and
`box_covariance_px2`/`refined_covariance_px2`. Covariances are symmetric positive
definite 2x2 matrices in raw pixels squared. Unknown licenses are explicit local
research metadata, not permission to redistribute. The root upstream MIT
license and README AGPL/commercial statements need clarification before bundling
code, data or weights. No upstream code or weights ship in this implementation.

## Collection and labeling

```powershell
python -m scripts.scaffold_comparison_dataset --output research_output/study
```

The scaffold intentionally contains missing inputs and unreviewed labels; it
cannot masquerade as a completed study. Fill six sessions: two development and
one held-out evaluation session per ball type, forty independently identified
pitch opportunities per session, twelve surveyed target placements per ball
type, controlled motion and negative footage. Cover nominal, lighting,
background, image-edge and occlusion conditions. Preserve each exact config,
full calibration, ROI and field transform with both videos and their explicit
encoded-frame timestamp mappings. Do not derive the opportunity denominator
from pitches accepted by a detector.

Click ball centers using Review's existing annotation mode and export those
points. Convert encoded indexes to source identities with:

```powershell
python -m scripts.convert_review_annotations --session recordings/session --annotations review_points.json --output research_output/labels_draft.json
```

This produces an unreviewed draft. Add independent `opportunities` with unique
`id`, `start_ns`, `end_ns`, and nonoverlapping windows. Each labeled frame has
`camera_id`, `frame_index`, `timestamp_ns`, `visibility` (`visible`, `occluded`,
`absent`), optional `opportunity_id`, and `stratum`. Visible balls need
`center_px`; surveyed targets additionally use `xyz_ft` and a stable `target_id`
shared by both views. Qualification requires twelve distinct target identities,
not twelve observations of one target. Optional `radius_px`
sets detection-label matching tolerance. Review negative and occluded frames,
then explicitly set `human_reviewed: true`. Review → Tools → Compare approaches
includes a local label-revision editor and saves new annotation/study revisions.

## Run and inspect

```powershell
python -m scripts.compare_pipelines --dataset research_output/study/dataset.json --bundle research_output/bundle/bundle.json --output research_output/results
```

The Review dialog exposes the same service. Four detectors (classical A/B,
BaseballCV box/refined) each run with greedy_v1, global_v2 and global_v3 stereo.
Calibration, ROIs, timing offsets and fitting settings are shared across cells.
Candidate identity, tracklet enrichment and eligibility now use the same
component in live and replay. Session-scoped detector caches are committed only
after complete valid replay; model, configuration, source and implementation
changes invalidate their identities. Failures are retryable, not cached as
success. Every independent pitch opportunity retains a terminal result,
including no pitch, rejected results and multiple attempts. Extra attempts stay
visible. Missing models produce unavailable cells rather than disappearing.

Reports include recall/precision, localization tails, correct/false/unverified
stereo matches, surveyed-target error, pitch outcomes, source accounting and
detector latency. Component artifacts retain candidates, associations and
provenance. The experiment runs in a supervised process; cancel kills its owned
tree and retains partial reports. New/active offline research pauses for capture.

The experimental global_v3 profile uses localization-normalized epipolar and
reprojection checks, causal temporal predictions, one-to-one assignment and an
explicit ambiguity margin. Initial gates are three standard deviations and
ten percent assignment-cost margin. Existing time, epipolar and depth limits
remain outer gates. Missing localization covariance rejects the experimental
match. Confidence scores are not converted into physical uncertainty.

Estimate localization errors only from development sessions:

```powershell
python -m scripts.calibrate_localization --report research_output/results/reports/JOB.json --output research_output/localization.json
```

The estimator retains bias in the residual second moment, uses a quarter-pixel
squared floor and requires thirty reviewed errors per localization basis. Copy
the selected matrices into new bundle metadata and session `pixel_covariances`
for classical profiles. Freeze revisions before held-out evaluation. Refined
fallback and refined centers have distinct error bases. These are conditional
localization models, excluding exposure and calibration uncertainty.
Session overrides of ML covariance are supported for offline exploration and
marked in reports. They cannot qualify a live profile: put the selected ML
covariances into a new bundle and rerun held-out evaluation so live and replay
use the same model.

## Separate monocular experiment

Provide `baseballcv_research_assets.v1` with local `.pt` assets and SHA-256 values
for `phc_detector`, `glove_tracking`, `ball_trackingv4`, and optional `pose`.
Declare code/weight/data licenses. Use a clean checkout at upstream revision
`c3c26c979766b28e0c78c3fee2edc2aa3dad571e` and the isolated Python:

```powershell
python -m scripts.compare_pipelines --dataset study.json --output research_output/results --bundle bundle.json --monocular-assets assets.json --external-python research-env/Scripts/python.exe --external-repository BaseballCV
```

The local adapter supplies models and local videos through upstream public
loading/analyze APIs. Network calls are denied; no Savant scraping or model
download occurs. Each paired-camera view and declared `broadcast_clips` runs
separately. Missing pose/models or unsuitable footage remain unavailable.
Results preserve the image-zone-at-glove-arrival basis, optional glove-frame
label error and upstream assumptions. They never populate stereo plate-crossing,
speed or strike fields. Mirror clips stay local in the selected output directory.

## Qualify and select live use

Hold-out quality gates require center/target p95 error within five percent of
classical A/greedy, coverage loss at most two percentage points, no false-match
increase, complete required strata and at least ten percent improvement in a
measurement tail. Thirty positive labels, forty opportunities and twelve target
placements are minimum software evidence gates, not physical sample-size claims.

During an operator-started recording, Coaching → Detector trial runs an
explicit shadow detector without publishing its results into the primary
pipeline. Warm up, record at least fifteen minutes at the existing camera mode,
then stop and save the report. End recording before qualification. At least
99% of opportunities must be processed and per-camera detector and complete
shadow pipeline p95 must fit the frame period. A simulator or paced replay cannot qualify an actual live profile.
The timing journal must reconcile with recorded video timestamp mappings.

```powershell
python -m scripts.qualify_detector_profile --report comparison.json --timing timing.json --config config.yaml --bundle bundle.json --variant baseballcv_box:global_v3 --output research_output/qualified.json
```

The bundle's declared localization must match the selected live variant.
Review → Compare approaches → Select qualified profile saves one pending setup
generation through SetupWorkflowService. Finish Setup checks and publish a new
rig revision before recording. Runtime independently verifies the model,
implementation, hardware, config, calibration, effective regions, field transform,
camera identities and qualification evidence. Restoring classical is also
an explicit saved setup action. No automatic model/profile conversion occurs.

Actual supplied-weight compatibility, clean-machine packaging, real-time
throughput and held-out field results remain operator-run gates. Later matched-
location speed and independent plate-location references must use the existing
physical-validation v2 process and disjoint confirmation data before claims.
