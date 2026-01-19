"""Parameter tuning panel for adjusting detection settings."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from detect.config import Mode


class ParameterPanel(QtWidgets.QWidget):
    """Panel for tuning detection parameters in real-time.

    Provides sliders and controls for:
    - Detection mode (MODE_A, MODE_B, MODE_C)
    - Frame diff threshold
    - Background diff threshold
    - Min/max blob area
    - Circularity filters

    Signals:
        parameter_changed: Emitted when any parameter changes
    """

    # Signal emitted when parameters change
    parameter_changed = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize parameter panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Current parameter values
        self._mode = Mode.MODE_A
        self._frame_diff_threshold = 18.0
        self._bg_diff_threshold = 12.0
        self._min_area = 12
        self._max_area = 500
        self._min_circularity = 0.1

        self._build_ui()

    def _build_ui(self) -> None:
        """Build parameter controls UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Detection Parameters")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Mode selector
        mode_group = self._build_mode_selector()
        layout.addWidget(mode_group)

        # Threshold sliders
        threshold_group = self._build_threshold_sliders()
        layout.addWidget(threshold_group)

        # Filter sliders
        filter_group = self._build_filter_sliders()
        layout.addWidget(filter_group)

        # Reset button
        reset_btn = QtWidgets.QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._reset_parameters)
        reset_btn.setToolTip("Reset all parameters to original session values")
        layout.addWidget(reset_btn)

        # Apply button
        apply_btn = QtWidgets.QPushButton("Apply Changes")
        apply_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        apply_btn.clicked.connect(self.parameter_changed.emit)
        layout.addWidget(apply_btn)

        layout.addStretch()

        self.setLayout(layout)
        self.setMaximumWidth(350)

    def _build_mode_selector(self) -> QtWidgets.QGroupBox:
        """Build detection mode selector.

        Returns:
            Group box with mode radio buttons
        """
        group = QtWidgets.QGroupBox("Detection Mode")

        self._mode_a_radio = QtWidgets.QRadioButton("MODE_A (Standard)")
        self._mode_a_radio.setChecked(True)
        self._mode_a_radio.toggled.connect(lambda: self._set_mode(Mode.MODE_A))

        self._mode_b_radio = QtWidgets.QRadioButton("MODE_B (Sensitive)")
        self._mode_b_radio.toggled.connect(lambda: self._set_mode(Mode.MODE_B))

        self._mode_c_radio = QtWidgets.QRadioButton("MODE_C (Aggressive)")
        self._mode_c_radio.toggled.connect(lambda: self._set_mode(Mode.MODE_C))

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._mode_a_radio)
        layout.addWidget(self._mode_b_radio)
        layout.addWidget(self._mode_c_radio)

        group.setLayout(layout)
        return group

    def _build_threshold_sliders(self) -> QtWidgets.QGroupBox:
        """Build threshold slider controls.

        Returns:
            Group box with threshold sliders
        """
        group = QtWidgets.QGroupBox("Thresholds")

        # Frame diff threshold
        frame_diff_label = QtWidgets.QLabel("Frame Diff:")
        self._frame_diff_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._frame_diff_slider.setRange(1, 50)
        self._frame_diff_slider.setValue(18)
        self._frame_diff_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._frame_diff_slider.setTickInterval(5)
        self._frame_diff_value = QtWidgets.QLabel("18.0")
        self._frame_diff_slider.valueChanged.connect(self._on_frame_diff_changed)

        # BG diff threshold
        bg_diff_label = QtWidgets.QLabel("BG Diff:")
        self._bg_diff_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._bg_diff_slider.setRange(1, 30)
        self._bg_diff_slider.setValue(12)
        self._bg_diff_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._bg_diff_slider.setTickInterval(5)
        self._bg_diff_value = QtWidgets.QLabel("12.0")
        self._bg_diff_slider.valueChanged.connect(self._on_bg_diff_changed)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(frame_diff_label, 0, 0)
        layout.addWidget(self._frame_diff_slider, 0, 1)
        layout.addWidget(self._frame_diff_value, 0, 2)
        layout.addWidget(bg_diff_label, 1, 0)
        layout.addWidget(self._bg_diff_slider, 1, 1)
        layout.addWidget(self._bg_diff_value, 1, 2)

        group.setLayout(layout)
        return group

    def _build_filter_sliders(self) -> QtWidgets.QGroupBox:
        """Build filter slider controls.

        Returns:
            Group box with filter sliders
        """
        group = QtWidgets.QGroupBox("Blob Filters")

        # Min area
        min_area_label = QtWidgets.QLabel("Min Area:")
        self._min_area_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._min_area_slider.setRange(1, 50)
        self._min_area_slider.setValue(12)
        self._min_area_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._min_area_slider.setTickInterval(5)
        self._min_area_value = QtWidgets.QLabel("12")
        self._min_area_slider.valueChanged.connect(self._on_min_area_changed)

        # Max area
        max_area_label = QtWidgets.QLabel("Max Area:")
        self._max_area_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._max_area_slider.setRange(100, 1000)
        self._max_area_slider.setValue(500)
        self._max_area_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._max_area_slider.setTickInterval(100)
        self._max_area_value = QtWidgets.QLabel("500")
        self._max_area_slider.valueChanged.connect(self._on_max_area_changed)

        # Min circularity
        min_circ_label = QtWidgets.QLabel("Min Circularity:")
        self._min_circ_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._min_circ_slider.setRange(0, 100)
        self._min_circ_slider.setValue(10)
        self._min_circ_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        self._min_circ_slider.setTickInterval(10)
        self._min_circ_value = QtWidgets.QLabel("0.10")
        self._min_circ_slider.valueChanged.connect(self._on_min_circ_changed)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(min_area_label, 0, 0)
        layout.addWidget(self._min_area_slider, 0, 1)
        layout.addWidget(self._min_area_value, 0, 2)
        layout.addWidget(max_area_label, 1, 0)
        layout.addWidget(self._max_area_slider, 1, 1)
        layout.addWidget(self._max_area_value, 1, 2)
        layout.addWidget(min_circ_label, 2, 0)
        layout.addWidget(self._min_circ_slider, 2, 1)
        layout.addWidget(self._min_circ_value, 2, 2)

        group.setLayout(layout)
        return group

    def _set_mode(self, mode: Mode) -> None:
        """Set detection mode.

        Args:
            mode: Detection mode
        """
        self._mode = mode
        self.parameter_changed.emit()

    def _on_frame_diff_changed(self, value: int) -> None:
        """Handle frame diff slider change."""
        self._frame_diff_threshold = float(value)
        self._frame_diff_value.setText(f"{self._frame_diff_threshold:.1f}")
        self.parameter_changed.emit()

    def _on_bg_diff_changed(self, value: int) -> None:
        """Handle BG diff slider change."""
        self._bg_diff_threshold = float(value)
        self._bg_diff_value.setText(f"{self._bg_diff_threshold:.1f}")
        self.parameter_changed.emit()

    def _on_min_area_changed(self, value: int) -> None:
        """Handle min area slider change."""
        self._min_area = value
        self._min_area_value.setText(str(value))
        self.parameter_changed.emit()

    def _on_max_area_changed(self, value: int) -> None:
        """Handle max area slider change."""
        self._max_area = value
        self._max_area_value.setText(str(value))
        self.parameter_changed.emit()

    def _on_min_circ_changed(self, value: int) -> None:
        """Handle min circularity slider change."""
        self._min_circularity = value / 100.0
        self._min_circ_value.setText(f"{self._min_circularity:.2f}")
        self.parameter_changed.emit()

    def _reset_parameters(self) -> None:
        """Reset parameters to original values."""
        # Reset to defaults
        self._mode_a_radio.setChecked(True)
        self._frame_diff_slider.setValue(18)
        self._bg_diff_slider.setValue(12)
        self._min_area_slider.setValue(12)
        self._max_area_slider.setValue(500)
        self._min_circ_slider.setValue(10)

        self.parameter_changed.emit()

    def load_parameters(
        self,
        mode: Mode,
        frame_diff_threshold: float,
        bg_diff_threshold: float,
        min_area: int,
        max_area: int,
        min_circularity: float,
    ) -> None:
        """Load parameters from config.

        Args:
            mode: Detection mode
            frame_diff_threshold: Frame diff threshold
            bg_diff_threshold: BG diff threshold
            min_area: Min blob area
            max_area: Max blob area
            min_circularity: Min circularity
        """
        # Set mode
        if mode == Mode.MODE_A:
            self._mode_a_radio.setChecked(True)
        elif mode == Mode.MODE_B:
            self._mode_b_radio.setChecked(True)
        elif mode == Mode.MODE_C:
            self._mode_c_radio.setChecked(True)

        # Set sliders (block signals to avoid triggering change event)
        self._frame_diff_slider.blockSignals(True)
        self._frame_diff_slider.setValue(int(frame_diff_threshold))
        self._frame_diff_slider.blockSignals(False)
        self._frame_diff_value.setText(f"{frame_diff_threshold:.1f}")

        self._bg_diff_slider.blockSignals(True)
        self._bg_diff_slider.setValue(int(bg_diff_threshold))
        self._bg_diff_slider.blockSignals(False)
        self._bg_diff_value.setText(f"{bg_diff_threshold:.1f}")

        self._min_area_slider.blockSignals(True)
        self._min_area_slider.setValue(min_area)
        self._min_area_slider.blockSignals(False)
        self._min_area_value.setText(str(min_area))

        self._max_area_slider.blockSignals(True)
        self._max_area_slider.setValue(max_area)
        self._max_area_slider.blockSignals(False)
        self._max_area_value.setText(str(max_area))

        self._min_circ_slider.blockSignals(True)
        self._min_circ_slider.setValue(int(min_circularity * 100))
        self._min_circ_slider.blockSignals(False)
        self._min_circ_value.setText(f"{min_circularity:.2f}")

        # Update internal values
        self._mode = mode
        self._frame_diff_threshold = frame_diff_threshold
        self._bg_diff_threshold = bg_diff_threshold
        self._min_area = min_area
        self._max_area = max_area
        self._min_circularity = min_circularity

    @property
    def mode(self) -> Mode:
        """Get current detection mode."""
        return self._mode

    @property
    def frame_diff_threshold(self) -> float:
        """Get frame diff threshold."""
        return self._frame_diff_threshold

    @property
    def bg_diff_threshold(self) -> float:
        """Get BG diff threshold."""
        return self._bg_diff_threshold

    @property
    def min_area(self) -> int:
        """Get min area."""
        return self._min_area

    @property
    def max_area(self) -> int:
        """Get max area."""
        return self._max_area

    @property
    def min_circularity(self) -> float:
        """Get min circularity."""
        return self._min_circularity
