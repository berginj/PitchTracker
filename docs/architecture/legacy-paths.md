# Runtime path ownership

The canonical desktop path is intentionally narrow:

```text
launcher.py
  -> ui.coaching.coach_window.CoachWindow
  -> app.qt_pipeline_service.QtPipelineService
  -> app.services.orchestrator.PipelineOrchestrator
  -> capture / detection / recording / analysis services
```

`ui/qt_app.py` is a compatibility shim for older scripts and delegates to
`launcher.py`. New UI entry points must use the launcher and
`QtPipelineService`; the shim is not a second application bootstrap path.

The operator approved retirement on 2026-10-13. InProcessPipelineService,
MainWindow, the seven-stage SetupWindow, ten-stage stereo registry and direct
pipeline CLI now live under `archive/retired/2026-10-13`, with their own tests.
The old module/class exports are intentionally removed. This is an API retirement
in development main, not a published installer release.

| Previous caller | Supported replacement |
|---|---|
| `from ui import MainWindow` / `ui.main_window` | `python launcher.py`; Coaching and Review use QtPipelineService |
| `ui.setup.SetupWindow` / ten-stage registry | `python launcher.py --setup`; StereoSetupWindow defaults to the five guided stages |
| `InProcessPipelineService` | PipelineOrchestrator; subscribe to typed EventBus events through its public API |
| PitchSummary through `app.pipeline_service` | `app.contracts.PitchSummary` |
| `app/pipeline.py` direct camera CLI | Explicit operator capture in Coaching; service APIs for application integrations |
| MainWindow calibration wizard | Guided metric calibration; Setup Doctor remains a diagnostic/tooling surface |

`ui.qt_app` and `scripts/test_setup_wizard.py` remain thin launcher commands.
Shared `app.pipeline.service_contracts`, camera/discovery, calibration, field,
recording, and replay helpers remain active. Private duplicate enrichment is
removed; CandidateProcessor owns the shared live/replay step.

Do not instantiate archived code or add aliases that reintroduce its workflow.
See [Rig Validation Walkthrough](../RIG_VALIDATION_WALKTHROUGH.md) for the
supported setup, physical qualification and reference-collection sequence.
