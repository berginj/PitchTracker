"""Performance benchmarking suite for PitchTracker.

This package contains benchmarks to measure:
- Frame processing throughput (FPS)
- Detection latency (p50, p95, p99)
- Memory stability over time
- Pipeline performance under load

Run all benchmarks: python -m benchmarks.run_all
Run specific benchmark: python -m benchmarks.throughput
"""
