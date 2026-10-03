# Branch consolidation implementation and validation — 2026-10-02

Integration branch: `integration/valuable-branch-consolidation`.
Base commit: `e2f40e7`. See the [branch review](BRANCH_CONSOLIDATION_2026_10_02.md)
for every branch's disposition and original implementation plan.

Source commits: `9c2e8c2` (setup/discovery), `5435430` (launcher/imports),
`4a7cee3` (unused-code cleanup), `6025503` (integration test isolation), and
`5539056` (unused build-spec imports).
Four pre-existing detached worktrees were also inspected: each was clean and
either an ancestor of main or the already-incorporated production-readiness
squash source. They were left untouched. A separate detached worktree at
`6025503` isolates Python 3.14 validation from the main checkout's test artifacts.

The user authorized implementation of all four plan items, followed by removal
of unused/unreferenced code, with multiple agents. Changes preserve the current
source/frozen worker entry points and supported Python 3.13/3.14 policy. The
Python 3.9 compatibility patches were not imported.

## Implementation

- Adapted cancellation from `ab9bc82` around the current dedicated camera worker
  entry point, retaining native capability metadata. Cancellation reaps active
  PnP/OpenCV children, avoids cache writes, suppresses stale signals, and restarts
  discovery for the latest backend after the cancelled job terminates.
- Setup closure waits for owned work to finish before running step cleanup.
- Startup validation has a backward-compatible cancellation service method;
  the tooling subprocess is terminated/reaped, and the launcher retains its
  `QThread` until `finished`. Source-launcher preparation now runs in `main()`;
  importing launchers preserves cwd, import paths, and existing caches.
- Independent review identified legacy calibration and launcher update workers
  needing the same terminal-state ownership. Those paths are included in the
  shutdown implementation and tests. Legacy calibration suppresses cancelled
  results and waits for its existing tooling operation (up to 300 seconds),
  rather than terminating a Qt thread. Update downloads check cancellation
  between chunks; active reads retain their existing network timeout.
- Current roadmap follow-ups distinguish previously fixed recording command
  admission/config containment from the remaining physical qualification gates.

## Unused-code audit and removals

The audit covered the import graph of all 739 tracked Python files, code/docs
references, package exports, CLI guards, dynamic worker dispatch, and PyInstaller
hidden imports. It removed repository-internal code with no surviving consumer:

- Four disconnected modules: `detect/telemetry.py`, `track/trajectory_eval.py`,
  and `telemetry/{__init__,monitor}.py`. The active monitoring implementations
  remain under `app/monitoring` and the runtime services; `REQ.md` now describes
  those locations.
- Ten unused private helpers in trend/fatigue analysis, stereo uncertainty and
  assignment, training reports, the calibration dialog, and the old quick
  detector panel. Active extracted classification/covariance/settings workflows
  remain. Obsolete confidence-as-fatigue computations were removed while the
  compatibility output field remains zero.
- Seven write-only private fields in detection-threading, settings/games,
  trajectory display, recording controls, and review actions. Public constructor
  signatures and menu ownership remain intact.
- Two disconnected launcher helpers, `_darken_color` and `_launch_setup`, plus
  the invoked but empty `_set_window_icon` placeholder.
- Unused PyInstaller hook imports in `launcher.spec`.

Compatibility shims (`InProcessPipelineService`, `ui.qt_app`, review/session
aliases), public trajectory contracts/registries, operator scripts, tests,
archives, schema mirrors, recordings, calibration, configs, and user assets
were retained. Static repository analysis cannot rule out arbitrary external
reflection; it does not justify deleting supported public APIs.

## Validation

The initial Python 3.13.14 baseline passed 88 focused tests and schema, public
documentation, file-length, and typing-policy checks.

| Gate | Result |
|---|---|
| Full Windows Python 3.13.14 suite, native UVC probe disabled, two loadscope workers | 1,750 passed; 32 skipped; 37 warnings; exit 0; 277.37 s |
| Full Windows Python 3.14.7 suite, native UVC probe disabled, serial isolated worktree | 1,750 passed; 32 skipped; 11 warnings; exit 0; 565.48 s |
| Fresh frozen-worker smoke tests | 4 passed; exit 0; 12.23 s |
| Direct repository-wide mypy on Python 3.13 | Clean, 739 source files |
| Flake8 | Zero findings in repository sources |
| Schema mirror, public docs, file length, typing policy, Windows-aware whitespace | Passed; zero grandfathered source files |
| PyInstaller 6.18.0 GUI and worker bundle | Built successfully; 193.39 s |
| Inno Setup installer compilation | Successful; unsigned; 159.55 s |

The full suites validate `6025503`. The later build-only import cleanup passed
all five packaging contract tests; it does not change runtime behavior. Existing
warnings are dependency deprecations, intentional OpenCV index-identity warnings,
a synthetic clustering warning, and the existing ChArUco test-return warning.
Skipped tests retain their codec/display/dependency/artifact guards.

Local Flake8/mypy scans excluded only the pre-existing untracked
`docs/reviews/2026-09-09-assets/` in addition to normal repository exclusions.
That user directory contains existing lint/type findings and was not edited or
staged. No policy suppressions or CI configuration were relaxed.

The first full run found three failures: a simulator integration test assumed
50 GB of real disk space, then its obsolete private-state cleanup leaked
recording workers and caused two later rollback checks to fail. `6025503`
controls disk availability only inside the normal-path test, explicitly sets
temporary recording output, and guarantees public `shutdown()` in `finally`.
Production disk thresholds remain unchanged. The affected integration and
characterization suites then passed together (18 tests); both full runtime
suite reruns passed against the corrected tree.

## Build artifacts

Fresh bundle: `dist/consolidation-2026-10-02/PitchTracker/`. Existing bundles and
installer output were preserved. It contains the GUI and dedicated console
worker. The final bundle was built from `5539056`. Runtime source matches
`4a7cee3`; `6025503` only updates integration tests, and `5539056` removes unused
build-spec imports. The installer uses an ignored copy of `installer.iss`
with paths redirected to this fresh bundle and a separate output directory.

- `PitchTracker.exe` SHA-256:
  `FD7C33F65B43DF766DC9FAF59DA23C9696E3DE1A39B298238B8CB0FA38C69B42`
- `PitchTrackerWorker.exe` SHA-256:
  `78C10D67F7F97F23AC2A9A2A737B847872330099EC2C35A4CA6C1E6E934ED225`
- `installer_output/consolidation-2026-10-02-final/PitchTracker-Setup-v2.0.0-stereo-consolidation.exe`
  SHA-256: `95CD8DFD0BE94C47628CBE48D5457CDCB6D27FB12DB5022B1FAB476B86CF9A86`.
  This is a local unsigned installer, not a published release.

Smoke tests cover health and camera-probe help without camera I/O, synthetic
trajectory fitting against source, simulator setup capture, and tooling
environment validation. PyInstaller emits optional-import/system-DLL warnings;
local smoke success does not replace clean-machine GUI/installer qualification.

## Remaining operator gates

No operator-led physical camera capture was performed; lifecycle/discovery tests
use fakes and frozen setup uses the simulator. No private media or calibration
data was uploaded. The existing untracked review assets were preserved.
Operator-run real-rig disconnect, backend-switch, setup/launcher close, and
clean-machine install/update/uninstall/reinstall tests remain necessary.
No physical accuracy approval, release, push, or publication is implied.
