# Platform Assessment

## Recommendation

Retain Python, PySide6, OpenCV, NumPy, and SciPy. Do not start a rewrite or native POC from the present evidence. The measured slow paths call native-heavy libraries, the representative host is not established, and no Python-exclusive hot path has been shown to consume 30% of end-to-end cost.

Official ecosystem facts support incremental options: [Qt for Python is the official Qt binding](https://doc.qt.io/qtforpython-6/index.html), and Qt documents desktop deployment choices including its Nuitka-based tool and PyInstaller ([deployment overview](https://doc.qt.io/qtforpython-6.8/deployment/index.html)). [PyO3 supports native Python extensions and incremental Rust modules](https://pyo3.rs/main/), but its own [performance guide](https://pyo3.rs/main/performance.html) documents boundary/GIL costs. CPython 3.13 free threading remains [experimental and requires extension support](https://docs.python.org/3.13/howto/free-threading-extensions.html). Go can call C through [cgo](https://go.dev/wiki/cgo), while .NET's official guidance recommends a stable C ABI because C++ has no cross-platform ABI ([native interoperability](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/abi-support)). These facts make a Python-hosted native island feasible, not automatically beneficial.

## Weighted scorecard

Scores are 1–5, where 5 is favorable. The supplied weights total 100.

| Criterion (weight) | Python | Python+Rust | Full Rust | Go | .NET | C++ |
|---|---:|---:|---:|---:|---:|---:|
| Performance (8) | 2 | 4 | 5 | 4 | 4 | 5 |
| Latency (7) | 2 | 4 | 5 | 4 | 4 | 5 |
| Throughput (7) | 2 | 4 | 5 | 4 | 4 | 5 |
| Memory (3) | 3 | 4 | 5 | 4 | 4 | 5 |
| Reliability (8) | 3 | 4 | 4 | 4 | 4 | 3 |
| Developer productivity (7) | 5 | 3 | 2 | 4 | 4 | 2 |
| Ecosystem compatibility (7) | 5 | 4 | 2 | 2 | 3 | 5 |
| Replacement cost (7) | 5 | 4 | 1 | 1 | 2 | 3 |
| Migration complexity (6) | 5 | 4 | 1 | 2 | 2 | 2 |
| Operational complexity (5) | 4 | 3 | 2 | 3 | 3 | 2 |
| Deployment complexity (4) | 4 | 3 | 2 | 4 | 4 | 2 |
| Observability (4) | 3 | 3 | 3 | 4 | 4 | 3 |
| Security (5) | 3 | 4 | 5 | 4 | 4 | 3 |
| Maintainability (7) | 4 | 4 | 3 | 4 | 4 | 2 |
| Hiring/skills (3) | 4 | 2 | 2 | 4 | 4 | 3 |
| Incremental migration (6) | 5 | 5 | 2 | 2 | 2 | 3 |
| Regression risk (6) | 5 | 4 | 1 | 2 | 2 | 2 |
| **Weighted total / 5** | **3.75** | **3.80** | **2.98** | **3.42** | **3.46** | **3.29** |

The hybrid's slightly higher conditional score reflects potential, not authorization to migrate. Python wins the present decision because the POC entry condition is not met and regression/replacement evidence dominates near-term value.

## PLAT-001 — Native POC gate

- **Finding:** No separable Python-bound component has been demonstrated at ≥30% of representative CPU or wall time after native library, codec, filesystem, and emulation costs are excluded.
- **Evidence:** Detector and trajectory timings are slow, but their stacks rely on OpenCV/NumPy/SciPy; no native-stack profile or representative hardware run attributed the cost to Python.
- **Impact:** A language experiment now would optimize an unknown and add packaging risk.
- **Confidence:** High about missing evidence; medium about eventual opportunity.
- **Recommendation:** Retain Python and profile first. Prefer Rust/PyO3 or a narrow C++ boundary only if the entry threshold is met.
- **Dependencies:** Corrected end-to-end benchmark, representative x64/ARM64 builds, deterministic parity fixtures.
- **Effort:** Small to decide; medium for profiling; large only if a POC passes.
- **Definition of Done:** Entry: ≥30% separable Python-bound share. Go: deterministic parity plus ≥25% lower p95, ≥25% higher throughput, or ≥30% lower CPU at equal throughput, with no material memory, packaging, deployment, or diagnostic regression. Stop below 20% improvement, on correctness divergence, when already native-bound, or when Windows packaging becomes materially less reliable.

A full rewrite is out of scope unless multiple non-isolatable Python-bound paths exceed 50% of end-to-end cost and an incremental boundary is proven infeasible.
