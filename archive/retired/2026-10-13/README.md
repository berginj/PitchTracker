# Retired desktop paths — 2026-10-13

Retired at the operator's explicit request after the branch review. The original
paths and contents are preserved beneath this directory, including the tests
that belong solely to these implementations. They are historical source, not
alternate supported entry points or an executable archive package.

- MainWindow and its controller/mixin stack.
- InProcessPipelineService and implementation-only mixins.
- The direct app/pipeline.py CLI.
- Seven-stage SetupWindow and its step specification.
- Ten-stage stereo widget registry and live registry wiring.
- The calibration wizard coupled to MainWindow.
- Tests for those implementations and the prior ten-stage default specification.

Use `python launcher.py`, or `python launcher.py --setup --backend uvc` for
guided setup. Runtime work belongs to PipelineOrchestrator and its services.
Shared contracts, discovery, calibration tooling, diagnostic views and
recording/replay helpers remain in active source.

See [migration guidance](../../../docs/architecture/legacy-paths.md) and
[the rig walkthrough](../../../docs/RIG_VALIDATION_WALKTHROUGH.md).
Restore historical work through its original Git revision if research requires
it; do not copy these paths back into production to satisfy an obsolete import.
