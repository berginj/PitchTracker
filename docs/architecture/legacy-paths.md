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

`app/pipeline_service.py` (`InProcessPipelineService`) remains a compatibility
implementation for existing callers. It must not be introduced into new UI
code. Shared DTOs are owned by `app.contracts`; the compatibility service may
implement the interface in `app.pipeline.service_contracts`, but it does not
define another copy of the durable result types.

Retiring the compatibility implementation requires an explicit migration plan
for its remaining callers and a release decision. Until then, changes should
reduce its fan-out and keep its boundary visible rather than silently creating
new imports.
