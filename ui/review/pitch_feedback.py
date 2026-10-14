"""Recorded pitch feedback, kept independent from live capture state."""

from PySide6 import QtCore, QtWidgets

from app.review.recorded_metrics import recorded_metrics
from ui.themes import get_style_manager


class PitchFeedback(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.labels = {}
        for key, style in (("identity", "sectionTitle"), ("speed", "title"), ("source", "muted"),
                           ("result", "body"), ("location", "body"), ("quality", "muted"), ("playback", "muted")):
            label = QtWidgets.QLabel()
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            get_style_manager().style_label(label, style)
            layout.addWidget(label)
            self.labels[key] = label
        self.clear()

    def load_pitch(self, pitch, playback_reason: str = "") -> None:
        raw = getattr(pitch, "manifest", {})
        metrics = recorded_metrics(raw if isinstance(raw, dict) else {})
        self.labels["identity"].setText(f"Selected pitch · {pitch.pitch_id}")
        self.labels["speed"].setText(f"Speed: {metrics.speed}")
        self.labels["source"].setText(metrics.provenance)
        self.labels["result"].setText(f"Recorded result: {metrics.result}")
        self.labels["location"].setText(f"Plate location: {metrics.location}")
        self.labels["quality"].setText(f"Recorded status: {metrics.status}" + (f" · {metrics.reason}" if metrics.reason else ""))
        self.labels["playback"].setText(f"Pitch video unavailable: {playback_reason}" if playback_reason else "Pitch start mapped to recorded video.")

    def clear(self) -> None:
        for label in self.labels.values():
            label.clear()
        self.labels["identity"].setText("Select a recorded pitch")
        self.labels["quality"].setText("Historical selection is separate from the active recording.")
