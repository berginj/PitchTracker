"""Performance benchmarking suite for PitchTracker.

This package contains benchmarks to measure:
- Frame processing throughput (FPS) with terminal-outcome conservation
- Detection latency (p50, p95, p99) with terminal-outcome conservation
- Memory stability over time with terminal-outcome conservation
- Pipeline performance under load

Every benchmark conserves offered opportunities: the sum of processed,
failed, dropped (input/result), and cancelled/other terminal outcomes
must equal the total offered count.  Fixed sleeps are never used as
completion logic; benchmarks wait on an event/condition for all
terminal outcomes before collecting results.

Run all benchmarks: python -m benchmarks.run_all --quick
Run specific benchmark: python -m benchmarks.throughput --frames 30
"""
