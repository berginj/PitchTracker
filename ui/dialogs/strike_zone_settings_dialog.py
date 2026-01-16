"""Strike zone settings dialog."""

from __future__ import annotations

from PySide6 import QtWidgets


class StrikeZoneSettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring strike zone parameters."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        ball_type: str,
        batter_height: float,
        top_ratio: float,
        bottom_ratio: float,
    ) -> None:
        """Initialize strike zone settings dialog.

        Args:
            parent: Parent widget
            ball_type: "baseball" or "softball"
            batter_height: Batter height in inches
            top_ratio: Strike zone top as ratio of batter height
            bottom_ratio: Strike zone bottom as ratio of batter height
        """
        super().__init__(parent)
        self.setWindowTitle("Strike Zone Settings")
        self.resize(420, 200)

        self._ball = QtWidgets.QComboBox()
        self._ball.addItems(["baseball", "softball"])
        self._ball.setCurrentText(ball_type)

        self._height = QtWidgets.QDoubleSpinBox()
        self._height.setMinimum(40.0)
        self._height.setMaximum(96.0)
        self._height.setSuffix(" in")
        self._height.setValue(batter_height)

        self._top = QtWidgets.QDoubleSpinBox()
        self._bottom = QtWidgets.QDoubleSpinBox()

        for ratio in (self._top, self._bottom):
            ratio.setMinimum(0.0)
            ratio.setMaximum(1.0)
            ratio.setSingleStep(0.01)

        self._top.setValue(top_ratio)
        self._bottom.setValue(bottom_ratio)

        # Form layout
        form = QtWidgets.QFormLayout()
        form.addRow("Ball type", self._ball)
        form.addRow("Batter height", self._height)
        form.addRow("Top ratio", self._top)
        form.addRow("Bottom ratio", self._bottom)

        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        apply_button = QtWidgets.QPushButton("Apply")
        cancel_button = QtWidgets.QPushButton("Cancel")
        apply_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def values(self) -> tuple[str, float, float, float]:
        """Get configured values.

        Returns:
            Tuple of (ball_type, batter_height_in, top_ratio, bottom_ratio)
        """
        return (
            self._ball.currentText(),
            self._height.value(),
            self._top.value(),
            self._bottom.value(),
        )


__all__ = ["StrikeZoneSettingsDialog"]
