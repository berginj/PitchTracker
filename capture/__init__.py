"""Capture module."""

from .camera_device import CameraDevice, CameraStats
from .opencv_backend import OpenCVCamera
from .simulated_camera import SimulatedCamera

__all__ = ["CameraDevice", "CameraStats", "OpenCVCamera", "SimulatedCamera"]
