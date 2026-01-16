Potential cleanup checklist (unreferenced in code/docs)
- [ ] `telemetry/monitor.py` — no imports/usages found outside `telemetry`
- [ ] `telemetry/__init__.py` — only re-exports for unused module
- [ ] `detect/telemetry.py` — `log_timing` never called
- [ ] `record/analyze_video.py` — no references
- [ ] `record/dual_capture.py` — no references
- [ ] `app/demo.py` — no references
- [ ] `schema/session_summary.schema.json` — unused; schemas referenced from `contracts-shared/`
- [ ] `schema/version.json` — unused; schemas referenced from `contracts-shared/`