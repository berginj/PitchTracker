"""Bind stable PnP identities to actual DirectShow video-input indices.

DevicePath distinguishes identical models; PnP enumeration order does not.
See https://learn.microsoft.com/en-us/windows/win32/directshow/selecting-a-capture-device.
Enumeration reads moniker properties without opening a capture filter.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Sequence

from log_config.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DirectShowInput:
    index: int
    friendly_name: str
    device_path: str


def pnp_identity(device_path: str) -> str:
    """Extract an exact PnP instance identity from a Windows device interface path."""
    path = device_path.strip().casefold()
    if not path.startswith("\\\\?\\"):
        return ""
    components = path[4:].split("#")
    if len(components) < 4 or not components[3].startswith("{"):
        return ""
    return "\\".join(components[:3])


def enumerate_video_inputs() -> tuple[DirectShowInput, ...]:
    """Read the same video-input category/order used by OpenCV's DirectShow backend."""
    try:
        com = importlib.import_module("comtypes")
        property_bag_type = importlib.import_module("comtypes.persist").IPropertyBag
        graph_module = importlib.import_module("pygrabber.dshow_graph")
        categories = importlib.import_module("pygrabber.dshow_ids").DeviceCategories
    except ImportError as exc:
        raise RuntimeError("Stable UVC identity requires requirements-uvc-native.txt; install it and refresh devices.") from exc
    com.CoInitialize()
    native = stream = moniker = bag = None
    try:
        native = graph_module.SystemDeviceEnum()
        stream = native.system_device_enum.CreateClassEnumerator(com.GUID(categories.VideoInputDevice), dwFlags=0)
        entries = []
        index = 0
        while stream:
            moniker, count = stream.Next(1)
            if not count:
                break
            try:
                bag = moniker.BindToStorage(0, 0, property_bag_type._iid_).QueryInterface(property_bag_type)
                name = str(bag.Read("FriendlyName", pErrorLog=None))
                path = str(bag.Read("DevicePath", pErrorLog=None))
            except com.COMError:
                logger.warning("DirectShow input {} has no readable identity; it cannot bind a stable camera ID", index)
            else:
                entries.append(DirectShowInput(index, name, path))
            index += 1
        return tuple(entries)
    finally:
        # Release apartment-owned interfaces before balancing this thread's COM initialization.
        bag = moniker = stream = native = None
        com.CoUninitialize()


def resolve_directshow_index(instance_id: str, inputs: Sequence[DirectShowInput] | None = None) -> int:
    """Reject missing or ambiguous bindings instead of using a PnP list position."""
    if not instance_id.strip():
        raise ValueError("The selected camera has no stable PnP instance identity; refresh devices.")
    expected = instance_id.strip().casefold()
    matches = [entry.index for entry in (enumerate_video_inputs() if inputs is None else inputs)
               if pnp_identity(entry.device_path) == expected]
    if len(matches) != 1:
        raise ValueError("The selected camera does not have exactly one matching DirectShow device path; refresh devices.")
    return matches[0]
