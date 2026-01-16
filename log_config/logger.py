"""Centralized logging configuration using loguru."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Remove default handler
logger.remove()

# Add console handler with INFO level
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)

# Add file handler with rotation
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

logger.add(
    logs_dir / "pitchtracker_{time}.log",
    rotation="50 MB",
    retention="10 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True,  # Thread-safe logging
)

# Add error-specific log file
logger.add(
    logs_dir / "errors_{time}.log",
    rotation="10 MB",
    retention="30 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    enqueue=True,
)


def get_logger(name: Optional[str] = None):
    """Get a logger instance with the given name.

    Args:
        name: Module name for the logger (usually __name__)

    Returns:
        Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


# Performance logging helper
def log_performance(operation: str, duration_ms: float, threshold_ms: float = 100.0) -> None:
    """Log performance metrics with warnings for slow operations.

    Args:
        operation: Description of the operation
        duration_ms: Duration in milliseconds
        threshold_ms: Threshold for warning (default: 100ms)
    """
    if duration_ms > threshold_ms:
        logger.warning(f"Slow operation: {operation} took {duration_ms:.2f}ms (threshold: {threshold_ms}ms)")
    else:
        logger.debug(f"Performance: {operation} took {duration_ms:.2f}ms")


# Export configured logger
__all__ = ["logger", "get_logger", "log_performance"]
