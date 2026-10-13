"""Guided rig setup; importing its contracts does not load Qt widgets."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .stereo_setup_window import StereoSetupWindow


def __getattr__(name: str) -> Any:
    if name != "StereoSetupWindow":
        raise AttributeError(name)
    from .stereo_setup_window import StereoSetupWindow
    return StereoSetupWindow


__all__ = ["StereoSetupWindow"]
