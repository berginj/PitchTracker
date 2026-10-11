# Local fitting and evaluation

Last reviewed: 2026-10-11

The application remains Python, Qt, NumPy and SciPy. The optional C++ extension
accelerates the stereo physics residual and its Jacobian; it does not replace
the optimizer or the application. Default trajectory mode remains `stereo_3d`.
Ray fitters still use their existing implementation and remain comparison-first.

## What runs where

Live primary fits use one persistent numerical subprocess. Its imports stay
warm, BLAS/OpenMP thread counts are one, and each request has a correlation ID,
generation and request token. Queue admission, pipe writes, execution and response decoding
consume the deadline. Timeout, cancellation or invalid identity kills and reaps
the child; the next request starts a fresh generation. Configuration, ball
radius, manual speed and ray camera models are copied for each analysis job.

Primary summaries publish before optional comparisons. Comparisons have a
separate worker and bounded queue, publish `TrajectoryComparisonEvent`, and are
persisted by RecordingAgent in `trajectory_comparisons.json` and the decision
journal. Required inputs publish as `TrajectoryFitPreparedEvent`: the complete
request includes covariance, camera arrays, settings, units and correlation.
Failed comparisons cannot replace a primary summary. Analysis shutdown drains
accepted work before recording finalizes the journal.

CPU-native evaluation uses float64 forward sensitivities of the same discrete
RK4 steps as the reference implementation. SciPy retains bounds, Huber loss,
scaling, convergence and uncertainty diagnostics. `reference` selects the
previous Python residual and finite-difference Jacobian. Without the extension,
CPU falls back to that reference implementation.

## Install and select

Build a wheel with a C++17 toolchain for the **Python process architecture**:

```powershell
python -m pip install ./native
```

Windows production builds use CMake/MSVC. The development-only
`python scripts/build_native.py` supports an installed `ziglang` compiler.
`PITCHTRACKER_ZIG` can point to its executable. Never copy an x64 extension into
an ARM64 Python environment, or a CPython 3.13 extension into 3.14.
PyInstaller includes the optional installed extension and the new workers.
CI builds the CPU extension on both supported Python versions.
`build_installer.ps1` also builds it before bundling. Use `-CudaKernel` for a
CUDA toolchain build, or `-SkipNativeKernel` when supplying an already installed
qualified wheel. This prevents a normal installer build from silently omitting
the compiled CPU path.

A separate numerical-only worker can use a different architecture from the GUI.
In the target Python/toolchain environment, install `requirements-numerical.txt`
and the native extension, then run `pyinstaller numerical_worker.spec`. Select
the resulting executable explicitly with `PITCHTRACKER_NUMERICAL_WORKER`.
The same persistent JSON protocol crosses the architecture boundary. This
distribution excludes Qt and OpenCV; stereo physics works independently of
those libraries, while ray requests return a structured missing-camera-model
failure until a distribution with distortion support is supplied.
An x64 standalone worker was built and exercised locally for stereo fitting,
ray rejection, persistent protocol and clean exit. That test does not qualify
an ARM64 build. The numerical requirements select a NumPy version with native
ARM64 wheels without changing the application's existing x64 runtime pins.

Coaching Settings exposes CPU, Auto and NVIDIA GPU; the selection is retained
in local app state. Config-only deployments use `trajectory.compute_backend`.
Each batch has its own immutable backend and worker selection.

CUDA is an optional build, not an installation requirement:

```powershell
python -m pip install ./native --config-settings=cmake.define.PITCHTRACKER_CUDA=ON
```

The CUDA evaluator keeps observation arrays resident and provides a batched
float64 residual/Jacobian API. SciPy optimization remains on CPU. Explicit GPU
selection checks residual/Jacobian parity against the compiled CPU evaluator
before use. Device errors fall back to CPU within the supervised deadline.
Diagnostics record the requested/effective backend and fallback reason.
Compatible concurrent stereo jobs share one supervised GPU process. Its bounded
dispatcher groups requests by observation count and prior settings; independent
SciPy optimizers feed a shared resident evaluator through a short coalescing
window. Constant observation arrays upload once per group, while parameters and
results move each iteration. One ineligible fit releases registration so peers
can fall back to CPU. Queueing, shared execution and decoding consume the hard
deadline; a failed group can retry eligible members on CPU within remaining time.

Auto additionally requires a matching end-to-end qualification receipt:

```powershell
python -m scripts.qualify_cuda --workers 1 --output research/cuda-qualification.json
$env:PITCHTRACKER_CUDA_QUALIFICATION = (Resolve-Path research/cuda-qualification.json).Path
```

The receipt binds device/driver, extension binary, source implementation,
Python architecture, numerical libraries, observation count and concurrency.
It must demonstrate matching failure decisions, speed within 0.01 mph,
plate crossing within 0.001 ft and crossing time within 0.1 ms, plus at least
1.5x whole-workload throughput. No suitable receipt means Auto uses CPU.
A receipt for eight workers does not admit a one-worker live fit.
Kernel parity alone does not qualify Auto or establish physical accuracy.

## Batch refits and video replay

Open Review → Measurement Validation → Batch refits. Select one or more
sessions, a separate output directory, compute backend, and Auto or explicit
worker count. Auto reserves two physical cores and caps the pool at eight.
Workers accept one request at a time. New offline work pauses while local
CaptureAgent owns capture; admitted fits finish within their deadlines.

Observation refits verify the closed decision journal and reuse its complete
requests. Legacy per-pitch evidence is integrity checked and labelled
`legacy_reconstructed`: original settings and plate plane may be missing.
Those assumptions remain visible in derived results. Incomplete journals block
the session instead of silently excluding missing evidence.

```powershell
python -m scripts.refit_sessions --session recordings/session_A --output research/refits --workers 4
```

Settings sweeps reuse this command or the dialog with different JSON overrides
(`drag_k0`, `drag_sigma`, prior enablement, noise, fit iterations, deadline,
wind, speed uncertainty gate, or plate plane). Input/settings/backend/library
hashes determine cache identity. Completed successful fits resume from
`results/<hash>.json`; failures retry. Reports retain failed results and session
blockers. Cancel stops workers and preserves completed cache artifacts.
Captured sessions are read-only. Derived results never issue an accuracy
approval or silently alter a study. “Apply refit to case” explicitly updates
the selected shadow case's measured fields; independent references stay owned
by the study. Confirmation datasets reject this action.

Video replay requires explicit config, full production-ready stereo calibration,
lane/plate ROI JSON and a field-transform JSON matching `FieldTransform`.
It decodes both session AVI files in recorded timestamp order, synchronously
uses the existing detectors, stereo association and pitch state machine, and
retains terminal pairing counts. The decoder runs in a separately supervised
process with cancellation and a one-hour active timeout. It never opens cameras.
Inputs are hashed and checked again after replay. Reprocessed results remain
research evidence, not an assertion that those files were the original setup.
Replay accounting is saved under the derived output's `replays/` directory,
including offered frames, failed writes and rejected pitch attempts even when
there are no accepted fits. Review loads delayed comparison artifacts separately
from the recorded primary manifest.

New session timestamp CSVs append `encoded_frame_index` and `write_status`.
An OpenCV `write()` returning `None` means no reported failure; it is not proof
that bytes reached disk. Replay additionally verifies decoded frame counts,
contiguous mappings, dimensions, timestamp ordering and capture epoch. Failed
writes have no encoded index. Legacy CSVs without explicit mappings, missing
files, quick calibration or mismatches block replay rather than invent timing.

## Measured scope and remaining qualification

```powershell
python -m scripts.benchmark_fitting --repeats 5 --output research/fitting-benchmark.json
```

On the development RTX Spark N1X host, **x64 CPython under Windows ARM64
emulation**, a five-run synthetic 60-observation case measured:

| Path | Median | p95 |
|---|---:|---:|
| Reference residual | 1482 ms | 1513 ms |
| Compiled CPU residual/Jacobian | 18.5 ms | 21.8 ms |
| Warm supervised CPU worker | 28.8 ms | 34.8 ms |

The direct-fit median speedup was 80x; the earlier run measured 61x. The
[final benchmark artifact](review/fitting-benchmark-2026-10-11.json) contains
individual runs, implementation hashes and parity differences.
This excludes cold worker startup,
detection, decoding, UI refresh and disk persistence. It is a development
benchmark, not a production latency SLA or a physical validation result.
The broader target remains >=5x offline throughput, warm fit p95 below 250 ms,
and primary publication below 500 ms on qualified representative workloads.
`queue_and_analysis_ms` reports queue-to-publication preparation time separately
from numerical fit and worker roundtrip time; it excludes later UI rendering.

CUDA source and admission controls are implemented, but this host has no
qualified CUDA toolchain/build or end-to-end GPU result. Native ARM64 and
NVIDIA performance remain manual release gates. The local CPU measurements
do not validate native ARM64. Native Windows ARM64 video processing also
needs an OpenCV build. The numerical-only worker has a separate packaging
recipe, but its native ARM64 wheel/executable still needs platform qualification.
The shared GPU scheduler is exercised with a CPU-backed CUDA test double,
including independent optimizer parity and pre-objective rejection. Its actual
CUDA throughput remains unqualified until the GPU build is tested on hardware.
Blocked pipe-write and shared-worker hang tests verify deadline enforcement
and process reaping. Unexpected device initialization errors release all
optimizers to the compiled CPU fallback.
Before enabling Auto on a platform, run the kernel/fit suite, qualification
command, recorded-session throughput, cancellation/thermal/low-memory tests,
and compare field-recording eligibility decisions without changing truth data.

Validation for this change: the final Python 3.13 regression run passed 1,914
tests with 34 hardware/optional skips. The earlier full Python 3.14 run passed
1,904 tests with 34 skips. Subsequent Python 3.14 checks passed the 19 video/review
checks and 26 fitting/runtime/backend checks; the final seven shared-GPU tests
also passed on both versions, including the added device-initialization failure.
Lint, canonical 3.13 typing, schema mirror, documentation links and file-length
checks passed. No cameras or captured athlete recordings were used. CUDA
execution was not included in these automated results.
