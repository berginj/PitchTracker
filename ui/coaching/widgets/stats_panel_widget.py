"""Latest recorded pitch feedback and a stable recent-pitch list."""

from __future__ import annotations

from math import isclose, isfinite
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from app.contracts import measurement_is_usable
from ui.themes import get_style_manager

if TYPE_CHECKING:
    from app.contracts import PitchSummary


class StatsPanelWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._recent_signature: tuple = ()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        self._title = self._label("Latest Pitch", "sectionTitle", layout)
        self._speed_label = self._label("Speed: unavailable", "title", layout)
        self._source_label = self._label("Source and reference appear with a recorded pitch.", "muted", layout)
        self._result_label = self._label("Result: waiting for a pitch", "sectionTitle", layout)
        self._quality_label = self._label("No pitch measured", "muted", layout)
        self._location_label = self._label("Plate location: unavailable", "default", layout)
        movement = QtWidgets.QHBoxLayout()
        self._h_break_label = QtWidgets.QLabel("H-Break: unavailable")
        self._v_break_label = QtWidgets.QLabel("V-Break: unavailable")
        for label in (self._h_break_label, self._v_break_label):
            label.setWordWrap(True)
            self._style_manager.style_label(label, "muted")
            movement.addWidget(label)
        layout.addLayout(movement)
        self._label("Recent pitches · newest first", "eyebrow", layout)
        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setAccessibleName("Recent recorded pitches")
        self._recent_list.setMinimumHeight(70)
        self._recent_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._recent_list.setWordWrap(True)
        layout.addWidget(self._recent_list, 1)
        self.setProperty("surface", "card")
        self._style_manager.polish(self)

    def _label(self, text: str, variant: str, layout: QtWidgets.QVBoxLayout) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        self._style_manager.style_label(label, variant)
        layout.addWidget(label)
        return label

    @staticmethod
    def _status(pitch) -> str:
        value = getattr(pitch, "measurement_status", "UNKNOWN")
        return str(getattr(value, "value", value)).upper()

    @staticmethod
    def _speed(pitch) -> str:
        speed = pitch.speed_mph
        return f"{speed:.1f} mph" if measurement_is_usable(pitch) and speed is not None and isfinite(speed) and speed > 0 else "unavailable"

    def update_latest_pitch(self, pitch: PitchSummary) -> None:
        usable = measurement_is_usable(pitch)
        status = self._status(pitch)
        self._title.setText(f"Latest Pitch · {pitch.pitch_id}")
        speed = self._speed(pitch)
        self._speed_label.setText(f"Speed: {speed}")
        source = getattr(pitch, "speed_source", None)
        measurements = [value for value in (getattr(pitch, "external_speed", None), getattr(pitch, "vision_speed", None))
                        if value and pitch.speed_mph is not None and isclose(value.speed_mph, pitch.speed_mph, abs_tol=1e-6)
                        and (not source or value.source == source)]
        if len(measurements) == 1:
            measurement = measurements[0]
            reference = measurement.reference.replace("_", " ")
            if measurement.reference_z_ft is not None:
                reference += f" · z {measurement.reference_z_ft:g} ft"
            provenance = f"{measurement.source.replace('_', ' ')} · {reference}"
        else:
            provenance = f"{source.replace('_', ' ') if source else 'Source not recorded'} · reference unavailable"
        self._source_label.setText(provenance)
        self._speed_label.setToolTip(provenance)
        call_available = usable and getattr(pitch, "strike_call_available", True)
        result = ("STRIKE" if pitch.is_strike else "BALL") if call_available else (status if not usable else "UNAVAILABLE")
        self._result_label.setText(f"Result: {result}")
        self._style_manager.style_status_indicator(self._result_label, "info" if call_available else "warning")
        reasons = getattr(pitch, "observation_rejection_reasons", None) or getattr(pitch, "observation_warning_reasons", None) or []
        reason = getattr(pitch, "strike_call_reason", None) or "; ".join(reasons)
        short_reason = reason[:100] + ("…" if len(reason) > 100 else "")
        self._quality_label.setAccessibleDescription(reason)
        self._quality_label.setText(f"Recorded status: {status}" + (f" · {short_reason}" if reason else ""))
        if not call_available and not reason:
            self._quality_label.setText(f"Recorded status: {status} · No eligible strike/ball call or location marker.")
        x, y = pitch.trajectory_plate_x_ft, pitch.trajectory_plate_y_ft
        if usable and x is not None and y is not None and isfinite(x) and isfinite(y):
            self._location_label.setText(f"Plate location: x {x:+.2f} ft · height {y:.2f} ft")
        else:
            self._location_label.setText("Plate location: unavailable")
        validated = (usable and bool((pitch.quality_diagnostics or {}).get("movement_validated"))
                     and isfinite(pitch.run_in) and isfinite(pitch.rise_in))
        self._h_break_label.setText(f"H-Break: {pitch.run_in:+.1f} in" if validated else "H-Break: unavailable")
        self._v_break_label.setText(f"V-Break: {pitch.rise_in:+.1f} in" if validated else "V-Break: unavailable")
        detail = "Movement remains unavailable without validation. Raw displacement is available in Advanced Tools."
        self._h_break_label.setToolTip(detail)
        self._v_break_label.setToolTip(detail)

    def update_recent_list(self, recent_pitches: list[PitchSummary]) -> None:
        rows = []
        for index, pitch in list(enumerate(recent_pitches))[-10:][::-1]:
            status = self._status(pitch)
            usable = measurement_is_usable(pitch) and getattr(pitch, "strike_call_available", True)
            verdict = ("STRIKE" if pitch.is_strike else "BALL") if usable else (status if not measurement_is_usable(pitch) else "UNAVAILABLE")
            identity = getattr(pitch, "pitch_id", f"pitch_{index + 1}")
            rows.append((identity, f"#{index + 1} · {self._speed(pitch)} · {verdict} · {status}"))
        signature = tuple(rows)
        if signature == self._recent_signature:
            return
        selected = self._recent_list.currentItem()
        selected_id = selected.data(QtCore.Qt.ItemDataRole.UserRole) if selected else None
        scroll = self._recent_list.verticalScrollBar().value()
        self._recent_list.clear()
        for identity, text in rows:
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, identity)
            self._recent_list.addItem(item)
            if identity == selected_id:
                self._recent_list.setCurrentItem(item)
        self._recent_list.verticalScrollBar().setValue(scroll)
        self._recent_signature = signature

    def clear(self) -> None:
        self._title.setText("Latest Pitch")
        self._speed_label.setText("Speed: unavailable")
        self._source_label.setText("Source and reference appear with a recorded pitch.")
        self._speed_label.setToolTip("")
        self._result_label.setText("Result: waiting for a pitch")
        self._quality_label.setText("No pitch measured")
        self._quality_label.setAccessibleDescription("")
        self._location_label.setText("Plate location: unavailable")
        for label in (self._h_break_label, self._v_break_label):
            label.setText("H-Break: unavailable" if label is self._h_break_label else "V-Break: unavailable")
        self._recent_list.clear()
        self._recent_signature = ()


__all__ = ["StatsPanelWidget"]
