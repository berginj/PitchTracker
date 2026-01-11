"""Detection package implementing MODE_A and MODE_B pipelines."""

from detect.config import DetectorConfig, FilterConfig, Mode
from detect.detector import Detector

__all__ = ["Detector", "DetectorConfig", "FilterConfig", "Mode"]
