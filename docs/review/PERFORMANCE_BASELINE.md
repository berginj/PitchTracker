# Performance Baseline

## Environment and semantics

Audit host: Windows 11 Home Insider Preview build 29639, ARM64 Snapdragon X (12 cores), with Python 3.13.14 AMD64 and OpenCV 4.10.0 x64 under emulation. OpenCV reports FFmpeg, DirectShow, and MSMF; no GStreamer or CUDA. Results are not representative of supported x64 systems or physical cameras.

All measurements used deterministic synthetic frames/observations, warm-up, three repetitions where practical, terminal queue outcomes, `perf_counter_ns`, process CPU time, and RSS. No repository benchmark or runtime file was modified. Temporary probes and screenshots were deleted.

## Corrected results

| Workload | Result |
|---|---|
| Classical detection 1280×720 | 20.64–21.16 fps; p50 46.95–48.19 ms; p95 49.82–51.86 ms; p99 50.84–53.53 ms; max 54.87 ms |
| Classical detection 1920×1080 | 8.44–8.80 fps; p50 106.70–109.51 ms; p95 139.45–163.51 ms; p99 156.74–211.36 ms; max 230.28 ms |
| Burst dual stream, 360 submissions | 360 terminal outcomes/run; only 14–15 `PROCESSING_COMPLETE`; 345–346 input drops; terminal throughput is not processing throughput |
| Stereo 3D trajectory | 3/3 success; p50 1,349.32 ms; p95 1,358.58 ms; max 1,359.61 ms |
| Ray reprojection | 3/3 success; p50 1,090.68 ms; p95 1,342.45 ms; max 1,370.42 ms |
| Ray graph | 3/3 success; p50 867.76 ms; p95 869.89 ms; max 870.12 ms |
| Rapid lifecycle | 100 detection-pool start/stop cycles in 21.24 s; no probe exception |
| Five-minute memory | 5,948 submissions/terminal outcomes; 5,930 processed, 10 input drops, 8 other outcomes; RSS 126.6–191.3 MiB, end 171.9 MiB |

The memory series was non-monotonic and bounded during five minutes, but the 45.3 MiB cold-start-to-end increase prevents a claim of long-term stability. Disk I/O was negligible in these non-recording probes. CPU time per 30-frame detector run was 1.47–1.70 s at 720p and 3.94–4.17 s at 1080p. Native OpenCV/NumPy/SciPy time was not separable from interpreter time without native-stack profiling.

Launcher readiness, simulator pitch end-to-end latency, recording throughput, compositor/render latency, native hot-function attribution, and physical 60 fps are **Cannot verify in this baseline**: coaching construction fails; offscreen Qt disables writers on this host; no physical rig was selected; and the temporary probes did not claim unsupported profiler attribution.

## PERF-001 — Existing benchmark semantics are invalid

- **Finding:** `benchmarks/throughput.py` reports submitted frames as processed after a fixed one-second sleep; related latency paths use fixed sleeps and may time only detector calls or an observed subset.
- **Evidence:** Source inspection compared counters, enqueue paths, callbacks, and formulas. The corrected burst showed 360 terminal outcomes but only 14–15 processed frames.
- **Impact:** Current “60 FPS pass” and optimization claims can be wrong by orders of magnitude.
- **Confidence:** High.
- **Recommendation:** Define offered, accepted, processed, failed, cancelled, and dropped denominators; await terminal conservation; report distributions and host identity.
- **Dependencies:** Stable event metadata and benchmark fixtures.
- **Effort:** Medium.
- **Definition of Done:** Benchmark totals conserve every opportunity; fixed sleeps are absent from completion logic; CI artifacts include raw samples/config/commit/host; no target is marked pass without the correct denominator.

## PERF-002 — Current host misses the processing target

- **Finding:** A single classical detector stream is below 60 fps at both required resolutions on this emulated host, and two-stream bursts drop most inputs.
- **Evidence:** Three repeated results above; 345–346/360 burst submissions were input drops.
- **Impact:** The 1080p60 product target is not supported by current host evidence.
- **Confidence:** High for this environment, low for representative hardware.
- **Recommendation:** Profile representative native x64 and ARM64 builds with real frame pacing before changing language; optimize ROI/resolution/algorithm scheduling first.
- **Dependencies:** Qualified cameras, representative build, corrected benchmark.
- **Effort:** Medium-large.
- **Definition of Done:** On named target hardware, sustained dual 1080p60 input records processed/drop denominators and meets the accepted budget for a full session; capture-to-summary p95 is within the requirement.
