# Local detector dataset preparation and training

Status: current research workflow. Last reviewed: 2026-10-16.

This is the canonical dataset-preparation guide. The
[BaseballCV comparison workflow](../BASEBALLCV_COMPARISON.md) owns supported model
import, held-out evaluation and experimental live admission. Training a model
does not qualify it for live use or establish physical accuracy.

## Capture and provenance

Use the normal recording workflow with a qualified setup revision. Preserve
both videos, their encoded-frame timestamp mappings, configuration, metric
calibration, ROIs, field transform and independent reference/label provenance.
Include varied lighting, backgrounds, speeds, ball types, image edges, missed
detections and idle footage. Keep athlete/facility information local.

Choose observed hardware settings through guided setup; requested resolution,
FPS or exposure is not proof of achieved capture quality. Full calibration and
explicit timing are required for stereo replay. Scalar baseline/focal settings
are not a substitute for the calibrated camera model.

The recording service owns session/pitch artifacts. Use the actual manifest's
filenames and schema_version, whose source is
[contracts/versioning.py](../../contracts/versioning.py); app and schema versions
are different identities. The [manifest reference](../../MANIFEST_SCHEMA.md)
and [evidence contracts](../evidence_contracts.md) explain durable provenance.
Missing or unavailable artifacts must remain explicit.

## Extract frames

The [dataset preparation tool](../../record/dataset_prep.py) samples a selected
video using its matching timestamps:

```powershell
python -m record.dataset_prep --video recordings/<session_id>/session_left.avi --timestamps recordings/<session_id>/session_left_timestamps.csv --out-dir datasets/ball_left --fps 10 --prefix left
```

Use paths from the selected session. Output includes images, metadata.csv and a
YOLO-style dataset.yaml; labels are supplied by the labeling process. Do not
infer independent opportunities or negative examples only from accepted pitches.

## Labels and split discipline

Label ball boxes as class ball (ID 0), with image identity and normalized box
coordinates. For localization or stereo evaluation, retain independently
reviewed pixel centers, surveyed target/pitch identities and unavailable outcomes.
Marked-ball studies may additionally retain their marker specification and
dot/index labels; the [requirements](../../REQ.md) describe those research contracts.

Split by recording/session before tuning. Development and held-out evaluation
must not reuse the same session, renamed video or byte-identical copy. Preserve
annotation review state and record each rejected or unmatched opportunity.
The dedicated comparison workflow defines its session counts and held-out gates.

## Training and admission

Train in a separate research environment with explicitly supplied local assets.
Record model/data/code revisions, hashes, licenses, preprocessing, class IDs and
output layout. No weights or upstream code are implicitly downloaded or bundled.

Evaluate recall, false candidates, false stereo matches, localization tails,
attempt denominators and actual-capture timing. A numerical improvement alone
does not establish operational admission. Use the comparison service's bound
held-out and capture evidence before selecting an experimental live model;
keep classical detection and stereo defaults until an explicit release decision.

## Sharing and historical plans

There is no operational cloud-training submission workflow from the old proposal.
Any external transfer needs an explicit destination, selected artifacts and upload
authorization. Metadata alone can still identify people and facilities.

The original automation roadmap and implementation snippets are preserved in
[the documentation archive](../../archive/docs/ARCHIVE_INDEX.md).
[Optional integrations](../OPTIONAL_INTEGRATIONS.md) describes current scope.
