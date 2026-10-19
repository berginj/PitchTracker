"""Stable camera assignment survives differing PnP/DirectShow order and equal names."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from capture.directshow_identity import DirectShowInput, enumerate_video_inputs, pnp_identity, resolve_directshow_index
from capture.uvc_backend import UvcCamera
from exceptions import CameraNotFoundError


def path(serial):
    return "\\\\?\\usb#vid_1234&pid_5678&mi_00#" + serial + "#{65E8773D-8F56-11D0-A3B9-00A0C9223196}\\global"


def test_equal_model_names_bind_by_exact_device_path_with_permuted_indices():
    inputs = (DirectShowInput(0, "Unrelated camera", path("other")),
              DirectShowInput(1, "Same model", path("right")),
              DirectShowInput(2, "Same model", path("left")))
    assert resolve_directshow_index(r"USB\VID_1234&PID_5678&MI_00\LEFT", inputs) == 2
    assert resolve_directshow_index(r"USB\VID_1234&PID_5678&MI_00\RIGHT", inputs) == 1


@pytest.mark.parametrize("inputs", [
    (),
    (DirectShowInput(0, "Same model", path("left")), DirectShowInput(1, "Same model", path("left"))),
])
def test_missing_or_duplicate_path_never_falls_back_to_model_name(inputs):
    with pytest.raises(ValueError, match="exactly one"):
        resolve_directshow_index(r"USB\VID_1234&PID_5678&MI_00\left", inputs)


@pytest.mark.parametrize("value", ["", "Logitech BRIO", r"USB\VID_1234\left", r"\\?\usb#incomplete"])
def test_unstructured_paths_do_not_create_hardware_identity(value):
    assert pnp_identity(value) == ""


def test_unbound_stable_id_rejects_capture_before_native_open():
    camera = UvcCamera()
    camera.set_discovered_devices([{"serial": "left", "friendly_name": "Same model", "instance_id": "absent"}])
    with patch("capture.uvc_backend.resolve_directshow_index", side_effect=ValueError("No matching device path")):
        with patch("capture.uvc_backend.cv2.VideoCapture") as capture:
            with pytest.raises(CameraNotFoundError, match="No matching device path"):
                camera.open("left")
    capture.assert_not_called()


def test_missing_native_dependency_gives_install_guidance():
    with patch("capture.directshow_identity.importlib.import_module", side_effect=ImportError("not installed")):
        with pytest.raises(RuntimeError, match="requirements-uvc-native"):
            enumerate_video_inputs()


def test_enumeration_failure_releases_com_and_never_returns_a_partial_binding():
    stream = Mock()
    stream.Next.side_effect = RuntimeError("Enumeration interrupted")
    native = Mock()
    native.system_device_enum.CreateClassEnumerator.return_value = stream
    com = SimpleNamespace(CoInitialize=Mock(), CoUninitialize=Mock(), GUID=str, COMError=RuntimeError)
    modules = {
        "comtypes": com,
        "comtypes.persist": SimpleNamespace(IPropertyBag=Mock()),
        "pygrabber.dshow_graph": SimpleNamespace(SystemDeviceEnum=lambda: native),
        "pygrabber.dshow_ids": SimpleNamespace(DeviceCategories=SimpleNamespace(VideoInputDevice="capture-category")),
    }
    with patch("capture.directshow_identity.importlib.import_module", side_effect=modules.__getitem__):
        with pytest.raises(RuntimeError, match="Enumeration interrupted"):
            enumerate_video_inputs()
    com.CoInitialize.assert_called_once()
    com.CoUninitialize.assert_called_once()
