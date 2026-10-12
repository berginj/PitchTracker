# Setup Doctor and guided configuration

The desktop setup entrypoint is the five-stage
[Guided Setup](GUIDED_SETUP.md): Cameras, Image checks, Calibration, Field and
regions, and Ready. Valid edits save immediately. Setup records configuration
provenance and blocks recording for pending changes.

Calibration, alignment diagnostics, and environment validation remain owned by
tooling services. Supervised capture isolates stalled camera calls. Cancelling
or closing setup retains workers until their processes are reaped.

The older SetupWindow and diagnostic CLI tools remain compatibility paths.
Their output can be explicitly imported into a working rig; original files are
preserved. Missing calibration identity/transform provenance remains diagnostic
and requires a new full calibration before measurement use.

A completed setup enables estimated research recording. Physical timing,
independent references, confirmation studies, and signed approvals remain
separate requirements. See [Setup Snapshot Requirements](SETUP_SNAPSHOT_REQUIREMENTS.md)
and [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md).
