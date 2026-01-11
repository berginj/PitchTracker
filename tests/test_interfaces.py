from calib.calibrator import Calibrator
from capture.camera_device import CameraDevice
from detect.detector import Detector
from metrics.compute import MetricsComputer
from record.recorder import Recorder
from rectify.rectifier import Rectifier
from stereo.association import StereoMatcher
from track.tracker import Tracker
from ui.render import Renderer


def test_interfaces_are_abstract() -> None:
    assert issubclass(CameraDevice, object)
    assert issubclass(Calibrator, object)
    assert issubclass(Detector, object)
    assert issubclass(StereoMatcher, object)
    assert issubclass(Tracker, object)
    assert issubclass(MetricsComputer, object)
    assert issubclass(Recorder, object)
    assert issubclass(Rectifier, object)
    assert issubclass(Renderer, object)
