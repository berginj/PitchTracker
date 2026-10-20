"""Workspace preparation uses saved rig identity, without competing camera discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from ui.themes import apply_standard_layout

if TYPE_CHECKING:
    from ui.coaching.dialogs.session_start import SessionStartDialog


def build_prepared_camera_group(dialog, group: QtWidgets.QGroupBox,
                                left_label: QtWidgets.QLabel, right_label: QtWidgets.QLabel) -> QtWidgets.QGroupBox:
    profile = dialog._rig_profile_service.load_active()
    if dialog._backend == "sim" and profile is not None and profile.backend != "sim":
        profile = None
    if profile is not None and profile.left_serial and profile.right_serial:
        left, right = profile.left_serial, profile.right_serial
        description = f"Camera assignment belongs to rig {profile.profile_id}. Change and recheck cameras in Setup."
    elif dialog._backend == "sim":
        left, right = "sim-left", "sim-right"
        description = "Simulator cameras only. No hardware is opened by this dialog. Recording remains explicit."
    else:
        left = right = ""
        description = "No saved camera pair. Cancel preparation, open Setup, and complete the guided rig checks."
    dialog._left_camera_combo.addItem(left or "Complete Setup first", left)
    dialog._right_camera_combo.addItem(right or "Complete Setup first", right)
    dialog._left_camera_combo.setEnabled(False)
    dialog._right_camera_combo.setEnabled(False)
    note = QtWidgets.QLabel(description)
    note.setWordWrap(True)
    layout = QtWidgets.QGridLayout()
    apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
    layout.addWidget(left_label, 0, 0)
    layout.addWidget(dialog._left_camera_combo, 0, 1)
    layout.addWidget(right_label, 1, 0)
    layout.addWidget(dialog._right_camera_combo, 1, 1)
    layout.addWidget(note, 2, 0, 1, 2)
    group.setLayout(layout)
    return group


def fit_preparation_dialog(dialog: SessionStartDialog, layout: QtWidgets.QVBoxLayout,
                           buttons: QtWidgets.QDialogButtonBox) -> QtWidgets.QVBoxLayout:
    """Keep consent/cancel visible while session fields scroll at smaller viewports."""
    layout.removeWidget(buttons)
    content = layout.parentWidget()
    assert content is not None
    scroll = QtWidgets.QScrollArea(dialog)
    scroll.setAccessibleName("Session preparation fields")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setMinimumSize(0, 0)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
    scroll.setWidget(content)
    outer = QtWidgets.QVBoxLayout(dialog)
    apply_standard_layout(outer)
    outer.addWidget(scroll, 1)
    outer.addWidget(buttons)
    prepare = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    prepare.setText("Prepare Session")
    prepare.setAccessibleName("Confirm session preparation")
    prepare.setToolTip("Prepare camera preview only. Start Recording is a separate action.")
    left = dialog._left_camera_combo.currentData()
    right = dialog._right_camera_combo.currentData()
    if not left or not right or left == right:
        prepare.setEnabled(False)
        guidance = "Complete camera assignment and rig checks in Setup. Sessions, Players and Help remain available."
        prepare.setToolTip(guidance)
        prepare.setAccessibleDescription(guidance)
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setAccessibleName("Cancel session preparation")
    return outer
