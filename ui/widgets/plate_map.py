"""Strike zone plate map with pitch trails and simple game overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from contracts import StereoObservation
from metrics.strike_zone import StrikeZone


@dataclass(frozen=True)
class PitchTrail:
    points_ft: List[Tuple[float, float]]
    crossing_ft: Optional[Tuple[float, float]]


class PlateMapWidget(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._zone: Optional[StrikeZone] = None
        self._trails: List[PitchTrail] = []
        self._board: List[List[str]] = [["", "", ""], ["", "", ""], ["", "", ""]]
        self._target_cell: Optional[Tuple[int, int]] = None
        self._crossing_point: Optional[Tuple[float, float]] = None
        self.setMinimumSize(280, 220)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding,
        )

    def set_zone(self, zone: StrikeZone) -> None:
        self._zone = zone
        self.update()

    def set_pitch_paths(self, paths: Sequence[Sequence[StereoObservation]]) -> None:
        if self._zone is None:
            self._trails = []
            self.update()
            return
        trails: List[PitchTrail] = []
        plate_z = self._zone.plate_z_ft
        for path in paths:
            points = [(obs.X, obs.Y) for obs in path]
            if not points:
                continue
            crossing = _closest_to_plate(path, plate_z)
            trails.append(PitchTrail(points_ft=points, crossing_ft=crossing))
        self._trails = trails
        self.update()

    def set_board(self, board: List[List[str]]) -> None:
        self._board = board
        self.update()

    def set_target_cell(self, cell: Optional[Tuple[int, int]]) -> None:
        self._target_cell = cell
        self.update()

    def set_crossing_point(self, point_ft: Optional[Tuple[float, float]]) -> None:
        self._crossing_point = point_ft
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor(12, 15, 18))

        if self._zone is None:
            painter.end()
            return

        zone_rect, x_min, x_max, y_min, y_max = _zone_geometry(rect, self._zone)
        _draw_zone(painter, zone_rect)
        _draw_grid(painter, zone_rect)
        _draw_trails(painter, zone_rect, x_min, x_max, y_min, y_max, self._trails)
        _draw_tic_tac_toe(painter, zone_rect, self._board)
        _draw_target_cell(painter, zone_rect, self._target_cell)
        _draw_crossing_point(
            painter,
            zone_rect,
            x_min,
            x_max,
            y_min,
            y_max,
            self._crossing_point,
        )
        painter.end()


def _zone_geometry(
    rect: QtCore.QRect,
    zone: StrikeZone,
) -> Tuple[QtCore.QRectF, float, float, float, float]:
    margin = 12.0
    width = rect.width() - margin * 2
    height = rect.height() - margin * 2
    zone_width_ft = _zone_width_ft(zone)
    zone_height_ft = zone.y_top_ft - zone.y_bottom_ft
    if zone_width_ft <= 0 or zone_height_ft <= 0:
        zone_width_ft = 2.0
        zone_height_ft = 3.0
    scale = min(width / zone_width_ft, height / zone_height_ft)
    draw_width = zone_width_ft * scale
    draw_height = zone_height_ft * scale
    left = rect.center().x() - draw_width / 2
    top = rect.center().y() - draw_height / 2
    zone_rect = QtCore.QRectF(left, top, draw_width, draw_height)
    x_min = -zone_width_ft / 2.0
    x_max = zone_width_ft / 2.0
    y_min = zone.y_bottom_ft
    y_max = zone.y_top_ft
    return zone_rect, x_min, x_max, y_min, y_max


def _zone_width_ft(zone: StrikeZone) -> float:
    xs = [point[0] for point in zone.polygon_xz]
    if not xs:
        return 0.0
    return max(xs) - min(xs)


def _draw_zone(painter: QtGui.QPainter, zone_rect: QtCore.QRectF) -> None:
    painter.setPen(QtGui.QPen(QtGui.QColor(220, 230, 240), 2))
    painter.drawRoundedRect(zone_rect, 6, 6)


def _draw_grid(painter: QtGui.QPainter, zone_rect: QtCore.QRectF) -> None:
    pen = QtGui.QPen(QtGui.QColor(110, 130, 150), 1, QtCore.Qt.DashLine)
    painter.setPen(pen)
    third_w = zone_rect.width() / 3.0
    third_h = zone_rect.height() / 3.0
    for i in range(1, 3):
        x = zone_rect.left() + third_w * i
        y = zone_rect.top() + third_h * i
        painter.drawLine(QtCore.QPointF(x, zone_rect.top()), QtCore.QPointF(x, zone_rect.bottom()))
        painter.drawLine(QtCore.QPointF(zone_rect.left(), y), QtCore.QPointF(zone_rect.right(), y))


def _draw_trails(
    painter: QtGui.QPainter,
    zone_rect: QtCore.QRectF,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    trails: Iterable[PitchTrail],
) -> None:
    trails_list = list(trails)
    if not trails_list:
        return
    total = len(trails_list)
    for idx, trail in enumerate(trails_list):
        age = (total - 1 - idx) / max(total - 1, 1)
        alpha = int(60 + 140 * (1.0 - age))
        color = QtGui.QColor(64, 196, 255, alpha)
        pen = QtGui.QPen(color, 2)
        painter.setPen(pen)
        points = [_map_point(pt, zone_rect, x_min, x_max, y_min, y_max) for pt in trail.points_ft]
        if len(points) > 1:
            painter.drawPolyline(points)
        if trail.crossing_ft is not None:
            cross = _map_point(trail.crossing_ft, zone_rect, x_min, x_max, y_min, y_max)
            painter.setBrush(QtGui.QColor(255, 200, 64, alpha))
            painter.drawEllipse(cross, 5, 5)


def _draw_tic_tac_toe(
    painter: QtGui.QPainter,
    zone_rect: QtCore.QRectF,
    board: List[List[str]],
) -> None:
    font = painter.font()
    font.setPointSizeF(max(zone_rect.height() / 10.0, 10.0))
    painter.setFont(font)
    painter.setPen(QtGui.QPen(QtGui.QColor(240, 240, 240), 2))
    cell_w = zone_rect.width() / 3.0
    cell_h = zone_rect.height() / 3.0
    for row in range(3):
        for col in range(3):
            value = board[row][col]
            if not value:
                continue
            rect = QtCore.QRectF(
                zone_rect.left() + col * cell_w,
                zone_rect.top() + (2 - row) * cell_h,
                cell_w,
                cell_h,
            )
            painter.drawText(rect, QtCore.Qt.AlignCenter, value)


def _draw_target_cell(
    painter: QtGui.QPainter,
    zone_rect: QtCore.QRectF,
    cell: Optional[Tuple[int, int]],
) -> None:
    if cell is None:
        return
    row, col = cell
    cell_w = zone_rect.width() / 3.0
    cell_h = zone_rect.height() / 3.0
    rect = QtCore.QRectF(
        zone_rect.left() + col * cell_w,
        zone_rect.top() + (2 - row) * cell_h,
        cell_w,
        cell_h,
    )
    pen = QtGui.QPen(QtGui.QColor(255, 120, 64), 3)
    painter.setPen(pen)
    painter.setBrush(QtGui.QColor(255, 120, 64, 40))
    painter.drawRoundedRect(rect.adjusted(6, 6, -6, -6), 8, 8)


def _draw_crossing_point(
    painter: QtGui.QPainter,
    zone_rect: QtCore.QRectF,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    point: Optional[Tuple[float, float]],
) -> None:
    if point is None:
        return
    mapped = _map_point(point, zone_rect, x_min, x_max, y_min, y_max)
    painter.setPen(QtGui.QPen(QtGui.QColor(255, 80, 80), 2))
    painter.setBrush(QtGui.QColor(255, 80, 80, 180))
    painter.drawEllipse(mapped, 6, 6)


def _map_point(
    point: Tuple[float, float],
    zone_rect: QtCore.QRectF,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> QtCore.QPointF:
    x, y = point
    x_norm = 0.0 if x_max == x_min else (x - x_min) / (x_max - x_min)
    y_norm = 0.0 if y_max == y_min else (y - y_min) / (y_max - y_min)
    px = zone_rect.left() + x_norm * zone_rect.width()
    py = zone_rect.bottom() - y_norm * zone_rect.height()
    return QtCore.QPointF(px, py)


def _closest_to_plate(
    path: Sequence[StereoObservation],
    plate_z_ft: float,
) -> Optional[Tuple[float, float]]:
    if not path:
        return None
    closest = min(path, key=lambda obs: abs(obs.Z - plate_z_ft))
    return (closest.X, closest.Y)
