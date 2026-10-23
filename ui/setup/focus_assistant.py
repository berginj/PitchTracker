"""Live manual-focus view; capture stays in a supervised service process."""

from __future__ import annotations

from collections import deque
import time
from typing import Any

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from calib.focus_guidance import FocusGuide, TurnDirection
from contracts.focus_preview import FocusPreviewFrame
from ui.themes import apply_standard_layout, get_style_manager, style_status_label


class FocusImageView(QtWidgets.QGraphicsView):
    """Keep original pixels available for fitting, zooming and panning."""

    target_selected = QtCore.Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.image_item = QtWidgets.QGraphicsPixmapItem()
        self.scene().addItem(self.image_item)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setMinimumSize(160, 120)
        self.setAccessibleName("Manual focus image")
        self.setAccessibleDescription("Enter selects the visible centre; arrow keys move the target. Drag to pan when zoomed.")
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.zoom_factor = 0.0
        self.target: tuple[float, float] | None = None
        self.target_item = QtWidgets.QGraphicsRectItem()
        pen = QtGui.QPen(QtGui.QColor("#2563eb"), 2)
        pen.setCosmetic(True)
        self.target_item.setPen(pen)
        self.target_item.setZValue(1)
        self.scene().addItem(self.target_item)

    def set_image(self, image: np.ndarray) -> None:
        """Display a source image without changing its aspect ratio."""
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB if image.ndim == 2 else cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        qimage = QtGui.QImage(
            rgb.data, width, height, int(rgb.strides[0]), QtGui.QImage.Format.Format_RGB888,
        ).copy()
        previous_size = self.image_item.pixmap().size()
        self.image_item.setPixmap(QtGui.QPixmap.fromImage(qimage))
        self.scene().setSceneRect(self.image_item.boundingRect())
        if self.zoom_factor == 0 or previous_size != self.image_item.pixmap().size():
            self.set_zoom(self.zoom_factor)
        self.set_target(self.target)

    def set_target(self, target: tuple[float, float] | None) -> None:
        """Overlay the same source-pixel patch used by the focus guide."""
        self.target = target
        self.target_item.setVisible(target is not None)
        if target is not None:
            bounds = self.image_item.boundingRect()
            x, y = target[0] * max(0, bounds.width() - 1), target[1] * max(0, bounds.height() - 1)
            patch = QtCore.QRectF(x - 64, y - 64, 129, 129).intersected(bounds)
            self.target_item.setRect(patch)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        point = self.mapToScene(event.position().toPoint())
        bounds = self.image_item.boundingRect()
        if bounds.contains(point) and bounds.width() > 1 and bounds.height() > 1:
            self.target_selected.emit(min(1, point.x() / (bounds.width() - 1)),
                                      min(1, point.y() / (bounds.height() - 1)))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def set_zoom(self, factor: float) -> None:
        """Zero fits the image; positive factors show source pixels at scale."""
        self.zoom_factor = factor
        if factor == 0:
            self.fitInView(self.image_item, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.resetTransform()
            self.scale(factor, factor)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Provide the same target selection without requiring a pointing device."""
        bounds = self.image_item.boundingRect()
        moves = {QtCore.Qt.Key.Key_Left: (-0.02, 0), QtCore.Qt.Key.Key_Right: (0.02, 0),
                 QtCore.Qt.Key.Key_Up: (0, -0.02), QtCore.Qt.Key.Key_Down: (0, 0.02)}
        if not bounds.isEmpty() and event.key() in (*moves, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            centre = self.mapToScene(self.viewport().rect().center())
            x, y = self.target or (centre.x() / max(1, bounds.width() - 1),
                                   centre.y() / max(1, bounds.height() - 1))
            dx, dy = moves.get(event.key(), (0, 0))
            self.target_selected.emit(min(1, max(0, x + dx)), min(1, max(0, y + dy)))
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.zoom_factor == 0:
            self.set_zoom(0)


class FocusAssistantDialog(QtWidgets.QDialog):
    """A live image with a selected target and explicit turn comparisons."""

    capture_requested = QtCore.Signal()
    cancel_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Focus cameras")
        self.setModal(True)
        self.resize(1200, 850)
        self._images: dict[str, Any] = {}
        self._busy = False
        self._closing = False
        self._guides = {side: FocusGuide() for side in ("left", "right")}
        self._arrivals: dict[str, deque[float]] = {side: deque(maxlen=20) for side in ("left", "right")}
        self._failed = False
        self._source_stale: dict[str, bool] = {}
        self._black: dict[str, bool] = {}
        self._health_timer = QtCore.QTimer(self)
        self._health_timer.setInterval(250)
        self._health_timer.timeout.connect(self.show_health)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)
        guide = QtWidgets.QLabel(
            "Double-click the printed board to select the focus target. Looking at the front of the lens, "
            "choose a test direction BEFORE a small turn, then hold still for a second. "
            "Focus the image and press Enter to select its visible centre; arrow keys move the target. "
            "Drag to pan; use 200% to inspect edges. After focusing, mark the lens adjustment in Cameras."
        )
        guide.setWordWrap(True)
        layout.addWidget(guide)
        self.view = FocusImageView()
        self.view.target_selected.connect(self.select_target)
        controls = QtWidgets.QHBoxLayout()
        self.side = QtWidgets.QComboBox()
        self.side.addItem("Left camera", "left")
        self.side.addItem("Right camera", "right")
        self.side.setAccessibleName("Camera to focus")
        self.side.currentIndexChanged.connect(self.show_selected)
        controls.addWidget(self.side)
        self.zoom = QtWidgets.QComboBox()
        for title, factor in (("Fit image", 0.0), ("100%", 1.0), ("200%", 2.0), ("400%", 4.0)):
            self.zoom.addItem(title, factor)
        self.zoom.setAccessibleName("Focus image zoom")
        self.zoom.currentIndexChanged.connect(lambda: self.view.set_zoom(float(self.zoom.currentData())))
        controls.addWidget(self.zoom)
        self.refresh = QtWidgets.QPushButton("Start live preview (F5)")
        self.refresh.clicked.connect(self.toggle_live)
        self.refresh.setShortcut(QtGui.QKeySequence("F5"))
        get_style_manager().style_button(self.refresh, "primary")
        controls.addWidget(self.refresh)
        controls.addStretch()
        layout.addLayout(controls)
        self.status = QtWidgets.QLabel("Choose Start live preview. Cameras open once and stay open while focusing.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.view, 1)
        self.advice = QtWidgets.QLabel("Double-click the printed board to choose the focus target.")
        self.advice.setWordWrap(True)
        get_style_manager().style_label(self.advice, "sectionTitle")
        layout.addWidget(self.advice)
        self.sharpness = QtWidgets.QLabel("Sharpness unavailable")
        self.sharpness.setWordWrap(True)
        layout.addWidget(self.sharpness)
        turns = QtWidgets.QHBoxLayout()
        self.turn_buttons = []
        for label, direction in (("Test clockwise ↻", "clockwise"), ("Test counterclockwise ↺", "counterclockwise")):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, direction=direction: self.test_turn(direction))
            turns.addWidget(button)
            self.turn_buttons.append(button)
        layout.addLayout(turns)
        close = QtWidgets.QPushButton("Close focus view")
        close.clicked.connect(self.reject)
        layout.addWidget(close)

    def set_images(self, images: dict[str, Any]) -> None:
        """Show retained images without treating them as live focus observations."""
        self._images = dict(images)
        self.show_selected()
        style_status_label(self.status, "info", "Retained image. Start live preview before adjusting the lens.")

    def accept_frame(self, frame: FocusPreviewFrame) -> None:
        """Accept a fresh transient frame; this never creates setup evidence."""
        self._images[frame.side] = frame.image
        self._black[frame.side] = not bool(np.any(frame.image))
        self._arrivals[frame.side].append(time.monotonic())
        age_ns = time.monotonic_ns() - frame.t_capture_monotonic_ns
        self._source_stale[frame.side] = not 0 <= age_ns <= 1_000_000_000
        if not self._source_stale[frame.side]:
            self._guides[frame.side].observe(frame.image)
        else:
            self._guides[frame.side].invalidate("Waiting for fresh frames — pause lens adjustments.")
        if frame.side == self.side.currentData():
            self.show_selected()
        self.show_health()

    def show_selected(self) -> None:
        """Switch cameras without opening devices or changing saved settings."""
        image = self._images.get(str(self.side.currentData()))
        if image is None:
            self.view.image_item.setPixmap(QtGui.QPixmap())
            self.view.set_target(None)
            self.advice.setText("Start live preview and select a target for this camera.")
            self.sharpness.setText("Sharpness unavailable; start live preview.")
            return
        self.view.set_image(image)
        guide = self._guides[str(self.side.currentData())]
        self.view.set_target(guide.target)
        advice = guide.advice
        style_status_label(self.advice, advice.tone, advice.message)
        score = "unavailable" if advice.score is None else f"{advice.score:.0f} · best this test {advice.best:.0f}"
        change = "" if advice.change_percent is None else f" · change {advice.change_percent:+.0f}%"
        self.sharpness.setText(f"Target sharpness: {score}{change}. Relative guidance; run Image checks after focusing.")

    def select_target(self, x: float, y: float) -> None:
        """Changing the target resets comparisons; other camera state is retained."""
        self._guides[str(self.side.currentData())].select_target(x, y)
        self.show_selected()

    def test_turn(self, direction: TurnDirection) -> None:
        """Direction is reported by the operator, never guessed from a still frame."""
        side = str(self.side.currentData())
        arrivals = self._arrivals[side]
        fresh = bool(arrivals and time.monotonic() - arrivals[-1] <= 1 and not self._source_stale.get(side, True))
        if not self._busy or self._failed or not fresh or not self._guides[side].begin_turn(direction):
            style_status_label(self.advice, "info", "Start live preview, select the board, then hold still for a second.")
            return
        self.show_selected()

    def request_capture(self) -> None:
        """Request one persistent supervised stream."""
        if not self._busy and not self._closing:
            self._failed = False
            for guide in self._guides.values():
                if guide.target is not None:
                    guide.select_target(*guide.target)
            self.capture_requested.emit()

    def toggle_live(self) -> None:
        """The preview starts and stops through explicit service commands."""
        if not self._busy:
            self.request_capture()
        else:
            self.cancel_requested.emit()
            style_status_label(self.status, "info", "Stopping live preview…")

    def set_busy(self, busy: bool) -> None:
        """Retain closure until the camera-owning worker has stopped."""
        self._busy = busy
        if not busy:
            for guide in self._guides.values():
                guide.invalidate("Live preview stopped. Restart and let target sharpness settle.")
            self.show_selected()
        self.refresh.setText("Stop live preview (F5)" if busy else "Start live preview (F5)")
        if busy:
            self._arrivals = {side: deque(maxlen=20) for side in ("left", "right")}
            self._health_timer.start()
            style_status_label(self.status, "info", "Opening cameras once… live frames will follow.")
        elif self._closing:
            QtCore.QTimer.singleShot(0, self.reject)
        else:
            self._health_timer.stop()
            if not self._failed:
                style_status_label(self.status, "info", "Live preview stopped. Shown image is retained.")

    def show_health(self) -> None:
        if not self._busy or self._failed:
            return
        arrivals = self._arrivals[str(self.side.currentData())]
        if not arrivals:
            return
        if time.monotonic() - arrivals[-1] > 1 or self._source_stale.get(str(self.side.currentData()), False):
            self._guides[str(self.side.currentData())].invalidate("Waiting for fresh frames — pause lens adjustments.")
            self.show_selected()
            style_status_label(self.status, "warning", "Waiting for fresh frames — pause lens adjustments.")
            return
        fps = (len(arrivals) - 1) / max(0.001, arrivals[-1] - arrivals[0])
        if self._black.get(str(self.side.currentData()), False):
            style_status_label(self.status, "warning", f"Live · {fps:.1f} frames/s · Image is black — check lens cap, cable and lighting.")
            return
        style_status_label(self.status, "info", f"Live · {self.side.currentText()} · {fps:.1f} displayed frames/s")

    def show_failure(self, message: str) -> None:
        """Keep failure visible and require an explicit restart."""
        self._failed = True
        style_status_label(self.status, "error", message)

    def reject(self) -> None:
        self._health_timer.stop()
        if self._busy:
            self._closing = True
            self.cancel_requested.emit()
            style_status_label(self.status, "info", "Stopping capture before closing…")
            return
        super().reject()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.reject()
        event.setAccepted(not self._busy)
