"""Step 8: Persist stereo calibration profile.

Renders the :class:`~contracts.setup.StereoCalibrationProfile` produced from
setup-time calibration output. All profile formatting lives in the Qt-free
:mod:`ui.setup.persist_profile_view` view-model; this widget only lays the
formatted rows out, so the persistence preview stays unit-testable off-screen.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets

from contracts.setup import StereoCalibrationProfile
from ui.setup.persist_profile_view import build_stereo_profile_from_report, present_persist_preview
from ui.setup.quality_report_view import ReportView
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_status_label,
)

# Presenter tones -> StyleManager status-label tones.
_ROW_VALUE_TONES = {"success", "error", "warning", "info"}


class PersistProfileStep(BaseStep):
    """Step 8: present and persist the stereo calibration profile."""

    def __init__(
        self,
        profile_provider: Optional[Callable[[], Optional[StereoCalibrationProfile]]] = None,
        persist_callback: Optional[Callable[[StereoCalibrationProfile], str]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._profile_provider = profile_provider or build_stereo_profile_from_report
        self._persist_callback = persist_callback
        self._profile: Optional[StereoCalibrationProfile] = None
        self._persisted: bool = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._headline = QtWidgets.QLabel()
        self._headline.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._headline, "info", "Persist profile")
        layout.addWidget(self._headline)

        layout.addWidget(self._build_metrics_group())
        layout.addWidget(self._build_warnings_group())

        button_layout = QtWidgets.QHBoxLayout()
        apply_standard_layout(button_layout, margins=(0, 0, 0, 0), spacing=8)

        persist_button = QtWidgets.QPushButton("Persist Profile")
        persist_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        persist_button.clicked.connect(self._persist)
        self._style_manager.style_button(persist_button, "primary")
        button_layout.addWidget(persist_button)

        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        refresh_button.clicked.connect(self.refresh)
        self._style_manager.style_button(refresh_button, "ghost")
        button_layout.addWidget(refresh_button)
        layout.addLayout(button_layout)

        self._status_label = QtWidgets.QLabel()
        style_status_label(self._status_label, "info", "")
        layout.addWidget(self._status_label)

        layout.addStretch()
        self.setLayout(layout)

    def _build_metrics_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Profile")
        self._metrics_form = QtWidgets.QFormLayout()
        apply_standard_layout(self._metrics_form, margins=(12, 12, 12, 12), spacing=8)
        group.setLayout(self._metrics_form)
        return group

    def _build_warnings_group(self) -> QtWidgets.QGroupBox:
        self._warnings_group = QtWidgets.QGroupBox("Findings")
        self._warnings_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(self._warnings_layout, margins=(12, 12, 12, 12), spacing=8)
        self._warnings_group.setLayout(self._warnings_layout)
        return self._warnings_group

    def get_title(self) -> str:
        return "Persist Profile"

    def get_description(self) -> str:
        return "Persist the current stereo calibration profile for this rig."

    def validate(self) -> tuple[bool, str]:
        return (
            self._profile is not None and self._persisted,
            "" if self._profile is not None and self._persisted else "Persist the calibrated rig profile before continuing.",
        )

    def on_enter(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Rebuild and render the profile preview from the provider."""
        # A refreshed preview may describe different calibration artifacts or
        # cameras. It must be persisted again before it can satisfy the gate.
        self._persisted = False
        self._profile = self._profile_provider()
        style_status_label(self._status_label, "info", "")
        self._render(present_persist_preview(self._profile))

    def _persist(self) -> None:
        # A failed retry must not retain success from an earlier callback.
        self._persisted = False
        if self._profile is None:
            style_status_label(self._status_label, "error", "Nothing to persist.")
            return
        if self._persist_callback is None:
            style_status_label(
                self._status_label,
                "warning",
                "Profile prepared. Saving requires the full setup context.",
            )
            return
        try:
            result = self._persist_callback(self._profile)
        except Exception as exc:
            style_status_label(self._status_label, "error", str(exc))
            return
        self._persisted = True
        style_status_label(self._status_label, "success", f"Saved: {result}")

    def _render(self, view: ReportView) -> None:
        style_status_label(self._headline, view.tone, view.headline)

        _clear_form(self._metrics_form)
        for row in view.rows:
            label = QtWidgets.QLabel(row.label)
            self._style_manager.style_label(label, "muted")
            value = QtWidgets.QLabel(row.value)
            if row.tone in _ROW_VALUE_TONES:
                style_status_label(value, row.tone, row.value)
            self._metrics_form.addRow(label, value)

        _clear_layout(self._warnings_layout)
        if view.warnings:
            for warning in view.warnings:
                notice, _ = build_notice(warning, tone="warning")
                self._warnings_layout.addWidget(notice)
        else:
            notice, _ = build_notice("No findings. The rig looks good.", tone="success")
            self._warnings_layout.addWidget(notice)


def _clear_form(form: QtWidgets.QFormLayout) -> None:
    while form.rowCount():
        form.removeRow(0)


def _clear_layout(layout: QtWidgets.QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
