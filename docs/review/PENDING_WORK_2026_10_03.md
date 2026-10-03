# Pending-work review — 2026-10-03

Reviewed `main` / `origin/main` at `a55b8981ac2aa8779df8cc5038db61df6716ac3b`.
The six consolidation commits are pushed. This is a targeted code, artifact,
test, roadmap, and GitHub-backlog review, not a line-by-line certification.
Three agents examined runtime lifecycle, deployment/updating, and measurement
criteria. No source changes, physical capture, installations, downloads, or
private-data uploads were performed. Existing untracked review assets remain
untouched; this report is retained as the baseline for the remediation work below.

Prior full local suites passed 1,750 tests with 32 skips on each supported
Python runtime; four frozen-worker smoke tests passed. Those results do not
cover every failure ordering or the frozen GUI import path identified below.
At the final review check, [CI for this commit](https://github.com/berginj/PitchTracker/actions/runs/37122438901)
had passed the Python 3.13 test job and was still running Python 3.14.
Schema/docs/length/lint and Python 3.13 mypy had passed; native UVC and advisory
security jobs had completed successfully.
No new full suite was run for this review. Reproductions below use fakes only.

## Recommended implementation order

### 1. High: complete the frozen GUI dependency path

[`launcher.spec:47`](../../launcher.spec) excludes Matplotlib from the GUI,
but Coaching eagerly imports the pattern report generator, which imports it at
[`analysis/pattern_detection/report_generator.py:8`](../../analysis/pattern_detection/report_generator.py).
The chain runs through Coaching widgets, fatigue/trend analysis, and
`analysis.pattern_detection.__init__`. A source import with Matplotlib blocked
fails. Read-only PyInstaller archive inspection found the report generator in
the GUI PYZ and no Matplotlib; the worker PYZ contains both.

This is strong evidence of a packaged Coaching import defect; no actual frozen
GUI launch was performed. Include the required GUI dependency or defer report
imports until the supported report path. Add frozen GUI Coaching/Setup/Review
construction tests with simulator inputs and no installed development packages.
Existing worker-only smoke tests are insufficient for this closure.

### 2. High: preserve operator data and provide writable installed paths

[`installer.iss:74–77`](../../installer.iss) recursively deletes `{app}/data`,
`logs`, `calibration`, and `rois` during uninstall. There is no separate
data-removal choice. Sessions under `data` and rig calibration can be destroyed;
the default separate `recordings/` directory is not listed in these entries.
Retain operator artifacts by default and require a distinct explicit action to
remove them. Verify sentinel artifacts survive uninstall/reinstall.

The installer defaults to Program Files (`installer.iss:20`), while
[`launcher.py:473–478`](../../launcher.py) changes cwd to the bundled launcher
directory and creates relative mutable directories. Logging, preferences,
calibration and recording also use relative paths; see
[`log_config/logger.py:23`](../../log_config/logger.py) and
[`configs/app_state.py:12`](../../configs/app_state.py). No per-user data-root
policy was found. Establish writable application-data/config/log paths,
immutable bundled defaults, and explicit migration. Standard-user permission
failures are predicted by inspection, not demonstrated by an installed-account
test here. Test standard-user startup, persistence, update and reinstall.

### 3. High: retain recording ownership through failed stop

[`app/services/orchestrator/lifecycle.py:60–65`](../../app/services/orchestrator/lifecycle.py)
stops analysis first. If draining raises, recorder stop is skipped, but the
`finally` block clears recording-active state and session metadata. Subsequent
shutdown checks the cleared flag and no longer retries that open recorder.
Fake-only injection confirmed zero recorder-stop calls and zero subsequent
shutdown retries after analysis failure.

Represent stopping/failed ownership explicitly, preserve metadata until
terminal completion, and make independent cleanup and retries safe. Test
analysis timeout, writer timeout, repeated stop/shutdown, and successful retry.

Also preserve journal-finalization metadata across retries:
[`app/services/recording/session_lifecycle.py:107–123`](../../app/services/recording/session_lifecycle.py)
detaches/closes the journal before writer drain, retaining its manifest and
completeness only in local variables. A fake failed-then-successful writer stop
passed `None` for both values on retry despite a clean journal. Keep those
values in session-owned pending state until manifest finalization succeeds.

### 4. High: make capture stop and reconnect terminal

[`app/pipeline/camera_frame_router.py:140–146`](../../app/pipeline/camera_frame_router.py)
discards thread ownership after a timed join even when the thread is alive;
[`app/pipeline/camera_management.py:237`](../../app/pipeline/camera_management.py)
then closes its camera. Reconnection repeats close after a timed join at
[`app/pipeline/camera_lifecycle.py:138–150`](../../app/pipeline/camera_lifecycle.py).
Capture service stop also holds its lock while joining, although callbacks need
that lock (`app/services/capture/implementation.py:128–132,264`). These paths
can race native read/close. Native failure was not reproduced; blocked-reader
ownership and callbacks can be tested without cameras.

Unregistration at [`app/camera/reconnection.py:87–102`](../../app/camera/reconnection.py)
does not cancel/join an in-flight reconnect callback. A fake blocked open,
followed by shutdown and then release of the open, cleared the stop signal,
published a replacement camera and requested another capture thread after stop.

Retain terminal ownership, avoid lock-held joins, and fence reconnect with
cancellation/lifecycle-generation checks before and after open/configure and
before publishing replacement state. Test stop during read/backoff/open/configure,
immediate restart, and stale completion. A noninterruptible native read may
require process isolation. Qualify the resulting policy on hardware afterward.

### 5. High: finalize accepted pitches before pause/stop unsubscribes

The preferred stop path does not end the tracker before stopping analysis
(`app/services/orchestrator/pipeline_orchestrator.py:244–247`). Recording closes
an active pitch and later clears pending recorders (`session_lifecycle.py:135,169`).
Pause ends the tracker but does not drain accepted analysis before recording
unsubscribes, including from `PitchAnalyzedEvent`
(`pipeline_orchestrator.py:257`, `analysis/implementation.py:128`,
`recording/session_lifecycle.py:199`, `recording/event_handlers.py:207`).

Inspection identifies a terminal-result delivery gap; no full end-to-end lost
manifest reproduction was run. Fence producers, finalize or explicitly reject
the active pitch, keep terminal-result subscriptions through accepted analysis
drain, then close/pause writers. Test stop mid-pitch and blocked analysis across
pause/resume; require exactly one durable terminal artifact per eligible pitch.
Implement with item 3's retry-safe lifecycle.

### 6. High: bring the manual updater under shutdown ownership

[`ui/update_dialog.py:145,172–179,289`](../../ui/update_dialog.py) permits rejection
with an active download, has no close/reject drain guard, and shadows native
`QThread.finished` with a result signal. Line 215 directly quits the application
rather than using the launcher's drain path. A benign blocked-worker reproduction
confirmed rejection hides the dialog with its worker running and uncancelled.

Separate result/terminal signals, cancel and retain the worker through native
completion, suppress late results, and route install closure through owned
shutdown. Test blocked download, repeated rejection/close, retry, and install
while startup validation is active. No real download/install was performed.

### 7. Medium: tighten installer input, configuration and checksum provenance

`installer.iss:58` includes every `configs/*.yaml`, whereas the GUI spec names
two intended defaults. A dirty checkout can package additional local YAML;
no current private-config leak was demonstrated. Use an explicit distributable
allowlist and test excluded sentinel files. Define preservation/migration of
operator configuration during update rather than overwriting bundled defaults.

[`build_installer.ps1:147–157`](../../build_installer.ps1) selects the first
existing output executable for reporting/checksumming. Without `-Clean`, that
can be an older installer. Select the exact output produced by the current
compiler invocation and test multiple existing artifacts. Do not delete old
artifacts as a substitute for precise selection.

### 8. Medium: complete measurement semantics across exports and eligibility

[`ui/export.py:275–344`](../../ui/export.py) exports selected `speed_mph` and
`trajectory_confidence` without separate vision/external speed, location/time,
or the explicit heuristic fit-quality/physical-uncertainty basis. JSON manifests
already preserve richer records. Add compatible CSV columns and tests for
manual overrides, radar input, unavailable measurements and legacy summaries.

[`metrics/strike_zone.py:62`](../../metrics/strike_zone.py) fixes between-frame
misses and rejects unsupported gaps/coverage, but near-boundary calls do not
consume spatial covariance or acquisition-time uncertainty. Establish an
uncertainty-aware eligibility policy and boundary/timing regressions; do not
turn the existing estimated geometry result into an accuracy claim.

Expand the model-envelope evidence before extending claims. The current
[`benchmarks/trajectory_model_envelope.py:64`](../../benchmarks/trajectory_model_envelope.py)
reports speed bias from 12 fixed-seed cases, not plate-position bias. Add plate
bias, several noise seeds, geometry/coverage, timing, drag/ball-model and opt-in
prior sensitivity cases. Documented short arcs can pass despite omitted lift.
Keep spin/RPM unavailable and stereo primary; model development alone does not
establish a physical operating envelope.

## Required external validation and release work

- [#9](https://github.com/berginj/PitchTracker/issues/9): qualify real global-shutter
  pairs, controls, modes, USB load, drops, stable identities, disconnect/reconnect,
  setup repeatability and independently measured optical exposure timing.
- [#10](https://github.com/berginj/PitchTracker/issues/10): freeze the rig/build and
  protocol; collect shadow data, then a disjoint confirmation dataset with
  independent speed/plate references, all denominators and trusted attestations.
- [#11](https://github.com/berginj/PitchTracker/issues/11): after software deployment
  fixes, sign the candidate and test standard-user install, first launch,
  simulator/GUI workflows, stalled workers, update, uninstall and reinstall on
  clean Windows machines. Record exact source/artifact hashes.
- Publish the hardware matrix, supported envelope and refreshed installer only
  after applicable evidence gates pass. The latest public `v2.0.0` release has
  no attached installer assets at review time.

## Backlog reconciliation and low-priority cleanup

Ten GitHub issues are open: #9–#11 and #34–#40. The latter descriptions refer to
older code. #35's distortion defect is a strong software-closure candidate;
the original timing, drag, between-frame strike, fit-failure and speed-selection
defects have substantial remediation. Review acceptance criteria individually
against current tests rather than repeating those implementations. Residual
export/uncertainty/model criteria above and physical confirmation remain open.
No issues were changed or closed by this review.

## Remediation status — 2026-10-03

Items 1–8 above are implemented on `fix/pending-work-remediation`. Focused
validation passed for recording/orchestration (32), camera/detection/coaching
shutdown (22), packaging/updater (24, with two opt-in skips), and terminal
evidence retry (2). File-length, Flake8, and repository mypy checks are clean.
The complete matrix reached 1,819 passed and 34 skipped on Python 3.13 and
1,818 passed and 34 skipped on Python 3.14; each run had one timing-sensitive
failure in an existing analysis/calibration test, and both failed cases passed
when rerun serially. This is a validation follow-up, not a claim of a clean
full matrix.

The remediation adds simulator GUI smoke coverage and fresh-artifact checks,
but no physical cameras, clean-machine install, signing, or independent
measurement validation were performed. Issues #9–#11 and the corresponding
hardware, clean-install, signing, and accuracy gates remain open.

Two optional unused remnants remain: `SetupWindow._current_step()` at
`ui/setup/setup_window.py:218`, and write-only `_loading_label` storage at
`ui/setup/steps/camera_discovery_mixin.py:48`. They are lower priority than
ownership and deployment correctness. Compatibility shims, CLI diagnostics and
abstract/host methods are intentional. In particular, orchestrator runtime
calibration rejection enforces tooling ownership; it is not a missing feature.

Completed consolidation fixes, the empty oversized-file allowlist, required
mypy gate, and implemented UVC inventory should remain marked complete. Broader
queue rewrites, cloud/TAG integrations and ray-mode promotion remain conditional
work, not prerequisites for the controlled pilot.
