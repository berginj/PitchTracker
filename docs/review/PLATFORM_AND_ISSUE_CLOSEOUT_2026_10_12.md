# Numerical platform qualification and issue reconciliation — 2026-10-12

Baseline: `6b4bdd5`, plus the accompanying service-import and packaged-worker
cleanup changes. These checks use synthetic numerical inputs. Physical pitch
accuracy, camera timing and field-recording performance remain separate gates.

## Current committed CI

[CI run 38322158037](https://github.com/berginj/PitchTracker/actions/runs/38322158037)
passed for `6b4bdd5`: Python 3.13 and 3.14 each passed **1,943 tests with 33
skips**. Both built the float64 CPU extension. Canonical Python 3.13 mypy passed
for 820 files; schema, documentation, lint, file-length and native UVC checks
passed. These counts cover the baseline rather than subsequent edits.

The accompanying source changes passed full local Python 3.13 and 3.14 suites:
**1,942 passed, 45 skipped** on each runtime. These x64 environments do not have
the optional compiled extension, and the packaged-worker tests require explicit
selection; their successful native/frozen runs are recorded below. Repository
mypy passed for 823 source files. Schema, public docs, file length, lint and
typing-policy checks passed. Pre-existing untracked review scratch files were
excluded from source lint/type checks and left unchanged.

## Native ARM64 numerical qualification

The actual host is Windows 11 ARM64 Insider build 29683 on a Qualcomm Snapdragon
X1E80100 with an Adreno X1-85 GPU. Python 3.13.15 reports `win-arm64` and runs
natively: `IsWow64Process2` returns process-machine zero and host-machine
`0xaa64`. Both the extension and standalone numerical executable have ARM64
PE machine `0xaa64`. The numerical environment uses NumPy 2.3.5, SciPy 1.17.0,
pybind11 3.1.0 and PyInstaller 6.14.2 without Qt or OpenCV.

Native ARM64 Zig 0.16.0 crashed during compilation with status `0xc0000005`.
Zig 0.15.2 running in x64 emulation successfully cross-compiled the ARM64
extension with floating-point contraction disabled. This validates the native
numerical execution on this host, not an MSVC production wheel or the full
native ARM64 GUI/video-processing stack.

Qualified local artifact SHA-256 values:

- ARM64 extension: `d67179c6947846713634181ddcb0e34c35f865501c2448866bca02870585526a`.
- Standalone worker: `97d6c2678fcdc1e38b66eb6357dc6f169d6855a7027de00f622bbc831106db47`.

The compiled numerical regression suite passed **39 tests with zero skips**:
residual/Jacobian parity, reference fit decisions, deadlines, restart/shutdown,
fallback and dispatcher failures. CUDA test doubles prove software behavior;
they are not GPU hardware measurements. The independent 28-case model-envelope
sweep also completed on ARM64.

Ten repeats of the synthetic 60-observation benchmark measured:

| Operation | Median | p95 |
|---|---:|---:|
| Fit with Python reference residual | 957.16 ms | 1002.90 ms |
| Fit with compiled ARM64 residual/Jacobian | 12.88 ms | 15.88 ms |
| Warm supervised ARM64 worker | 14.99 ms | 16.57 ms |

Median direct-fit speedup was **74.34x**. Crossing differences were at most
`5.66e-10 ft`, with matching failure decisions. Warm-up took 634 ms. These
timings exclude detection, decoding, recording and UI work; they are not a
latency guarantee or a physical accuracy measurement.

The standalone worker was exercised from x64 Python 3.13 and 3.14 clients.
Each checked 15 noisy/outlier fits against the reference, persistent reuse,
explicit CUDA/Auto CPU fallback and unavailable ray models. Cancellation and
recovery also passed on both clients with cleanup below three seconds.
The initial one-file bootloader cleanup exceeded five seconds because its
application child remained alive. The fix terminates the owned Windows process
tree using [taskkill /T](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill).
The test waits for child-process exit; PID disappearance is unreliable while
Windows process handles remain open.

## CUDA outcome and remaining platform gates

No NVIDIA device, NVIDIA driver tooling or CUDA compiler was found. Running
`scripts.qualify_cuda` rejected qualification with exit code 2 and created no
receipt. Auto GPU admission remains unavailable. NVIDIA's
[Windows CUDA requirements](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html#system-requirements)
require a CUDA-capable GPU; the Adreno device does not provide that path.

Actual NVIDIA parity, end-to-end throughput, device-loss, thermal/low-memory and
recorded-workload qualification remain outstanding. MSVC ARM64 wheels, native
ARM64 OpenCV/GUI distribution, clean-machine installer tests and physical field
confirmation also remain unqualified. Local reports and binaries stay in
ignored output directories; private recordings, calibration files and logs are
not part of this record.

## Issue acceptance reconciliation

Criterion numbers follow each original checklist. Verified software behavior
does not credit an incomplete physical or conditional acceptance gate.

| Issue | Verified criteria and evidence | Remaining criteria | Disposition |
|---|---|---|---|
| [#34](https://github.com/berginj/PitchTracker/issues/34) | 1–3, 5: timing contracts, receipt/exposure distinction, clock/uncertainty/epoch regressions | 4, 6: independently verified timing model, optical procedure and permitted skew on the measurement rig | Open |
| [#35](https://github.com/berginj/PitchTracker/issues/35) | 1–4: radial/tangential/asymmetric/zero-distortion truth, raw pixels, covariance, double-undistortion rejection and accepted-but-wrong old gate control | 5: changed-pipeline/artifact physical revalidation under #10 | Open |
| [#36](https://github.com/berginj/PitchTracker/issues/36) | 1, 3–7: inverse-foot units, disabled default prior, covariance whitening, independent truth/windows/seeds, identifiability and physical gate | 2: a declared physical operating model for any opt-in prior; seeds/bounds are not that model | Open |
| [#37](https://github.com/berginj/PitchTracker/issues/37) | 1–6: full-volume swept sphere/radius, unavailable gaps/boundaries, 30/60/120 FPS, phase shifts, speeds, both ball radii, misses and consistent crossing/cell behavior | None in this deterministic geometry issue; physical location confirmation stays in #10 | Closed as completed |
| [#38](https://github.com/berginj/PitchTracker/issues/38) | 1, 2, 4, 5, 7: heuristic labels, unavailable prediction error, failure usability gates, covariance/timing/missing/nonconvergence cases and model-limit docs | 3, 6: complete physical uncertainty synthesis if introduced, then independent empirical interval coverage | Open |
| [#39](https://github.com/berginj/PitchTracker/issues/39) | 1–6: observed-point location/time, separate durable vision/external values, matching-plane validation, assisted rejection, cropped windows, failed fits, manual/radar inputs | None in this provenance issue; physical matched-plane comparison stays in #10 | Closed as completed |
| [#40](https://github.com/berginj/PitchTracker/issues/40) | 1, 2, 4, 6: independent lift/control/cropped-window sweep with speed/plate bias, stereo default and unavailable RPM | 3, 5, 7: physically supported envelope/comparison model, any future movement metric baseline, confirmation of expanded claims | Open |

Original reproductions now return:

- #34 identical receipts: `UNKNOWN`, pairing `GOOD`, exposure sync unverified.
- #36 seven-sample 60 mph truth: `60.000000086 mph`, fitted
  `k=0.00150000000012 ft^-1`, RMS `2.60e-7 inches`, no failure codes.
  The 0.5624 mph model-conditional speed standard deviation is not a physical
  accuracy bound.
- #37 between-frame crossing: available estimated strike, row 2, column 1.

Evidence sources: `test_sync_check.py`, `test_measurement_geometry_regressions.py`,
`test_trajectory_measurement_regressions.py`, `test_strike_uncertainty.py`,
`test_speed_provenance.py`, `test_physical_validation_v2.py`,
`test_trajectory_model_envelope.py` and `test_numerical_platform.py`.

## Reproduce the numerical-only checks

Use ARM64 Python with `requirements-numerical.txt` and a compatible native
extension. Build with `numerical_worker.spec`, set
`PITCHTRACKER_QUALIFICATION_WORKER` to that executable, and run:

```powershell
python -m pytest tests/test_numerical_platform.py -q
```

These integration tests skip without an explicitly selected executable. Source
checks and `scripts.benchmark_fitting` remain independently available.
This workflow does not open cameras.
