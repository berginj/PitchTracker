"""Paired target picking and separate left/right lane and plate regions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_capture import SetupCapturePurpose
from ui.geometry import normalize_rect, rect_to_polygon
from ui.setup.guided_base import WorkflowStep, display_image
from ui.themes import style_status_label
from ui.widgets.roi_label import RoiLabel


class SetupImageLabel(RoiLabel):
    target_clicked = QtCore.Signal(object)

    def __init__(self, callback):
        super().__init__(callback)
        self.pick_target = True
        self.image: Any = None
        self.polygons: list[list[list[int]]] = []
        self.setMinimumSize(180, 130)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.pick_target and self.image_size() is not None:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                point = self._map_point(event.position().toPoint())
                self.target_clicked.emit([float(point.x()), float(point.y())])
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.image is not None:
            display_image(self, self.image)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        size = self.image_size()
        if size is None:
            return
        painter = QtGui.QPainter(self)
        painter.setPen(QtGui.QPen(QtGui.QColor("#35d3a5"), 2))
        for polygon in self.polygons:
            painter.drawPolygon(QtGui.QPolygonF([
                QtCore.QPointF(x * self.width() / size[0], y * self.height() / size[1]) for x, y in polygon
            ]))


class FieldStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService):
        super().__init__(workflow, "Field and regions")
        note = QtWidgets.QLabel(
            "Capture the surveyed targets. Add at least three fitting targets and one holdout. "
            "Select a target row, click the same target in both images, and enter its measured field X/Y/Z in feet."
        )
        note.setWordWrap(True)
        self.layout_box.addWidget(note)
        self.mode = QtWidgets.QComboBox()
        for label, value in (("Pick surveyed targets", "target"), ("Draw lane regions", "lane"), ("Draw plate regions", "plate")):
            self.mode.addItem(label, value)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.layout_box.addWidget(self.mode)
        target_row = QtWidgets.QHBoxLayout()
        self.table: QtWidgets.QTableWidget
        self.target_selector = QtWidgets.QComboBox()
        self.target_selector.currentIndexChanged.connect(lambda row: self.table.selectRow(row) if row >= 0 else None)
        target_row.addWidget(QtWidgets.QLabel("Target to pick"))
        target_row.addWidget(self.target_selector, 1)
        add = QtWidgets.QPushButton("Add target")
        add.clicked.connect(self.add_target)
        target_row.addWidget(add)
        self.layout_box.addLayout(target_row)
        image_layout = QtWidgets.QHBoxLayout()
        self.views: dict[str, SetupImageLabel] = {}
        for side in ("left", "right"):
            column = QtWidgets.QVBoxLayout()
            column.addWidget(QtWidgets.QLabel(f"{side.capitalize()} camera"))
            view = SetupImageLabel(lambda rect, final, side=side: self.region_drawn(side, rect, final))
            view.target_clicked.connect(lambda pixel, side=side: self.target_clicked(side, pixel))
            self.views[side] = view
            column.addWidget(view)
            image_layout.addLayout(column)
        self.layout_box.addLayout(image_layout)
        capture = QtWidgets.QPushButton("Capture target images")
        capture.clicked.connect(lambda: self.capture(SetupCapturePurpose.FIELD_PAIR, self.capture_ready))
        self.layout_box.addWidget(capture)
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Target", "Field X (ft)", "Field Y (ft)", "Field Z (ft)",
                                             "Holdout", "Left pixel", "Right pixel"])
        self.table.setMinimumHeight(140)
        self.table.itemChanged.connect(self.table_changed)
        self.layout_box.addWidget(self.table)
        buttons = QtWidgets.QHBoxLayout()
        for label, callback in (
            ("Add target", self.add_target), ("Remove target", self.remove_target),
            ("Check field alignment", self.check_field), ("Check regions", self.check_regions),
            ("Cancel", self.cancel_pending),
        ):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        self.layout_box.addLayout(buttons)
        self.footer()

    def refresh(self) -> None:
        self.render_targets()
        self.render_regions()
        self.show_saved()

    def render_targets(self) -> None:
        rows = self.workflow.state["targets"]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for row, target in enumerate(rows):
            values = [target["target_id"], *target["field_xyz_ft"], "",
                      str(target["left_pixel"]), str(target["right_pixel"])]
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem("" if value is None else str(value))
                if column == 4:
                    item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.CheckState.Checked if target["holdout"] else QtCore.Qt.CheckState.Unchecked)
                if column >= 5:
                    item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        selected = self.table.currentRow()
        self.target_selector.blockSignals(True)
        self.target_selector.clear()
        for target in rows:
            self.target_selector.addItem(target["target_id"] + (" (holdout)" if target["holdout"] else ""))
        self.target_selector.setCurrentIndex(max(0, selected) if rows else -1)
        self.target_selector.blockSignals(False)
        if rows and selected < 0:
            self.table.selectRow(0)

    def add_target(self) -> None:
        targets = self.workflow.state["targets"]
        suffix = 1
        while any(item["target_id"] == f"target-{suffix}" for item in targets):
            suffix += 1
        targets.append({"target_id": f"target-{suffix}", "field_xyz_ft": [None, None, None],
                        "left_pixel": [None, None], "right_pixel": [None, None], "holdout": False})
        self.action(lambda: self.workflow.update_targets(targets), edit=True)
        self.render_targets()
        self.table.selectRow(len(targets) - 1)

    def remove_target(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            targets = self.workflow.state["targets"]
            targets.pop(row)
            self.action(lambda: self.workflow.update_targets(targets), edit=True)
            self.render_targets()

    def table_changed(self, *_args) -> None:
        def save():
            targets = self.workflow.state["targets"]
            for row, target in enumerate(targets):
                items = [self.table.item(row, column) for column in range(5)]
                if any(item is None for item in items):
                    raise ValueError("Target row is incomplete")
                text = [item.text().strip() if item is not None else "" for item in items]
                target["target_id"] = text[0]
                target["field_xyz_ft"] = [float(text[column]) if text[column] else None for column in (1, 2, 3)]
                holdout = items[4]
                target["holdout"] = holdout is not None and holdout.checkState() == QtCore.Qt.CheckState.Checked
            self.workflow.update_targets(targets)
        self.action(save, edit=True)

    def target_clicked(self, side: str, pixel: list[float]) -> None:
        def save():
            row = self.table.currentRow()
            if row < 0 or not self.workflow.image_metadata:
                raise ValueError("Capture images and select a target row before clicking")
            targets = self.workflow.state["targets"]
            target = targets[row]
            pair = deepcopy(self.workflow.image_metadata)
            if target.get("source_pair", {}).get("correlation_id") != pair["correlation_id"]:
                target["confirmed_sides"] = []
            target[f"{side}_pixel"] = pixel
            target["confirmed_sides"] = sorted(set(target.get("confirmed_sides", [])) | {side})
            target["source_pair"] = pair
            target["calibration_sha256"] = self.workflow.artifact("calibration").stem
            self.workflow.update_targets(targets)
        self.action(save, edit=True)
        selected = self.table.currentRow()
        self.render_targets()
        self.table.selectRow(selected)

    def capture_ready(self, _payload) -> None:
        for side, view in self.views.items():
            view.image = self.workflow.images[side]
            height, width = view.image.shape[:2]
            view.set_image_size(width, height)
            display_image(view, view.image)
        self.render_regions()
        self.show_saved()

    def mode_changed(self, *_args) -> None:
        mode = self.mode.currentData()
        for view in self.views.values():
            view.pick_target = mode == "target"
            view.set_mode(None if view.pick_target else mode)

    def region_drawn(self, side: str, rect, final: bool) -> None:
        if not final:
            return
        normalized = normalize_rect(rect, self.views[side].image_size())
        polygon = rect_to_polygon(normalized)
        if polygon:
            self.action(lambda: self.workflow.save_region(
                side, self.mode.currentData(), [[x, y] for x, y in polygon],
            ), edit=True)
            self.render_regions()

    def render_regions(self) -> None:
        state = self.workflow.state
        for side, view in self.views.items():
            camera_id = state["camera_ids"].get(side)
            view.polygons = [
                polygon for kind in ("lane", "plate")
                if (polygon := state["regions"].get(f"{kind}_by_camera", {}).get(camera_id))
            ]
            view.update()

    def check_field(self) -> None:
        self.action(self.workflow.fit_field)
        self.set_details(self.workflow.state["checks"].get("field", {}))
        if self.workflow.state["checks"].get("field", {}).get("passed"):
            style_status_label(self.status, "success", "Field alignment and holdout passed")

    def check_regions(self) -> None:
        self.action(self.workflow.validate_regions)
        if self.workflow.state["checks"].get("regions", {}).get("passed"):
            style_status_label(self.status, "success", "Both cameras have valid lane and plate regions")

    def validate(self) -> tuple[bool, str]:
        state = self.workflow.state
        passed = all(state["checks"].get(name, {}).get("passed") and name in self.workflow.visit_checks
                     for name in ("field", "regions"))
        return bool(passed), "" if passed else "Check the field holdout and both cameras' regions"
