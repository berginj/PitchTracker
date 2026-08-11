# Test Confidence Review

## Results

| Check | Result |
|---|---|
| Schema mirror | Pass |
| File-length gate | Pass with 34 grandfathered files |
| Flake8 | Pass, zero findings |
| Mypy advisory | 1,447 errors in 136 of 261 checked files; not a required gate |
| Local safety tool | Unavailable; latest GitHub security job passed |
| Collection | 1,302 tests |
| Focused xdist | 147 passed, 13 failed, 4 skipped |
| Full xdist/offscreen | 1,233 passed, 36 failed, 33 skipped, 177 warnings; 65.04 s pytest execution |
| Full serial/offscreen | 1,235 passed, 34 failed, 33 skipped, 23 warnings; 425.60 s |
| Latest HEAD Actions | Run `29923290687`: Python 3.11, Python 3.12, and security jobs passed |

The plan's reconnaissance result (1,232 passed, 38 failed, 32 skipped) is superseded by the fresh results above. Serial execution removed two race/environment failures; every displayed serial failure shared the recording writer/offscreen condition.

## TEST-001 — Ten UI workflows are falsely skipped

- **Finding:** `tests/test_ui_workflows.py` reports pytest-qt unavailable despite the installed plugin and working `qtbot` fixture.
- **Evidence:** The guard imports `pytest_qt.plugin.QtBot`; pytest-qt installs/imports as `pytestqt.plugin`. Ten tests skip with the false reason.
- **Impact:** Important UI workflow regressions, including coaching construction, can reach green CI.
- **Confidence:** High.
- **Recommendation:** Use the fixture/plugin's actual module or remove the import guard and let pytest resolve `qtbot`.
- **Dependencies:** A CI-safe Qt platform strategy.
- **Effort:** Small.
- **Definition of Done:** The ten tests execute on both CI Python versions and fail if core windows cannot construct.

## TEST-002 — UI and codec verification are coupled incorrectly

- **Finding:** The offscreen Qt environment causes OpenCV video writers to fail on this host, while the same writers open outside offscreen mode.
- **Evidence:** With offscreen set, H264, avc1, XVID, MP4V, and MJPG all fail and produce 34 serial failures. Without it, a direct `SessionRecorder`/FFMPEG probe succeeds and all five `VideoWriter` choices report open; H264 first reports an OpenH264 mismatch, then uses a platform fallback.
- **Impact:** A single full-suite invocation cannot prove both UI behavior and recording portability here; failures can be misclassified as absent codecs.
- **Confidence:** High for this host; packaged-machine behavior cannot verify.
- **Recommendation:** Split headless non-Qt recording tests from offscreen UI tests, make codec capabilities explicit, and add a packaged clean-machine smoke lane.
- **Dependencies:** #11 and supported-codec policy.
- **Effort:** Medium.
- **Definition of Done:** Non-Qt recording tests pass with an enumerated supported codec; UI tests run offscreen without initializing recording; clean x64 and ARM64 evidence records codec/container/backend.

## TEST-003 — Skip inventory contains stale and optional coverage

- **Finding:** The 33 serial skips comprise ten false pytest-qt skips, ten opt-in stress/memory tests using stale/currently guarded APIs, eight staged TAG integration tests, three GUI-environment tests, one video-clip fixture guard, and one codec fallback.
- **Evidence:** Pytest skip reasons and source guards were reconciled individually.
- **Impact:** A single skip count hides defects, staged functionality, expensive tests, and unavailable fixtures.
- **Confidence:** High.
- **Recommendation:** Categorize skips in CI and set budgets per category; eliminate false/stale skips first.
- **Dependencies:** TEST-001/002.
- **Effort:** Medium.
- **Definition of Done:** CI publishes skip categories and owners; no skip claims an installed dependency is missing; active stress tests use current APIs and run on a schedule.

## Capability confidence

High: config/schema mirror, core typed contracts, deterministic pitch state, synthetic trajectory behavior, service-level logic. Medium: setup, capture abstractions, detection, analysis, review/export. Low: physical accuracy, coaching UI, packaged recording, installer/updater, staged cloud/Bluetooth, real-camera recovery.
