# PitchTracker Executive Review

Audit date: 2026-08-11

Released-source baseline: `main` at `e8a1009c72163ff990e9022f6a6902d38814e25f`

Development baseline: the same commit plus 13 modified and 2 untracked camera/setup files

## Decision page

PitchTracker is a substantial, locally operated Windows desktop prototype with broad automated coverage and unusually explicit evidence contracts. It is not yet trustworthy as a source of physical pitch speed, location, or strike decisions because no representative global-shutter rig has completed the documented field-validation program. The code is suitable for continued engineering and simulator work; it is not ready for accuracy claims or an unattended field pilot.

The system currently appears to exist to **help baseball and softball coaches capture, reconstruct, review, and export pitch evidence on a local Windows laptop by combining synchronized stereo video, configurable detection, a pitch lifecycle, trajectory fitting, and durable session artifacts**.

| Question | Answer |
|---|---|
| Trustworthiness | Automated contracts are broad, but physical accuracy is unvalidated and local full-suite verification is environment-sensitive. Do not use outputs as ground truth. |
| Product alignment | Strong intent alignment; incomplete evidence alignment. The UI and backlog still expose prototype gaps that block the intended operator workflow. |
| Functional health | HEAD CI passed Python 3.11 and 3.12. This audit collected 1,302 tests; serial offscreen produced 1,235 passed, 34 failed, 33 skipped. The 34 failures share a codec/offscreen root. |
| Documentation usability | The evidence boundary is mostly good, but counts, completion wording, performance claims, and setup-step counts drifted. This audit corrects canonical claims and supplies a traceable review package. |
| Agent readiness | Agent ownership is clear. Required event metadata is not consistently implemented, and Copilot rules conflict with established exception patterns. |
| Architecture | Retain the service/event architecture. Fix UI construction, event metadata, recording portability, legacy divergence, and oversized ownership boundaries before introducing another language. |
| Measured performance | On this ARM64 Windows host running AMD64 Python/OpenCV, classical detection was about 21 fps at 720p and 8.4–8.8 fps at 1080p per stream. These are host-specific software results, not camera throughput. |
| Platform choice | Retain Python. NumPy, OpenCV, and SciPy already perform much work in native libraries; no Python-exclusive hot path has met the 30% POC threshold. |
| Next actions | P0: restore coaching-window construction and create truthful UI/codec test lanes. P1: complete issues #9–#11, metadata, benchmark repair, accessibility, and responsive layouts. P2: resolve module/legacy debt. |

## Executive top ten

1. **ALN-001:** Physical speed, location, and strike-zone accuracy remain unvalidated.
2. **UI-001:** `CoachWindow(backend="sim")` fails during construction because four game widgets call a nonexistent `StyleManager.apply_standard_layout` method.
3. **TEST-001:** Ten UI workflow tests falsely report that pytest-qt is unavailable because they import `pytest_qt`; the installed module is `pytestqt`.
4. **TEST-002:** Setting `QT_QPA_PLATFORM=offscreen` makes all five OpenCV writer choices fail on this host, producing 34 serial failures and preventing one invocation from proving UI and recording behavior together.
5. **PERF-001:** Existing throughput benchmarks count submitted frames as processed and include fixed sleeps; published pass/fail claims based on them are invalid.
6. **PERF-002:** Measured classical detection is far below the 1080p60 requirement on this host, and a burst test dropped 345–346 of 360 inputs.
7. **UI-002:** Setup requires 1,998 pixels of width even after the worktree scroll change; review requires 1,764×1,073 and the launcher requires 1,012×686.
8. **AGT-001:** Durable and asynchronous events still omit parts of the repository's required correlation/session/schema metadata.
9. **RM-001:** Thirty-four files are grandfathered above the 500-line gate; only the first two extraction targets are on the active roadmap.
10. **DOC-001:** Canonical status and performance pages mix historical green-suite evidence with current completion and performance claims.

## Baseline integrity

The released baseline and worktree were not checked out, stashed, or rewritten. The development delta changes UVC device mapping and setup diagnostics, extends setup deadlines, resets shared ROI values, and adds a setup scroll wrapper and tests. Private device identifiers in the untracked catalog were inspected locally but are redacted here. Worktree-only behavior is called out in [DRIFT_MATRIX.md](DRIFT_MATRIX.md).

## Verification boundary

Verified: source and history inspection; GitHub issues/PRs and latest Actions results; schema/file-length/Flake8 gates; collection and focused/full pytest runs; Qt offscreen construction and programmatic accessibility checks; synthetic detector, queue, trajectory, lifecycle, codec, and memory probes.

Cannot verify: physical cameras; real pitch speed/location accuracy; screen-reader behavior; hands-on keyboard/navigation feel; Windows DPI configurations outside the tested offscreen sizes; clean-machine installer/updater behavior; production codec availability; cloud/Bluetooth integrations; physical 60 fps. The Windows computer-control runtime was unavailable, so UI evidence is offscreen/programmatic only.

## Overall recommendation

Continue with Python and the current architecture. Treat this as an evidence-completion and reliability program, not a rewrite program. A native POC becomes justified only when profiling isolates a Python-bound component at 30% or more of representative end-to-end cost and the acceptance gates in [PLATFORM_ASSESSMENT.md](PLATFORM_ASSESSMENT.md) are met.
