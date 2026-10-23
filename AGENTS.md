# PitchTracker maintenance instructions

PitchTracker is a Windows/PySide6 desktop app for evidence-first dual-camera
pitch measurement. Software success does not establish physical accuracy.

These are the repository-wide instructions for code and documentation work.
Read applicable scoped AGENTS.md files before editing. Runtime responsibilities
and message contracts live in [agent contracts](docs/architecture/agent-contracts.md).

## Start here

- Check git status before editing; preserve unrelated tracked and untracked work.
- Read existing code and use narrow patches and existing service patterns.
- Use [docs/README.md](docs/README.md) to find the canonical guide.
- [Current Status](docs/CURRENT_STATUS.md) owns delivered behavior and validation.
  [Roadmap](docs/ROADMAP.md) owns open work and acceptance criteria.
- Historical plans and results are context, not current instructions or approval.
- Agents are logical service roles. This file does not authorize automatic
  delegation or creating additional coding agents.

## Supported workflow and checks

Use Windows and the supported Python 3.13/3.14 environment. Install development
dependencies with python -m pip install -r requirements-dev.txt.
Start without cameras with python launcher.py --backend sim.

Run focused tests first, then the relevant required gates. Use adequate timeouts
for scipy and integration tests; record dependency and hardware skips explicitly.

```powershell
python -m pytest
python -m flake8 . --count --statistics
python scripts/check_file_length.py
python scripts/sync_schema.py --check
python scripts/check_public_docs.py
python scripts/check_typing_policy.py
python -m mypy . --no-incremental --show-error-codes
python -m pip_audit -r requirements.txt -r requirements-uvc-native.txt --strict
```

CI tests Python 3.13 and 3.14; canonical typing runs on 3.13. The security job
audits resolved Windows dependencies on both versions and blocks failures.
Use the current workflow and CI run for exact commands and results.
Main receives reviewed changes through a PR with passing required checks.
Never force push, reset, overwrite user work or remove branches without authorization.

## Runtime ownership

- Use PipelineOrchestrator for wiring, QtPipelineService for Qt integration and
  SetupWorkflowService for immediately saved rig edits, checks and publication.
- The launcher hosts one WorkspaceWindow: Live, Sessions, Players and Setup.
  Navigation alone must not acquire cameras, edit a rig or start/stop recording.
- Keep camera I/O in capture services; detection in detection services; pitch
  state in PitchStateMachineV2; fitting in trajectory/analysis; persistence in
  recording. UI observes and issues explicit service commands.
- Use typed contracts, events and public interfaces; do not reach into another
  service's private state outside tests or existing compatibility shims.
- Keep one owner for mutable state; use locks or event handoff. Snapshot inputs
  for asynchronous work; retain cancellation, worker cleanup and accepted-work
  draining before journal finalization.
- Preserve stereo_3d as the primary trajectory mode. Ray modes and optional
  detectors remain comparison-first until their separate evidence gates pass.
  A failed comparison must not erase the primary result.
- Preserve calibration, timestamp mapping, ROI and field-transform admission.
  Units are pixels, feet and monotonic nanoseconds as specified by contracts.
- Archived implementations are not runtime fallbacks. Read the
  [architecture](docs/ARCHITECTURE_CURRENT_STATE.md) before changing boundaries.
  Update the [runtime contracts](docs/architecture/agent-contracts.md), typed
  interfaces, schemas and compatibility readers when those boundaries change.

## Code conventions and failures

- Python files must stay within 500 lines; aim for 200-300 and extract before 400.
  Design targets: functions at most 50 lines and five parameters, classes at most
  30 methods, complexity at most ten and nesting at most three levels.
- Use snake_case modules/functions, PascalCase classes, explicit types and
  docstrings for public contracts. Follow the canonical typing policy.
- Expected domain failures use existing typed errors or structured failure codes.
  Broad catches are permitted at deliberate service/tooling/UI isolation
  boundaries when they log the failure, clean up and return a valid degraded state.
  Never silently swallow exceptions or perform blanket exception rewrites.
- Chain translated exceptions. Log lifecycle at INFO, frame detail at DEBUG,
  recoverable failures at WARNING and failed operations with exceptions at ERROR.
  Include available session, pitch and camera identifiers without secrets.
- Keep core code independent of Qt widgets. Reuse shared theme tokens and
  components; follow [UI instructions](ui/AGENTS.md) for experience changes.
- Version durable contracts and retain backward-compatible readers or document
  migration. Update app/release version sources together only for an intended release.

## Data and hardware safety

- Do not delete recordings, calibration files or configs without an explicit request.
- Do not upload frames, videos, manifests, athlete/facility data, calibration or
  logs without explicit upload authorization. Keep private state and secrets out
  of Git, screenshots and support bundles.
- Do not operate cameras or recording invisibly without clear operator intent.
- Before writes or recursive operations, verify resolved paths remain inside the
  intended workspace/output directory; preserve unrelated content.
- Before capture, validate backend, serials, supported modes and recovery policy.
  Before calibration, validate image pairs, board dimensions, output location and
  NPZ contracts. Before recording, check disk space and writer availability.
- Validate config sections and local tooling input types/paths. Never bypass
  validation or write malformed manifests.
- Long-running and hardware operations require timeout, cancellation and typed
  failure paths. Keep service admission independent of UI controls.
- Synthetic tests and setup readiness do not establish physical accuracy.
  Preserve unavailable/rejected outcomes, denominators, provenance and raw data.
  Hardware changes need simulator tests and an explicit manual-validation note.

## Documentation and review

- Follow [documentation maintenance](docs/DOCUMENTATION.md). Update the existing
  canonical guide; create a document only for a distinct decision, substantial
  plan or material validation record.
- Keep historical evidence dated; update links mechanically without rewriting
  past results as current claims. Keep local scratch assets under ignored archive/local/.
- For UX work, follow the [workspace plan](docs/UX_WORKSPACE_PLAN.md), scoped UI
  instructions and public service contracts. Preserve recording status across
  navigation; test recovery, keyboard access and viewport reachability.
  UX-07 covers secondary surfaces and local Help; UX-08 retains complete journeys
  and manual display/accessibility qualification. Roadmap owns delivery status.
- Review correctness, compatibility, resource ownership, privacy and evidence
  limits. Validate changed behavior at the smallest useful boundary, including
  one message-flow integration check for new service ownership.
- Report what changed, what passed, what skipped and any remaining manual gates.
