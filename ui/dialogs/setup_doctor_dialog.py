"""Setup Doctor dialog for fixed-rig production readiness checks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.services.rig_profile import CRITICAL, PASS, WARN, RigProfileService, RigProfileValidation
from configs.settings import AppConfig
from ui.themes import apply_standard_layout, get_style_manager, polish_form_controls


STAGES = (
    "Camera identity",
    "Camera stability",
    "Orientation and software correction",
    "Overlap and toe-in",
    "ChArUco metadata",
    "Calibration capture quality",
    "Full stereo calibration",
    "ROI setup",
    "Runtime dry-run",
)


class SetupDoctorDialog(QtWidgets.QDialog):
    """Non-capturing Setup Doctor status and validation surface."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        config: Optional[AppConfig] = None,
        config_path: Path = Path("configs/default.yaml"),
        backend: str = "uvc",
        left_serial: Optional[str] = None,
        right_serial: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Setup Doctor")
        self.resize(760, 620)
        self._style_manager = get_style_manager()
        self._config = config
        self._config_path = config_path
        self._backend = backend
        self._left_serial = left_serial
        self._right_serial = right_serial
        self._profile_service = RigProfileService(config_path=config_path)
        self._validation: Optional[RigProfileValidation] = None

        self._status_label = QtWidgets.QLabel()
        self._status_label.setWordWrap(True)
        self._profile_label = QtWidgets.QLabel()
        self._profile_label.setWordWrap(True)
        self._details = QtWidgets.QTextEdit()
        self._details.setReadOnly(True)
        self._stage_table = QtWidgets.QTableWidget(0, 3)
        self._stage_table.setHorizontalHeaderLabels(["Stage", "State", "Notes"])
        self._stage_table.horizontalHeader().setStretchLastSection(True)
        self._stage_table.verticalHeader().setVisible(False)

        recheck_button = QtWidgets.QPushButton("Run Checks")
        recheck_button.clicked.connect(self.refresh_status)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        self._style_manager.style_button(recheck_button, "primary")
        self._style_manager.style_button(close_button, "ghost")

        header = QtWidgets.QVBoxLayout()
        apply_standard_layout(header, margins=(0, 0, 0, 0), spacing=8)
        title = QtWidgets.QLabel("Setup Doctor")
        self._style_manager.style_label(title, "pageTitle")
        subtitle = QtWidgets.QLabel("Validate the active fixed rig before coaching sessions.")
        subtitle.setWordWrap(True)
        self._style_manager.style_label(subtitle, "muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addWidget(self._status_label)
        header.addWidget(self._profile_label)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(recheck_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addLayout(header)
        layout.addWidget(self._stage_table, 2)
        layout.addWidget(self._details, 1)
        layout.addLayout(buttons)
        self.setLayout(layout)
        polish_form_controls(self)

        self.refresh_status()

    @property
    def validation(self) -> Optional[RigProfileValidation]:
        return self._validation

    def refresh_status(self) -> None:
        profile = self._profile_service.load_active()
        if profile is None and self._config is not None:
            profile = self._profile_service.legacy_fallback(
                self._config,
                backend=self._backend,
                left_serial=self._left_serial or "",
                right_serial=self._right_serial or "",
            )

        self._validation = self._profile_service.validate_for_runtime(
            profile,
            config=self._config,
            backend=self._backend,
            left_serial=self._left_serial,
            right_serial=self._right_serial,
        )
        state = self._validation.state
        tone = "success" if state == PASS else "warning" if state == WARN else "error"
        self._style_manager.style_status_indicator(self._status_label, tone)
        self._status_label.setText(f"Runtime validation: {state}")

        profile_id = profile.profile_id if profile is not None else "<none>"
        calib_path = self._validation.diagnostics.get("calibration_file", "")
        roi_path = self._validation.diagnostics.get("roi_file", "")
        self._profile_label.setText(f"Profile: {profile_id}\nCalibration: {calib_path}\nROI: {roi_path}")
        self._populate_stages()
        self._populate_details()

    def _populate_stages(self) -> None:
        validation = self._validation
        if validation is None:
            return
        self._stage_table.setRowCount(len(STAGES))
        for row, stage in enumerate(STAGES):
            state, notes = self._stage_state(stage, validation)
            self._stage_table.setItem(row, 0, QtWidgets.QTableWidgetItem(stage))
            self._stage_table.setItem(row, 1, QtWidgets.QTableWidgetItem(state))
            self._stage_table.setItem(row, 2, QtWidgets.QTableWidgetItem(notes))
        self._stage_table.resizeColumnsToContents()

    def _stage_state(self, stage: str, validation: RigProfileValidation) -> tuple[str, str]:
        diagnostics = validation.diagnostics
        if stage == "Full stereo calibration":
            mode = diagnostics.get("calibration_mode", "missing")
            if mode == "missing":
                return WARN, "Legacy scalar stereo fallback will be used."
            if mode == "invalid_matrix_file":
                return CRITICAL, "Matrix file is invalid."
            if mode == "QUICK":
                return WARN, "Quick calibration is diagnostic/fallback-only."
            return PASS, str(diagnostics.get("calibration_quality", "Loaded"))
        if stage == "ROI setup":
            roi_status = diagnostics.get("roi_status", "missing")
            if roi_status.startswith("invalid"):
                return CRITICAL, roi_status
            if roi_status == "missing":
                return WARN, "No ROI file."
            if not diagnostics.get("has_lane_roi") or not diagnostics.get("has_plate_roi"):
                return WARN, "Lane or plate ROI is missing."
            return PASS, "Lane and plate ROI loaded."
        if stage == "Runtime dry-run":
            return validation.state, "Dry-run status from profile validation."
        if validation.is_critical:
            return WARN, "Not yet proven by Setup Doctor."
        return PASS if validation.state == PASS else WARN, "Validated from active profile metadata."

    def _populate_details(self) -> None:
        validation = self._validation
        if validation is None:
            self._details.clear()
            return
        lines: list[str] = []
        if validation.issues:
            lines.append("Critical:")
            lines.extend(f"- {item}" for item in validation.issues)
        if validation.warnings:
            if lines:
                lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in validation.warnings)
        if not lines:
            lines.append("All runtime checks passed.")
        self._details.setPlainText("\n".join(lines))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh_status)


__all__ = ["SetupDoctorDialog", "STAGES"]
