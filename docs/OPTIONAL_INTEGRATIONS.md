# Optional integrations and deferred proposals

Status: current scope reference. Last reviewed: 2026-10-16.
[Roadmap](ROADMAP.md) owns priorities; [Current Status](CURRENT_STATUS.md) owns delivery.

## Local detector research

The [BaseballCV comparison workflow](BASEBALLCV_COMPARISON.md) is implemented
local research, with separately qualified experimental live selection. Classical
detection and stereo remain defaults. Supplied model assets, held-out evidence
and actual-capture qualification are required; none grants physical accuracy approval.
See [training](ml/TRAINING.md) for dataset preparation.

## TAG Sports

The [TAG service](../app/services/tag_sports_integration.py) and adapter contracts
provide an isolated import/research foundation. They are not wired into the
current coaching/orchestrator journey. Cloud and Bluetooth feature flags default
off; enabling a flag still requires a concrete configured adapter and authorization.
The [feature flags](../app/services/tag_sports_flags.py) do not create a backend
or establish a partnership.

The March partnership schedules, outreach drafts and API/export designs are
[historical proposals](../archive/docs/ARCHIVE_INDEX.md). They do not authorize
outreach, device access, athlete-data sharing or claims of completed integration.
Resume work only through a scoped roadmap issue with current interfaces,
privacy boundaries and acceptance evidence.

## Cloud training submission

No production training-submission backend or operational ingest endpoint is
provided by the archived cloud proposal. Keep datasets and recording artifacts
local. A future submission feature requires an explicit data contract, destination,
consent/upload authorization, implementation and security/compatibility validation.
Telemetry can still identify athletes or facilities and is not automatically
safe to upload merely because video is absent.

Use [the training guide](ml/TRAINING.md) and
[physical validation protocol](PHYSICAL_VALIDATION_PROTOCOL_V2.md) for current work.
