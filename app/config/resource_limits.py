"""Resource limit configuration for system resource management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Configuration for system resource limits."""

    # Memory limits (MB)
    max_memory_mb: float = 4096.0  # 4GB
    warning_memory_mb: float = 2048.0  # 2GB

    # CPU limits (%)
    max_cpu_percent: float = 95.0
    warning_cpu_percent: float = 80.0

    # Disk space limits (GB)
    critical_disk_gb: float = 5.0
    warning_disk_gb: float = 20.0
    recommended_disk_gb: float = 50.0

    # Queue limits
    max_queue_size: int = 10
    detection_queue_size: int = 6
    recording_queue_size: int = 20

    # Thread limits
    max_threads: int = 50
    warning_threads: int = 30

    # File handle limits
    max_open_files: int = 100
    warning_open_files: int = 50

    # Frame rate limits
    max_fps: int = 120
    recommended_fps: int = 60

    # Session limits
    max_session_duration_hours: float = 8.0
    max_session_size_gb: float = 100.0

    # Timeouts (seconds)
    camera_open_timeout: float = 10.0
    camera_read_timeout: float = 2.0
    detection_timeout: float = 5.0
    cleanup_timeout: float = 10.0
    shutdown_timeout: float = 30.0

    def validate(self) -> list[str]:
        """Validate resource limits configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Memory checks
        if self.max_memory_mb <= 0:
            errors.append("max_memory_mb must be positive")
        if self.warning_memory_mb <= 0:
            errors.append("warning_memory_mb must be positive")
        if self.warning_memory_mb >= self.max_memory_mb:
            errors.append("warning_memory_mb must be less than max_memory_mb")

        # CPU checks
        if self.max_cpu_percent <= 0 or self.max_cpu_percent > 100:
            errors.append("max_cpu_percent must be between 0 and 100")
        if self.warning_cpu_percent <= 0 or self.warning_cpu_percent > 100:
            errors.append("warning_cpu_percent must be between 0 and 100")
        if self.warning_cpu_percent >= self.max_cpu_percent:
            errors.append("warning_cpu_percent must be less than max_cpu_percent")

        # Disk checks
        if self.critical_disk_gb <= 0:
            errors.append("critical_disk_gb must be positive")
        if self.warning_disk_gb <= 0:
            errors.append("warning_disk_gb must be positive")
        if self.critical_disk_gb >= self.warning_disk_gb:
            errors.append("critical_disk_gb must be less than warning_disk_gb")
        if self.warning_disk_gb >= self.recommended_disk_gb:
            errors.append("warning_disk_gb must be less than recommended_disk_gb")

        # Queue checks
        if self.max_queue_size <= 0:
            errors.append("max_queue_size must be positive")
        if self.detection_queue_size <= 0:
            errors.append("detection_queue_size must be positive")
        if self.recording_queue_size <= 0:
            errors.append("recording_queue_size must be positive")

        # Thread checks
        if self.max_threads <= 0:
            errors.append("max_threads must be positive")
        if self.warning_threads <= 0:
            errors.append("warning_threads must be positive")
        if self.warning_threads >= self.max_threads:
            errors.append("warning_threads must be less than max_threads")

        # File handle checks
        if self.max_open_files <= 0:
            errors.append("max_open_files must be positive")
        if self.warning_open_files <= 0:
            errors.append("warning_open_files must be positive")
        if self.warning_open_files >= self.max_open_files:
            errors.append("warning_open_files must be less than max_open_files")

        # FPS checks
        if self.max_fps <= 0:
            errors.append("max_fps must be positive")
        if self.recommended_fps <= 0:
            errors.append("recommended_fps must be positive")
        if self.recommended_fps > self.max_fps:
            errors.append("recommended_fps must be less than or equal to max_fps")

        # Session checks
        if self.max_session_duration_hours <= 0:
            errors.append("max_session_duration_hours must be positive")
        if self.max_session_size_gb <= 0:
            errors.append("max_session_size_gb must be positive")

        # Timeout checks
        if self.camera_open_timeout <= 0:
            errors.append("camera_open_timeout must be positive")
        if self.camera_read_timeout <= 0:
            errors.append("camera_read_timeout must be positive")
        if self.detection_timeout <= 0:
            errors.append("detection_timeout must be positive")
        if self.cleanup_timeout <= 0:
            errors.append("cleanup_timeout must be positive")
        if self.shutdown_timeout <= 0:
            errors.append("shutdown_timeout must be positive")

        if errors:
            logger.error(f"Resource limits validation failed: {len(errors)} errors")
            for error in errors:
                logger.error(f"  - {error}")

        return errors

    def is_memory_critical(self, memory_mb: float) -> bool:
        """Check if memory usage is critical.

        Args:
            memory_mb: Current memory usage in MB

        Returns:
            True if critical
        """
        return memory_mb >= self.max_memory_mb

    def is_memory_warning(self, memory_mb: float) -> bool:
        """Check if memory usage is at warning level.

        Args:
            memory_mb: Current memory usage in MB

        Returns:
            True if at warning level
        """
        return memory_mb >= self.warning_memory_mb

    def is_cpu_critical(self, cpu_percent: float) -> bool:
        """Check if CPU usage is critical.

        Args:
            cpu_percent: Current CPU usage percentage

        Returns:
            True if critical
        """
        return cpu_percent >= self.max_cpu_percent

    def is_cpu_warning(self, cpu_percent: float) -> bool:
        """Check if CPU usage is at warning level.

        Args:
            cpu_percent: Current CPU usage percentage

        Returns:
            True if at warning level
        """
        return cpu_percent >= self.warning_cpu_percent

    def is_disk_critical(self, free_gb: float) -> bool:
        """Check if disk space is critical.

        Args:
            free_gb: Free disk space in GB

        Returns:
            True if critical
        """
        return free_gb < self.critical_disk_gb

    def is_disk_warning(self, free_gb: float) -> bool:
        """Check if disk space is at warning level.

        Args:
            free_gb: Free disk space in GB

        Returns:
            True if at warning level
        """
        return free_gb < self.warning_disk_gb


# Global resource limits instance
_resource_limits: Optional[ResourceLimits] = None


def get_resource_limits() -> ResourceLimits:
    """Get global resource limits instance.

    Returns:
        Global resource limits
    """
    global _resource_limits
    if _resource_limits is None:
        _resource_limits = ResourceLimits()
        logger.debug("Created global resource limits with default values")

        # Validate on creation
        errors = _resource_limits.validate()
        if errors:
            logger.warning("Default resource limits have validation errors (using anyway)")

    return _resource_limits


def set_resource_limits(limits: ResourceLimits) -> None:
    """Set global resource limits.

    Args:
        limits: Resource limits configuration
    """
    global _resource_limits

    # Validate before setting
    errors = limits.validate()
    if errors:
        raise ValueError(f"Invalid resource limits: {errors}")

    _resource_limits = limits
    logger.info("Updated global resource limits")


__all__ = [
    "ResourceLimits",
    "get_resource_limits",
    "set_resource_limits",
]
