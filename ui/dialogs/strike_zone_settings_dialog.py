"""Strike zone settings dialog."""

from __future__ import annotations

from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


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
        self.resize(520, 300)
        self._style_manager = get_style_manager()

        # Initialize widgets
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
            ratio.setDecimals(2)

        self._top.setValue(top_ratio)
        self._bottom.setValue(bottom_ratio)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header("Strike Zone Settings", "Configure strike zone dimensions and ball type")
        layout.addWidget(header)

        # Form layout
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)
        form.addRow("Ball type:", self._ball)
        form.addRow("Batter height:", self._height)
        form.addRow("Top ratio:", self._top)
        form.addRow("Bottom ratio:", self._bottom)

        layout.addLayout(form)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        button_box.addButton("Apply", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("Cancel", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)

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
