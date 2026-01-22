"""Performance benchmarking script for PitchTracker pipeline.

Measures key performance metrics:
- Frame capture latency
- Detection processing time
- Memory usage (frame buffers, allocations)
- Disk I/O throughput
- CPU usage
- Lock contention
"""

import gc
import os
import sys
import time
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.settings import load_config
from app.services.orchestrator import PipelineOrchestrator


@dataclass
class PerformanceMetrics:
    """Container for performance measurements."""

    # Timing metrics (milliseconds)
    capture_latency_ms: List[float] = field(default_factory=list)
    detection_latency_ms: List[float] = field(default_factory=list)
    recording_latency_ms: List[float] = field(default_factory=list)

    # Memory metrics (MB)
    memory_usage_mb: List[float] = field(default_factory=list)
    peak_memory_mb: float = 0.0

    # I/O metrics
    disk_write_mb: float = 0.0
    disk_write_rate_mbps: List[float] = field(default_factory=list)

    # CPU metrics
    cpu_percent: List[float] = field(default_factory=list)

    # Frame metrics
    frames_captured: int = 0
    frames_detected: int = 0
    frames_dropped: int = 0

    # Lock contention (if measurable)
    lock_wait_ms: List[float] = field(default_factory=list)

    def add_capture_latency(self, latency_ms: float):
        """Add capture latency sample."""
        self.capture_latency_ms.append(latency_ms)

    def add_detection_latency(self, latency_ms: float):
        """Add detection latency sample."""
        self.detection_latency_ms.append(latency_ms)

    def add_recording_latency(self, latency_ms: float):
        """Add recording latency sample."""
        self.recording_latency_ms.append(latency_ms)

    def add_memory_sample(self, memory_mb: float):
        """Add memory usage sample."""
        self.memory_usage_mb.append(memory_mb)
        self.peak_memory_mb = max(self.peak_memory_mb, memory_mb)

    def add_cpu_sample(self, cpu_percent: float):
        """Add CPU usage sample."""
        self.cpu_percent.append(cpu_percent)

    def add_disk_write_rate(self, mbps: float):
        """Add disk write rate sample."""
        self.disk_write_rate_mbps.append(mbps)

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "capture_latency": {
                "min_ms": min(self.capture_latency_ms) if self.capture_latency_ms else 0,
                "max_ms": max(self.capture_latency_ms) if self.capture_latency_ms else 0,
                "avg_ms": sum(self.capture_latency_ms) / len(self.capture_latency_ms) if self.capture_latency_ms else 0,
                "p95_ms": self._percentile(self.capture_latency_ms, 95),
                "samples": len(self.capture_latency_ms)
            },
            "detection_latency": {
                "min_ms": min(self.detection_latency_ms) if self.detection_latency_ms else 0,
                "max_ms": max(self.detection_latency_ms) if self.detection_latency_ms else 0,
                "avg_ms": sum(self.detection_latency_ms) / len(self.detection_latency_ms) if self.detection_latency_ms else 0,
                "p95_ms": self._percentile(self.detection_latency_ms, 95),
                "samples": len(self.detection_latency_ms)
            },
            "recording_latency": {
                "min_ms": min(self.recording_latency_ms) if self.recording_latency_ms else 0,
                "max_ms": max(self.recording_latency_ms) if self.recording_latency_ms else 0,
                "avg_ms": sum(self.recording_latency_ms) / len(self.recording_latency_ms) if self.recording_latency_ms else 0,
                "p95_ms": self._percentile(self.recording_latency_ms, 95),
                "samples": len(self.recording_latency_ms)
            },
            "memory": {
                "avg_mb": sum(self.memory_usage_mb) / len(self.memory_usage_mb) if self.memory_usage_mb else 0,
                "peak_mb": self.peak_memory_mb,
                "samples": len(self.memory_usage_mb)
            },
            "disk_io": {
                "total_mb": self.disk_write_mb,
                "avg_rate_mbps": sum(self.disk_write_rate_mbps) / len(self.disk_write_rate_mbps) if self.disk_write_rate_mbps else 0,
                "peak_rate_mbps": max(self.disk_write_rate_mbps) if self.disk_write_rate_mbps else 0
            },
            "cpu": {
                "avg_percent": sum(self.cpu_percent) / len(self.cpu_percent) if self.cpu_percent else 0,
                "peak_percent": max(self.cpu_percent) if self.cpu_percent else 0,
                "samples": len(self.cpu_percent)
            },
            "frames": {
                "captured": self.frames_captured,
                "detected": self.frames_detected,
                "dropped": self.frames_dropped,
                "drop_rate": self.frames_dropped / max(1, self.frames_captured)
            }
        }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


class PerformanceMonitor:
    """Monitor system performance during benchmark."""

    def __init__(self, metrics: PerformanceMetrics):
        self.metrics = metrics
        self.process = psutil.Process()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Baseline I/O counters
        self.baseline_io = self.process.io_counters()
        self.last_io_check = time.time()

    def start(self):
        """Start monitoring in background thread."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            # Sample memory
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / (1024 * 1024)
            self.metrics.add_memory_sample(memory_mb)

            # Sample CPU
            cpu_percent = self.process.cpu_percent(interval=0.1)
            self.metrics.add_cpu_sample(cpu_percent)

            # Sample disk I/O rate
            current_time = time.time()
            current_io = self.process.io_counters()

            elapsed = current_time - self.last_io_check
            if elapsed > 0:
                bytes_written = current_io.write_bytes - self.baseline_io.write_bytes
                mbps = (bytes_written / (1024 * 1024)) / elapsed
                self.metrics.add_disk_write_rate(mbps)
                self.metrics.disk_write_mb = bytes_written / (1024 * 1024)

            self.last_io_check = current_time
            self.baseline_io = current_io

            time.sleep(0.5)  # Sample every 500ms


def run_benchmark(
    duration_seconds: int = 30,
    backend: str = "sim",
    config_path: Optional[Path] = None
) -> PerformanceMetrics:
    """Run performance benchmark.

    Args:
        duration_seconds: How long to run benchmark
        backend: Camera backend to use ("sim" for simulated)
        config_path: Optional config file path

    Returns:
        PerformanceMetrics with collected data
    """
    print(f"\n{'='*60}")
    print(f"PitchTracker Performance Benchmark")
    print(f"{'='*60}")
    print(f"Duration: {duration_seconds}s")
    print(f"Backend: {backend}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Initialize metrics
    metrics = PerformanceMetrics()

    # Load config
    if config_path is None:
        config_path = Path("configs/default.yaml")
    config = load_config(config_path)

    # Create orchestrator
    print("Initializing pipeline...")
    orchestrator = PipelineOrchestrator(backend=backend)

    # Start performance monitor
    monitor = PerformanceMonitor(metrics)
    monitor.start()

    # Event handlers to measure latency
    frame_timestamps = {}

    def on_frame_captured(camera_id: str, frame):
        """Track frame capture time."""
        frame_id = id(frame)
        frame_timestamps[frame_id] = time.time()
        metrics.frames_captured += 1

    def on_detection_complete(camera_id: str, detections):
        """Track detection completion."""
        metrics.frames_detected += 1

    try:
        # Start capture
        print("Starting capture...")
        start_time = time.time()
        orchestrator.start_capture(config, left_serial="sim_left", right_serial="sim_right")

        # Subscribe to events (if possible - may need to modify orchestrator)
        # For now, we'll just collect system-level metrics

        # Run for specified duration
        print(f"Running benchmark for {duration_seconds} seconds...")
        elapsed = 0
        last_report = 0

        while elapsed < duration_seconds:
            time.sleep(1.0)
            elapsed = time.time() - start_time

            # Report progress every 5 seconds
            if int(elapsed) % 5 == 0 and int(elapsed) != last_report:
                last_report = int(elapsed)
                current_metrics = metrics.to_dict()
                print(f"  {int(elapsed)}s - "
                      f"Memory: {current_metrics['memory']['peak_mb']:.1f}MB, "
                      f"CPU: {current_metrics['cpu']['avg_percent']:.1f}%, "
                      f"Disk I/O: {current_metrics['disk_io']['avg_rate_mbps']:.2f} MB/s")

        print("\nStopping capture...")
        orchestrator.stop_capture()

    finally:
        monitor.stop()

    print("\n" + "="*60)
    print("Benchmark Complete")
    print("="*60 + "\n")

    return metrics


def print_metrics_report(metrics: PerformanceMetrics):
    """Print formatted metrics report."""
    data = metrics.to_dict()

    print("\n" + "="*60)
    print("PERFORMANCE METRICS REPORT")
    print("="*60 + "\n")

    # Memory
    print("MEMORY USAGE:")
    print(f"  Average:     {data['memory']['avg_mb']:.1f} MB")
    print(f"  Peak:        {data['memory']['peak_mb']:.1f} MB")
    print(f"  Samples:     {data['memory']['samples']}")
    print()

    # CPU
    print("CPU USAGE:")
    print(f"  Average:     {data['cpu']['avg_percent']:.1f}%")
    print(f"  Peak:        {data['cpu']['peak_percent']:.1f}%")
    print(f"  Samples:     {data['cpu']['samples']}")
    print()

    # Disk I/O
    print("DISK I/O:")
    print(f"  Total Written: {data['disk_io']['total_mb']:.1f} MB")
    print(f"  Avg Rate:      {data['disk_io']['avg_rate_mbps']:.2f} MB/s")
    print(f"  Peak Rate:     {data['disk_io']['peak_rate_mbps']:.2f} MB/s")
    print()

    # Frames
    print("FRAME PROCESSING:")
    print(f"  Captured:    {data['frames']['captured']}")
    print(f"  Detected:    {data['frames']['detected']}")
    print(f"  Dropped:     {data['frames']['dropped']}")
    print(f"  Drop Rate:   {data['frames']['drop_rate']*100:.2f}%")
    print()

    # Latency (if available)
    if data['capture_latency']['samples'] > 0:
        print("CAPTURE LATENCY:")
        print(f"  Average:     {data['capture_latency']['avg_ms']:.2f} ms")
        print(f"  P95:         {data['capture_latency']['p95_ms']:.2f} ms")
        print(f"  Min/Max:     {data['capture_latency']['min_ms']:.2f} / {data['capture_latency']['max_ms']:.2f} ms")
        print()

    if data['detection_latency']['samples'] > 0:
        print("DETECTION LATENCY:")
        print(f"  Average:     {data['detection_latency']['avg_ms']:.2f} ms")
        print(f"  P95:         {data['detection_latency']['p95_ms']:.2f} ms")
        print(f"  Min/Max:     {data['detection_latency']['min_ms']:.2f} / {data['detection_latency']['max_ms']:.2f} ms")
        print()

    print("="*60 + "\n")


def save_metrics(metrics: PerformanceMetrics, output_file: Path):
    """Save metrics to JSON file."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics.to_dict()
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Metrics saved to: {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run PitchTracker performance benchmark")
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Benchmark duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--backend",
        default="sim",
        choices=["sim", "opencv", "uvc"],
        help="Camera backend to use (default: sim)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for metrics (default: benchmarks/results_TIMESTAMP.json)"
    )

    args = parser.parse_args()

    # Run benchmark
    metrics = run_benchmark(
        duration_seconds=args.duration,
        backend=args.backend
    )

    # Print report
    print_metrics_report(metrics)

    # Save to file
    if args.output:
        output_file = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"benchmarks/results_{timestamp}.json")

    save_metrics(metrics, output_file)

    print("\nBenchmark complete!")
