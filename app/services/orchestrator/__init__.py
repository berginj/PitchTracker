"""Pipeline orchestrator module - Coordinates all services via EventBus.

This module provides the main pipeline orchestration that wires together
capture, detection, recording, and analysis services.
"""

from .pipeline_orchestrator import PipelineOrchestrator

__all__ = ["PipelineOrchestrator"]
