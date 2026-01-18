"""Resource monitoring for tracking system resources and performance."""

from __future__ import annotations

import gc
import logging
import psutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.events import ErrorCategory, ErrorSeverity, publish_error

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """Snapshot of resource usage metrics."""

    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_free_gb: float = 0.0
    thread_count: int = 0
    open_files: int = 0
    frame_drops: int = 0


class ResourceMonitor:
    """Monitor system resources and performance."""

    def __init__(self, check_interval: float = 5.0):
        """Initialize resource monitor.

        Args:
            check_interval: Interval between checks in seconds
        """
        self._check_interval = check_interval
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Thresholds
        self._memory_warning_mb = 2000  # 2GB
        self._memory_critical_mb = 4000  # 4GB
        self._cpu_warning_percent = 80.0
        self._cpu_critical_percent = 95.0

        # Metrics history
        self._metrics_history: List[ResourceMetrics] = []
        self._max_history = 100

        # Process handle
        self._process = psutil.Process()

        # Tracking
        self._last_warning_time: Dict[str, float] = {}

    def start(self) -> None:
        """Start resource monitoring."""
        if self._monitoring:
            logger.warning("Resource monitor already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ResourceMonitor",
            daemon=False
        )
        self._monitor_thread.start()
        logger.info("Resource monitor started")

    def stop(self) -> None:
        """Stop resource monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        logger.info("Resource monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                metrics = self._collect_metrics()
                self._metrics_history.append(metrics)

                # Trim history
                if len(self._metrics_history) > self._max_history:
                    self._metrics_history.pop(0)

                # Check thresholds
                self._check_thresholds(metrics)

                # Force garbage collection periodically
                if len(self._metrics_history) % 10 == 0:
                    collected = gc.collect()
                    logger.debug(f"Garbage collected {collected} objects")

            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}", exc_info=True)

            time.sleep(self._check_interval)

    def _collect_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics.

        Returns:
            Current resource metrics
        """
        metrics = ResourceMetrics()

        try:
            # CPU usage
            metrics.cpu_percent = self._process.cpu_percent()

            # Memory usage
            mem_info = self._process.memory_info()
            metrics.memory_mb = mem_info.rss / (1024 * 1024)
            metrics.memory_percent = self._process.memory_percent()

            # Thread count
            metrics.thread_count = threading.active_count()

            # Open file handles
            try:
                metrics.open_files = len(self._process.open_files())
            except (PermissionError, psutil.AccessDenied):
                metrics.open_files = -1

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        return metrics

    def _check_thresholds(self, metrics: ResourceMetrics) -> None:
        """Check if any thresholds are exceeded.

        Args:
            metrics: Current metrics
        """
        current_time = time.time()

        # Memory checks
        if metrics.memory_mb > self._memory_critical_mb:
            if self._should_warn("memory_critical", current_time, 60.0):
                publish_error(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Critical memory usage: {metrics.memory_mb:.0f}MB ({metrics.memory_percent:.1f}%)",
                    source="ResourceMonitor",
                    memory_mb=metrics.memory_mb,
                    memory_percent=metrics.memory_percent,
                )
        elif metrics.memory_mb > self._memory_warning_mb:
            if self._should_warn("memory_warning", current_time, 120.0):
                publish_error(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.WARNING,
                    message=f"High memory usage: {metrics.memory_mb:.0f}MB ({metrics.memory_percent:.1f}%)",
                    source="ResourceMonitor",
                    memory_mb=metrics.memory_mb,
                    memory_percent=metrics.memory_percent,
                )

        # CPU checks
        if metrics.cpu_percent > self._cpu_critical_percent:
            if self._should_warn("cpu_critical", current_time, 60.0):
                publish_error(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.CRITICAL,
                    message=f"Critical CPU usage: {metrics.cpu_percent:.1f}%",
                    source="ResourceMonitor",
                    cpu_percent=metrics.cpu_percent,
                )
        elif metrics.cpu_percent > self._cpu_warning_percent:
            if self._should_warn("cpu_warning", current_time, 120.0):
                publish_error(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.WARNING,
                    message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                    source="ResourceMonitor",
                    cpu_percent=metrics.cpu_percent,
                )

    def _should_warn(self, key: str, current_time: float, interval: float) -> bool:
        """Check if warning should be issued (throttling).

        Args:
            key: Warning key
            current_time: Current time
            interval: Minimum interval between warnings

        Returns:
            True if warning should be issued
        """
        last_time = self._last_warning_time.get(key, 0.0)
        if current_time - last_time > interval:
            self._last_warning_time[key] = current_time
            return True
        return False

    def get_current_metrics(self) -> ResourceMetrics:
        """Get current resource metrics.

        Returns:
            Current metrics
        """
        return self._collect_metrics()

    def get_metrics_history(self) -> List[ResourceMetrics]:
        """Get metrics history.

        Returns:
            List of historical metrics
        """
        return self._metrics_history.copy()


# Global resource monitor instance
_resource_monitor: Optional[ResourceMonitor] = None
_monitor_lock = threading.Lock()


def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor instance.

    Returns:
        Global resource monitor
    """
    global _resource_monitor
    if _resource_monitor is None:
        with _monitor_lock:
            if _resource_monitor is None:
                _resource_monitor = ResourceMonitor()
                logger.debug("Created global resource monitor")
    return _resource_monitor


__all__ = [
    "ResourceMetrics",
    "ResourceMonitor",
    "get_resource_monitor",
]
