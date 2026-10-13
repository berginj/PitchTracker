"""Analysis service module - Post-processing and pattern detection.

This module provides pitch trajectory fitting, session summary generation,
pattern detection, and strike zone calculation.
"""

from importlib import import_module
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .interface import AnalysisService
    from .implementation import AnalysisServiceImpl


def __getattr__(name: str) -> Any:
    module = {"AnalysisService": "interface", "AnalysisServiceImpl": "implementation"}.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


__all__ = ["AnalysisService", "AnalysisServiceImpl"]
