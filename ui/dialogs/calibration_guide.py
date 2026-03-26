"""Calibration guide dialog with step-by-step instructions."""

from __future__ import annotations

from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    style_dialog_button_box,
)


class CalibrationGuide(QtWidgets.QDialog):
    """Dialog displaying calibration workflow instructions."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize calibration guide dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Calibration Guide")
        self.resize(640, 540)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI with theme system."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Header
        header = build_dialog_header(
            "Calibration Guide",
            "Step-by-step instructions for system calibration"
        )
        layout.addWidget(header)

        # Instructions
        steps = QtWidgets.QTextEdit()
        steps.setReadOnly(True)
        steps.setProperty("role", "panelMessage")
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
        layout.addWidget(steps)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        close_btn = button_box.addButton("Close", QtWidgets.QDialogButtonBox.AcceptRole)
        style_dialog_button_box(button_box, primary=True)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self._style_manager.polish_form_controls(self)


__all__ = ["CalibrationGuide"]
