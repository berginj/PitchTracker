"""Capture module."""

from .camera_device import CameraDevice, CameraStats
from .simulated_camera import SimulatedCamera

__all__ = ["CameraDevice", "CameraStats", "SimulatedCamera"]
