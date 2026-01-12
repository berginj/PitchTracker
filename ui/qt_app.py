"""PySide6 UI for preview and recording via the pipeline service."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import cv2
import yaml
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.pipeline_service import InProcessPipelineService
from calib.quick_calibrate import calibrate_and_write
from capture.uvc_backend import list_uvc_devices
from configs.lane_io import save_lane_rois
from configs.roi_io import load_rois, save_rois
from configs.settings import load_config
from detect.lane import LaneRoi
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pitch Tracker Qt UI.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--backend", default="uvc", choices=("uvc", "opencv", "sim"))
    return parser.parse_args()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, backend: str, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("Pitch Tracker")
        self._config = load_config(config_path)
        self._service = InProcessPipelineService(backend=backend)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_preview)
        self._roi_path = Path("configs/roi.json")
        self._lane_path = Path("configs/lane_roi.json")
        self._lane_rect: Optional[Rect] = None
        self._plate_rect: Optional[Rect] = None
        self._active_rect: Optional[Rect] = None
        self._roi_mode: Optional[str] = None

        self._left_input = QtWidgets.QComboBox()
        self._right_input = QtWidgets.QComboBox()
        self._left_input.setEditable(True)
        self._right_input.setEditable(True)
        self._left_input.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self._right_input.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self._start_button = QtWidgets.QPushButton("Start Capture")
        self._stop_button = QtWidgets.QPushButton("Stop Capture")
        self._restart_button = QtWidgets.QPushButton("Restart Capture")
        self._record_button = QtWidgets.QPushButton("Start Recording")
        self._stop_record_button = QtWidgets.QPushButton("Stop Recording")
        self._refresh_button = QtWidgets.QPushButton("Refresh Devices")
        self._status_label = QtWidgets.QLabel("Idle")
        self._ball_combo = QtWidgets.QComboBox()
        self._ball_combo.addItems(["baseball", "softball"])
        self._batter_height = QtWidgets.QDoubleSpinBox()
        self._batter_height.setMinimum(40.0)
        self._batter_height.setMaximum(96.0)
        self._batter_height.setSuffix(" in")
        self._top_ratio = QtWidgets.QDoubleSpinBox()
        self._bottom_ratio = QtWidgets.QDoubleSpinBox()
        for ratio in (self._top_ratio, self._bottom_ratio):
            ratio.setMinimum(0.0)
            ratio.setMaximum(1.0)
            ratio.setSingleStep(0.01)
        self._save_strike_button = QtWidgets.QPushButton("Save Strike Zone")

        self._left_view = RoiLabel(self._on_rect_update)
        self._right_view = QtWidgets.QLabel()
        self._left_view.setMinimumSize(320, 180)
        self._right_view.setMinimumSize(320, 180)
        self._left_view.setAlignment(QtCore.Qt.AlignCenter)
        self._right_view.setAlignment(QtCore.Qt.AlignCenter)
        self._left_view.setScaledContents(True)
        self._right_view.setScaledContents(True)

        self._lane_button = QtWidgets.QPushButton("Edit Lane ROI")
        self._plate_button = QtWidgets.QPushButton("Edit Plate ROI")
        self._clear_lane_button = QtWidgets.QPushButton("Clear Lane ROI")
        self._clear_plate_button = QtWidgets.QPushButton("Clear Plate ROI")
        self._save_roi_button = QtWidgets.QPushButton("Save ROIs")
        self._load_roi_button = QtWidgets.QPushButton("Load ROIs")
        self._guide_button = QtWidgets.QPushButton("Calibration Guide")
        self._quick_cal_button = QtWidgets.QPushButton("Quick Calibrate")

        self._mode_combo = QtWidgets.QComboBox()
        self._mode_combo.addItems([Mode.MODE_A.value, Mode.MODE_B.value])
        self._frame_diff = QtWidgets.QDoubleSpinBox()
        self._bg_diff = QtWidgets.QDoubleSpinBox()
        self._bg_alpha = QtWidgets.QDoubleSpinBox()
        self._edge_thresh = QtWidgets.QDoubleSpinBox()
        self._blob_thresh = QtWidgets.QDoubleSpinBox()
        self._min_area = QtWidgets.QSpinBox()
        self._min_circ = QtWidgets.QDoubleSpinBox()
        self._apply_detector = QtWidgets.QPushButton("Apply Detector")

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self._left_input)
        controls.addWidget(self._right_input)
        controls.addWidget(self._refresh_button)
        controls.addWidget(self._start_button)
        controls.addWidget(self._stop_button)
        controls.addWidget(self._restart_button)
        controls.addWidget(self._record_button)
        controls.addWidget(self._stop_record_button)
        controls.addWidget(QtWidgets.QLabel("Ball"))
        controls.addWidget(self._ball_combo)
        controls.addWidget(QtWidgets.QLabel("Batter Height"))
        controls.addWidget(self._batter_height)
        controls.addWidget(QtWidgets.QLabel("Top %"))
        controls.addWidget(self._top_ratio)
        controls.addWidget(QtWidgets.QLabel("Bottom %"))
        controls.addWidget(self._bottom_ratio)
        controls.addWidget(self._save_strike_button)

        views = QtWidgets.QHBoxLayout()
        views.addWidget(self._left_view, 1)
        views.addWidget(self._right_view, 1)

        roi_controls = QtWidgets.QHBoxLayout()
        roi_controls.addWidget(self._lane_button)
        roi_controls.addWidget(self._plate_button)
        roi_controls.addWidget(self._clear_lane_button)
        roi_controls.addWidget(self._clear_plate_button)
        roi_controls.addWidget(self._save_roi_button)
        roi_controls.addWidget(self._load_roi_button)
        roi_controls.addWidget(self._guide_button)
        roi_controls.addWidget(self._quick_cal_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(controls)
        layout.addLayout(views)
        layout.addLayout(roi_controls)
        layout.addWidget(self._build_detector_panel())
        layout.addWidget(self._status_label)

        container = QtWidgets.QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._start_button.clicked.connect(self._start_capture)
        self._stop_button.clicked.connect(self._stop_capture)
        self._restart_button.clicked.connect(self._restart_capture)
        self._record_button.clicked.connect(self._start_recording)
        self._stop_record_button.clicked.connect(self._stop_recording)
        self._refresh_button.clicked.connect(self._refresh_devices)
        self._ball_combo.currentTextChanged.connect(self._set_ball_type)
        self._batter_height.valueChanged.connect(self._set_batter_height)
        self._top_ratio.valueChanged.connect(self._set_strike_ratios)
        self._bottom_ratio.valueChanged.connect(self._set_strike_ratios)
        self._save_strike_button.clicked.connect(self._save_strike_zone)
        self._lane_button.clicked.connect(lambda: self._set_roi_mode("lane"))
        self._plate_button.clicked.connect(lambda: self._set_roi_mode("plate"))
        self._clear_lane_button.clicked.connect(self._clear_lane)
        self._clear_plate_button.clicked.connect(self._clear_plate)
        self._save_roi_button.clicked.connect(self._save_rois)
        self._load_roi_button.clicked.connect(self._load_rois)
        self._guide_button.clicked.connect(self._open_calibration_guide)
        self._apply_detector.clicked.connect(self._apply_detector_config)
        self._quick_cal_button.clicked.connect(self._open_quick_calibrate)

        self._refresh_devices()
        self._load_rois()
        self._maybe_show_guide()
        self._load_detector_defaults()
        self._ball_combo.setCurrentText(self._config.ball.type)
        self._batter_height.setValue(self._config.strike_zone.batter_height_in)
        self._top_ratio.setValue(self._config.strike_zone.top_ratio)
        self._bottom_ratio.setValue(self._config.strike_zone.bottom_ratio)

    def _start_capture(self) -> None:
        left = _current_serial(self._left_input)
        right = _current_serial(self._right_input)
        if not left or not right:
            self._status_label.setText("Enter both serials.")
            return
        self._service.start_capture(self._config, left, right)
        self._status_label.setText("Capturing.")
        self._timer.start(int(1000 / max(self._config.ui.refresh_hz, 1)))

    def _stop_capture(self) -> None:
        self._timer.stop()
        self._service.stop_capture()
        self._status_label.setText("Stopped.")

    def _restart_capture(self) -> None:
        self._stop_capture()
        self._start_capture()

    def _start_recording(self) -> None:
        self._service.start_recording()
        self._status_label.setText("Recording...")

    def _stop_recording(self) -> None:
        bundle = self._service.stop_recording()
        self._status_label.setText(f"Recorded frames: {len(list(bundle.frames))}")

    def _update_preview(self) -> None:
        try:
            left_frame, right_frame = self._service.get_preview_frames()
        except RuntimeError as exc:
            self._status_label.setText(str(exc))
            return
        self._left_view.set_image_size(left_frame.width, left_frame.height)
        overlays = _roi_overlays(self._lane_rect, self._plate_rect, self._active_rect)
        detections = self._service.get_latest_detections()
        gated = self._service.get_latest_gated_detections()
        left_dets = detections.get(left_frame.camera_id, [])
        right_dets = detections.get(right_frame.camera_id, [])
        left_gated = gated.get(left_frame.camera_id, {})
        right_gated = gated.get(right_frame.camera_id, {})
        zone = None
        if strike.zone_row is not None and strike.zone_col is not None:
            zone = (strike.zone_row, strike.zone_col)
        self._left_view.setPixmap(
            _frame_to_pixmap(
                left_frame.image,
                overlays,
                left_dets,
                left_gated.get("lane", []),
                left_gated.get("plate", []),
                plate_rect=self._plate_rect,
                zone=zone,
            )
        )
        self._right_view.setPixmap(
            _frame_to_pixmap(
                right_frame.image,
                overlays,
                right_dets,
                right_gated.get("lane", []),
                right_gated.get("plate", []),
                plate_rect=self._plate_rect,
                zone=zone,
            )
        )
        stats = self._service.get_stats()
        plate_metrics = self._service.get_plate_metrics()
        strike = self._service.get_strike_result()
        if stats:
            left_stats = stats.get("left", {})
            right_stats = stats.get("right", {})
            zone_label = "-"
            if strike.zone_row is not None and strike.zone_col is not None:
                zone_label = f"{strike.zone_row},{strike.zone_col}"
            self._status_label.setText(
                "fps L={:.1f} R={:.1f} drops L={} R={} run={:.2f} rise={:.2f} strike={} zone={}".format(
                    left_stats.get("fps_avg", 0.0),
                    right_stats.get("fps_avg", 0.0),
                    int(left_stats.get("dropped_frames", 0)),
                    int(right_stats.get("dropped_frames", 0)),
                    plate_metrics.run_in,
                    plate_metrics.rise_in,
                    "Y" if strike.is_strike else "N",
                    zone_label,
                )
            )

    def _refresh_devices(self) -> None:
        self._left_input.clear()
        self._right_input.clear()
        if self._service._backend == "uvc":
            devices = _probe_uvc_devices()
            for device in devices:
                label = f"{device['serial']} - {device['friendly_name']}"
                self._left_input.addItem(label, device["serial"])
                self._right_input.addItem(label, device["serial"])
            if devices:
                self._status_label.setText(f"Found {len(devices)} usable device(s).")
                if len(devices) >= 2:
                    self._left_input.setCurrentIndex(0)
                    self._right_input.setCurrentIndex(1)
            else:
                self._status_label.setText("No UVC devices found.")
            return
        indices = _probe_opencv_indices()
        for index in indices:
            label = f"Index {index}"
            self._left_input.addItem(label, str(index))
            self._right_input.addItem(label, str(index))
        if indices:
            self._status_label.setText(f"Found {len(indices)} camera index(es).")
            if len(indices) >= 2:
                self._left_input.setCurrentIndex(0)
                self._right_input.setCurrentIndex(1)
        else:
            self._status_label.setText("No OpenCV camera indices available.")

    def _set_roi_mode(self, mode: str) -> None:
        self._roi_mode = mode
        self._left_view.set_mode(mode)
        self._status_label.setText(f"ROI mode: {mode} (drag rectangle on left view)")

    def _on_rect_update(self, rect: Rect, final: bool) -> None:
        rect = _normalize_rect(rect, self._left_view.image_size())
        if rect is None:
            return
        if final:
            if self._roi_mode == "lane":
                self._lane_rect = rect
            elif self._roi_mode == "plate":
                self._plate_rect = rect
            self._active_rect = None
        else:
            self._active_rect = rect

    def _clear_lane(self) -> None:
        self._lane_rect = None
        self._status_label.setText("Lane ROI cleared.")

    def _clear_plate(self) -> None:
        self._plate_rect = None
        self._status_label.setText("Plate ROI cleared.")

    def _save_rois(self) -> None:
        lane_poly = _rect_to_polygon(self._lane_rect)
        plate_poly = _rect_to_polygon(self._plate_rect)
        save_rois(self._roi_path, lane_poly, plate_poly)
        if lane_poly is not None:
            lane_rois = {
                "left": LaneRoi(polygon=lane_poly),
                "right": LaneRoi(polygon=lane_poly),
            }
            save_lane_rois(self._lane_path, lane_rois)
        self._status_label.setText("ROIs saved.")

    def _load_rois(self) -> None:
        rois = load_rois(self._roi_path)
        self._lane_rect = _polygon_to_rect(rois.get("lane"))
        self._plate_rect = _polygon_to_rect(rois.get("plate"))
        if self._lane_rect or self._plate_rect:
            self._status_label.setText("ROIs loaded.")

    def _load_detector_defaults(self) -> None:
        cfg = self._config.detector
        self._mode_combo.setCurrentText(cfg.mode)
        self._frame_diff.setValue(cfg.frame_diff_threshold)
        self._bg_diff.setValue(cfg.bg_diff_threshold)
        self._bg_alpha.setValue(cfg.bg_alpha)
        self._edge_thresh.setValue(cfg.edge_threshold)
        self._blob_thresh.setValue(cfg.blob_threshold)
        self._min_area.setValue(cfg.filters.min_area)
        self._min_circ.setValue(cfg.filters.min_circularity)

    def _apply_detector_config(self) -> None:
        cfg = self._config.detector
        filter_cfg = FilterConfig(
            min_area=self._min_area.value(),
            max_area=cfg.filters.max_area,
            min_circularity=self._min_circ.value(),
            max_circularity=cfg.filters.max_circularity,
            min_velocity=cfg.filters.min_velocity,
            max_velocity=cfg.filters.max_velocity,
        )
        detector_cfg = CvDetectorConfig(
            frame_diff_threshold=self._frame_diff.value(),
            bg_diff_threshold=self._bg_diff.value(),
            bg_alpha=self._bg_alpha.value(),
            edge_threshold=self._edge_thresh.value(),
            blob_threshold=self._blob_thresh.value(),
            runtime_budget_ms=cfg.runtime_budget_ms,
            filters=filter_cfg,
        )
        mode = Mode(self._mode_combo.currentText())
        self._service.set_detector_config(detector_cfg, mode)
        self._status_label.setText("Detector settings applied.")

    def _set_ball_type(self, ball_type: str) -> None:
        self._service.set_ball_type(ball_type)

    def _set_batter_height(self, value: float) -> None:
        self._service.set_batter_height_in(value)

    def _set_strike_ratios(self) -> None:
        self._service.set_strike_zone_ratios(
            self._top_ratio.value(),
            self._bottom_ratio.value(),
        )

    def _save_strike_zone(self) -> None:
        config_path = self._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("strike_zone", {})
        data["strike_zone"]["batter_height_in"] = float(self._batter_height.value())
        data["strike_zone"]["top_ratio"] = float(self._top_ratio.value())
        data["strike_zone"]["bottom_ratio"] = float(self._bottom_ratio.value())
        data.setdefault("ball", {})
        data["ball"]["type"] = self._ball_combo.currentText()
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self._status_label.setText("Strike zone saved.")

    def _build_detector_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Detector (Quick)")
        form = QtWidgets.QFormLayout()
        for field in (
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_circ,
        ):
            field.setDecimals(2)
            field.setMaximum(10_000.0)
        self._bg_alpha.setMaximum(1.0)
        self._bg_alpha.setSingleStep(0.01)
        self._min_area.setMaximum(100_000)
        form.addRow("Mode", self._mode_combo)
        form.addRow("Frame diff", self._frame_diff)
        form.addRow("BG diff", self._bg_diff)
        form.addRow("BG alpha", self._bg_alpha)
        form.addRow("Edge thresh", self._edge_thresh)
        form.addRow("Blob thresh", self._blob_thresh)
        form.addRow("Min area", self._min_area)
        form.addRow("Min circularity", self._min_circ)
        form.addRow(self._apply_detector)
        panel.setLayout(form)
        return panel

    def _open_calibration_guide(self) -> None:
        dialog = CalibrationGuide(self)
        dialog.exec()

    def _open_quick_calibrate(self) -> None:
        dialog = QuickCalibrateDialog(self, self._config_path())
        dialog.exec()
        if dialog.updated:
            self._config = load_config(self._config_path())
            if dialog.updates:
                baseline = dialog.updates.get("baseline_ft")
                focal = dialog.updates.get("focal_length_px")
                if isinstance(baseline, (int, float)) and isinstance(focal, (int, float)):
                    self._status_label.setText(
                        f"Calibration updated (baseline_ft={baseline:.3f}, f_px={focal:.1f}). Restart capture."
                    )
                else:
                    self._status_label.setText("Calibration updated. Restart capture to apply.")
            else:
                self._status_label.setText("Calibration updated. Restart capture to apply.")

    def _maybe_show_guide(self) -> None:
        marker = Path("configs/.first_run_done")
        if marker.exists():
            return
        QtCore.QTimer.singleShot(300, self._open_calibration_guide)
        try:
            marker.write_text("ok")
        except OSError:
            pass

    def _config_path(self) -> Path:
        return Path("configs/default.yaml")


def _frame_to_pixmap(
    image: np.ndarray,
    overlays: list[Overlay] | None = None,
    detections: list | None = None,
    lane_detections: list | None = None,
    plate_detections: list | None = None,
    plate_rect: Optional[Rect] = None,
    zone: tuple[int, int] | None = None,
) -> QtGui.QPixmap:
    if image.ndim == 2:
        height, width = image.shape
        qimage = QtGui.QImage(
            image.data,
            width,
            height,
            image.strides[0],
            QtGui.QImage.Format_Grayscale8,
        )
    else:
        height, width, _ = image.shape
        rgb = image[..., ::-1].copy()
        qimage = QtGui.QImage(
            rgb.data,
            width,
            height,
            rgb.strides[0],
            QtGui.QImage.Format_RGB888,
        )
    pixmap = QtGui.QPixmap.fromImage(qimage)
    if overlays or detections or lane_detections or plate_detections or plate_rect or zone:
        painter = QtGui.QPainter(pixmap)
        if overlays:
            for rect, color in overlays:
                painter.setPen(QtGui.QPen(color, 2))
                painter.drawRect(*rect)
        _draw_detections(painter, detections, QtGui.QColor(255, 0, 0))
        _draw_detections(painter, lane_detections, QtGui.QColor(0, 200, 255))
        _draw_detections(painter, plate_detections, QtGui.QColor(255, 180, 0))
        if plate_rect:
            _draw_plate_grid(painter, plate_rect, QtGui.QColor(255, 180, 0), zone)
        painter.end()
    return pixmap


def _current_serial(combo: QtWidgets.QComboBox) -> str:
    data = combo.currentData()
    if isinstance(data, str) and data.strip():
        return data.strip()
    return combo.currentText().strip()


def _probe_opencv_indices(max_index: int = 8) -> list[int]:
    indices: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            indices.append(i)
    return indices


def _probe_uvc_devices() -> list[dict[str, str]]:
    devices = list_uvc_devices()
    usable: list[dict[str, str]] = []
    for device in devices:
        name = device.get("friendly_name", "")
        if not name:
            continue
        cap = cv2.VideoCapture(f"video={name}", cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            usable.append(device)
    return usable


class RoiLabel(QtWidgets.QLabel):
    def __init__(self, on_rect_update) -> None:
        super().__init__()
        self._on_rect_update = on_rect_update
        self._mode: Optional[str] = None
        self._start: Optional[QtCore.QPoint] = None
        self._image_size: Optional[tuple[int, int]] = None

    def set_mode(self, mode: Optional[str]) -> None:
        self._mode = mode

    def set_image_size(self, width: int, height: int) -> None:
        self._image_size = (width, height)

    def image_size(self) -> Optional[tuple[int, int]]:
        return self._image_size

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._mode is None or self._image_size is None:
            return
        if event.button() == QtCore.Qt.LeftButton:
            self._start = event.position().toPoint()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._start is None or self._image_size is None:
            return
        current = event.position().toPoint()
        start = self._map_point(self._start)
        end = self._map_point(current)
        rect = _points_to_rect(start, end)
        if rect:
            self._on_rect_update(rect, False)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._start is None or self._image_size is None:
            return
        if event.button() == QtCore.Qt.LeftButton:
            end = event.position().toPoint()
            start = self._map_point(self._start)
            end = self._map_point(end)
            rect = _points_to_rect(start, end)
            if rect:
                self._on_rect_update(rect, True)
        self._start = None

    def _map_point(self, point: QtCore.QPoint) -> QtCore.QPoint:
        if self._image_size is None:
            return point
        label_w = max(self.width(), 1)
        label_h = max(self.height(), 1)
        img_w, img_h = self._image_size
        x = int(point.x() * img_w / label_w)
        y = int(point.y() * img_h / label_h)
        return QtCore.QPoint(x, y)


Rect = tuple[int, int, int, int]
Overlay = tuple[Rect, QtGui.QColor]


def _points_to_rect(start: QtCore.QPoint, end: QtCore.QPoint) -> Optional[Rect]:
    x1 = start.x()
    y1 = start.y()
    x2 = end.x()
    y2 = end.y()
    if x1 == x2 or y1 == y2:
        return None
    return (x1, y1, x2, y2)


def _normalize_rect(rect: Rect, image_size: Optional[tuple[int, int]]) -> Optional[Rect]:
    if image_size is None:
        return None
    width, height = image_size
    x1, y1, x2, y2 = rect
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1 = max(0, min(x1, width - 1))
    x2 = max(0, min(x2, width - 1))
    y1 = max(0, min(y1, height - 1))
    y2 = max(0, min(y2, height - 1))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return None
    return (x1, y1, x2, y2)


def _rect_to_polygon(rect: Optional[Rect]) -> list[tuple[int, int]] | None:
    if rect is None:
        return None
    x1, y1, x2, y2 = rect
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _polygon_to_rect(polygon: Optional[list[tuple[int, int]]]) -> Optional[Rect]:
    if not polygon:
        return None
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _roi_overlays(
    lane_rect: Optional[Rect],
    plate_rect: Optional[Rect],
    active_rect: Optional[Rect],
) -> list[Overlay]:
    overlays: list[Overlay] = []
    if lane_rect:
        overlays.append((lane_rect, QtGui.QColor(0, 200, 255)))
    if plate_rect:
        overlays.append((plate_rect, QtGui.QColor(255, 180, 0)))
    if active_rect:
        overlays.append((active_rect, QtGui.QColor(0, 255, 0)))
    return overlays


def _draw_detections(
    painter: QtGui.QPainter,
    detections: list | None,
    color: QtGui.QColor,
) -> None:
    if not detections:
        return
    painter.setPen(QtGui.QPen(color, 2))
    for det in detections:
        radius = max(2, int(det.radius_px))
        painter.drawEllipse(
            int(det.u - radius),
            int(det.v - radius),
            int(radius * 2),
            int(radius * 2),
        )


def _draw_plate_grid(
    painter: QtGui.QPainter,
    rect: Rect,
    color: QtGui.QColor,
    zone: tuple[int, int] | None,
) -> None:
    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return
    if zone is not None:
        row, col = zone
        col_index = max(1, min(3, col)) - 1
        row_index = max(1, min(3, row)) - 1
        cell_w = width / 3.0
        cell_h = height / 3.0
        row_from_top = 2 - row_index
        cell_x1 = x1 + int(cell_w * col_index)
        cell_y1 = y1 + int(cell_h * row_from_top)
        cell_x2 = x1 + int(cell_w * (col_index + 1))
        cell_y2 = y1 + int(cell_h * (row_from_top + 1))
        brush = QtGui.QBrush(QtGui.QColor(255, 180, 0, 60))
        painter.fillRect(
            QtCore.QRect(cell_x1, cell_y1, cell_x2 - cell_x1, cell_y2 - cell_y1),
            brush,
        )
    painter.setPen(QtGui.QPen(color, 1, QtCore.Qt.DashLine))
    for i in range(1, 3):
        x = x1 + int(width * i / 3.0)
        y = y1 + int(height * i / 3.0)
        painter.drawLine(x, y1, x, y2)
        painter.drawLine(x1, y, x2, y)


class CalibrationGuide(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibration Guide")
        self.resize(640, 480)
        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setText(
            "\n".join(
                [
                    "Quick Calibration Steps:",
                    "",
                    "1) Mount & Focus",
                    "   - Lock focus on both lenses at install distance.",
                    "   - Disable auto exposure/gain/WB in the config.",
                    "",
                    "2) Verify Dual Capture",
                    "   - Start capture and confirm both feeds are live.",
                    "   - Check fps and drop rate in the status bar.",
                    "",
                    "3) Calibrate Lane ROI",
                    "   - Click 'Edit Lane ROI' and drag a rectangle around the pitch lane.",
                    "   - Use the area covering roughly 40-60 ft downrange.",
                    "   - Save ROIs.",
                    "",
                    "4) Calibrate Plate ROI",
                    "   - Click 'Edit Plate ROI' and drag around the strike zone + batter box area.",
                    "   - Save ROIs.",
                    "",
                    "5) Stereo Calibration (Optional, but recommended)",
                    "   - Capture checkerboard images for left/right.",
                    "   - Run: python -m calib.quick_calibrate --left ... --right ... --square-mm ... --write",
                    "   - Confirm baseline_ft and focal_length_px updated in config.",
                    "",
                    "6) Test Run/Rise",
                    "   - Observe run/rise in the status bar (plate window).",
                    "",
                    "Tip: Re-run the guide any time you update the rig or lenses.",
                ]
            )
        )
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(steps)
        layout.addWidget(close_button)
        self.setLayout(layout)


class QuickCalibrateDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, config_path: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Calibrate")
        self.resize(520, 240)
        self._config_path = config_path
        self.updated = False
        self.updates: dict | None = None

        self._left_dir = QtWidgets.QLineEdit()
        self._right_dir = QtWidgets.QLineEdit()
        self._pattern = QtWidgets.QLineEdit("9x6")
        self._square_mm = QtWidgets.QDoubleSpinBox()
        self._square_mm.setMinimum(1.0)
        self._square_mm.setMaximum(1000.0)
        self._square_mm.setValue(25.0)
        self._ext = QtWidgets.QLineEdit("*.png")

        left_browse = QtWidgets.QPushButton("Browse")
        right_browse = QtWidgets.QPushButton("Browse")
        left_browse.clicked.connect(lambda: self._browse_dir(self._left_dir))
        right_browse.clicked.connect(lambda: self._browse_dir(self._right_dir))

        form = QtWidgets.QFormLayout()
        left_row = QtWidgets.QHBoxLayout()
        left_row.addWidget(self._left_dir)
        left_row.addWidget(left_browse)
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self._right_dir)
        right_row.addWidget(right_browse)
        form.addRow("Left images folder", left_row)
        form.addRow("Right images folder", right_row)
        form.addRow("Pattern (cols x rows)", self._pattern)
        form.addRow("Square size (mm)", self._square_mm)
        form.addRow("Image glob", self._ext)

        buttons = QtWidgets.QHBoxLayout()
        run_button = QtWidgets.QPushButton("Run Calibration")
        close_button = QtWidgets.QPushButton("Close")
        run_button.clicked.connect(self._run)
        close_button.clicked.connect(self.reject)
        buttons.addWidget(run_button)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _browse_dir(self, target: QtWidgets.QLineEdit) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            target.setText(path)

    def _run(self) -> None:
        left_dir = Path(self._left_dir.text().strip())
        right_dir = Path(self._right_dir.text().strip())
        pattern = self._pattern.text().strip()
        glob_pattern = self._ext.text().strip() or "*.png"
        if not left_dir.exists() or not right_dir.exists():
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "Select both folders.")
            return
        left_paths = sorted(left_dir.glob(glob_pattern))
        right_paths = sorted(right_dir.glob(glob_pattern))
        if not left_paths or not right_paths:
            QtWidgets.QMessageBox.warning(self, "Quick Calibrate", "No images found.")
            return
        try:
            updates = calibrate_and_write(
                left_paths=left_paths,
                right_paths=right_paths,
                pattern=pattern,
                square_mm=self._square_mm.value(),
                config_path=self._config_path,
            )
        except Exception as exc:  # noqa: BLE001 - show calibration errors
            QtWidgets.QMessageBox.critical(self, "Quick Calibrate", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self,
            "Quick Calibrate",
            f"Updated stereo config: {updates}",
        )
        self.updated = True
        self.updates = updates


def main() -> None:
    args = parse_args()
    app = QtWidgets.QApplication([])
    window = MainWindow(backend=args.backend, config_path=args.config)
    window.resize(1280, 720)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
