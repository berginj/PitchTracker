# Guided rig setup

The launcher opens five stages: Cameras, Image checks, Calibration, Field and
regions, and Ready. Saved values are prefilled on every visit. Every valid edit
saves immediately; affected checks become incomplete and recording is blocked
until the changed rig is checked again.

See [Guided Setup](../../docs/GUIDED_SETUP.md) for operator instructions and
[Setup Snapshot Requirements](../../docs/SETUP_SNAPSHOT_REQUIREMENTS.md) for
measurement provenance.

## Ownership

SetupWorkflowService owns saved configuration, generations, check results, and
readiness. Widgets issue commands and present typed results. Camera acquisition
uses disposable supervised capture workers; calibration uses cancellable tooling
workers. Field triangulation and transform estimation use existing domain code.

Completed profiles contain their effective configuration, metric calibration,
per-camera regions, surveyed target evidence, and immutable setup snapshot.
Working edits live under calibration/setups and never overwrite completed rigs.
Session and UI preferences remain separate from rig configuration.

## Quality

Full metric stereo calibration is required for measurement. Coarse targetless
alignment is an image check and cannot establish metric scale. A saved/imported
calibration needs matching identity, dimensions, image transforms and board
provenance. Field setup requires three non-collinear fitting targets and a
separate holdout, with the existing 0.1 ft residual limit.

Passing setup enables estimated research recording. Optical timing and accuracy
still require independent physical qualification and confirmation. A new
revision does not inherit an accuracy approval. Unchanged configurations retain
their snapshot and append fresh preflight evidence.

## Compatibility and tests

The previous ten-step registry and seven-step SetupWindow are retired under
archive/retired/2026-10-13. StereoSetupWindow defaults to guided setup, including
direct construction and GUI smoke tests. All launcher routes use this workflow.

Start a discrete operator walkthrough with:

    python launcher.py --setup --backend uvc

See [Rig Validation Walkthrough](../../docs/RIG_VALIDATION_WALKTHROUGH.md) for
calibration, holdouts, timing, repeatability and independent quality references.

Run focused tests with QT_QPA_PLATFORM=offscreen:

    python -m pytest tests/test_guided_setup_workflow.py tests/test_guided_setup_desktop.py tests/test_guided_setup_tooling.py

Hardware validation must confirm capture modes, control readback, target picking,
cancellation, reconnect behavior, and reopen/recovery on the physical rig.
