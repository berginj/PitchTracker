"""Shared helpers for dialog, table, and modal presentation."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

from PySide6 import QtCore, QtWidgets

from .style_manager import get_style_manager


INPUT_TYPES: tuple[type[QtWidgets.QWidget], ...] = (
    QtWidgets.QLineEdit,
    QtWidgets.QTextEdit,
    QtWidgets.QPlainTextEdit,
    QtWidgets.QComboBox,
    QtWidgets.QAbstractSpinBox,
    QtWidgets.QDateEdit,
    QtWidgets.QTimeEdit,
    QtWidgets.QDateTimeEdit,
)

# Standardized margin presets (left, top, right, bottom)
MARGINS_SPACIOUS: Tuple[int, int, int, int] = (24, 24, 24, 24)
MARGINS_NORMAL: Tuple[int, int, int, int] = (16, 16, 16, 16)
MARGINS_TIGHT: Tuple[int, int, int, int] = (8, 8, 8, 8)
MARGINS_NONE: Tuple[int, int, int, int] = (0, 0, 0, 0)


def apply_standard_layout(
    layout: QtWidgets.QLayout,
    *,
    margins: Sequence[int] = (24, 24, 24, 24),
    spacing: int = 16,
) -> None:
    """Apply consistent spacing to dialog and step layouts."""
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)


def build_dialog_header(
    title: str,
    subtitle: str | None = None,
    *,
    eyebrow: str | None = None,
) -> QtWidgets.QFrame:
    """Create a standard dialog header card."""
    sm = get_style_manager()

    frame = QtWidgets.QFrame()
    frame.setProperty("surface", "hero")
    sm.polish(frame)

    layout = QtWidgets.QVBoxLayout(frame)
    apply_standard_layout(layout, margins=(20, 18, 20, 18), spacing=6)

    if eyebrow:
        eyebrow_label = QtWidgets.QLabel(eyebrow)
        sm.style_label(eyebrow_label, "eyebrow")
        layout.addWidget(eyebrow_label)

    title_label = QtWidgets.QLabel(title)
    title_label.setWordWrap(True)
    sm.style_label(title_label, "pageTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        sm.style_label(subtitle_label, "muted")
        layout.addWidget(subtitle_label)

    return frame


def build_notice(
    text: str,
    *,
    tone: str = "info",
) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel]:
    """Create a standard in-window notice banner."""
    sm = get_style_manager()

    frame = QtWidgets.QFrame()
    frame.setProperty("notice", tone)
    sm.polish(frame)

    layout = QtWidgets.QHBoxLayout(frame)
    apply_standard_layout(layout, margins=(14, 12, 14, 12), spacing=10)

    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    sm.style_label(label, "muted")
    layout.addWidget(label)

    return frame, label


def set_notice(
    frame: QtWidgets.QFrame,
    label: QtWidgets.QLabel,
    text: str,
    *,
    tone: str = "info",
) -> None:
    """Update a notice banner's text and tone."""
    sm = get_style_manager()
    label.setText(text)
    frame.setProperty("notice", tone)
    sm.polish(frame)


def style_status_label(
    label: QtWidgets.QLabel,
    tone: str,
    text: str | None = None,
) -> None:
    """Apply a standard semantic status style to a label."""
    sm = get_style_manager()
    if text is not None:
        label.setText(text)
    label.setWordWrap(True)
    sm.style_status_indicator(label, tone)


def style_preview_surface(label: QtWidgets.QLabel) -> None:
    """Apply the shared preview surface treatment to a label."""
    sm = get_style_manager()
    label.setProperty("surface", "preview")
    sm.polish(label)


def style_message_panel(widget: QtWidgets.QWidget, tone: str, text: str | None = None) -> None:
    """Apply a shared inset panel style to labels and read-only text widgets."""
    sm = get_style_manager()
    if text is not None and hasattr(widget, "setText"):
        widget.setText(text)
    widget.setProperty("role", "panelMessage")
    widget.setProperty("tone", tone)
    sm.polish(widget)


def style_progress_bar(progress_bar: QtWidgets.QProgressBar, variant: str = "default") -> None:
    """Apply a semantic progress bar variant."""
    sm = get_style_manager()
    progress_bar.setProperty("variant", variant)
    sm.polish(progress_bar)


def style_data_table(
    table: QtWidgets.QTableWidget,
    *,
    sortable: bool = True,
    stretch_last: bool = True,
    alternating_rows: bool = True,
    select_rows: bool = True,
) -> None:
    """Apply a consistent treatment to dense tabular views."""
    table.setAlternatingRowColors(alternating_rows)
    table.setSortingEnabled(sortable)
    table.setSelectionBehavior(
        QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        if select_rows
        else QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems
    )
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.horizontalHeader().setHighlightSections(False)
    table.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)


def configure_message_box(
    box: QtWidgets.QMessageBox,
    *,
    tone: str = "info",
    primary_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (),
    danger_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (),
    ghost_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (),
) -> QtWidgets.QMessageBox:
    """Apply consistent button styling to a message box."""
    sm = get_style_manager()

    tone_to_icon = {
        "info": QtWidgets.QMessageBox.Icon.Information,
        "success": QtWidgets.QMessageBox.Icon.Information,
        "warning": QtWidgets.QMessageBox.Icon.Warning,
        "error": QtWidgets.QMessageBox.Icon.Critical,
        "question": QtWidgets.QMessageBox.Icon.Question,
    }
    box.setIcon(tone_to_icon.get(tone, QtWidgets.QMessageBox.Icon.Information))

    # Style existing buttons after they are created from standard buttons/addButton.
    for button in box.buttons():
        sm.style_button(button, "default")

    for standard_button in primary_buttons:
        button = box.button(standard_button)
        if button is not None:
            sm.style_button(button, "primary")

    for standard_button in danger_buttons:
        button = box.button(standard_button)
        if button is not None:
            sm.style_button(button, "danger")

    for standard_button in ghost_buttons:
        button = box.button(standard_button)
        if button is not None:
            sm.style_button(button, "ghost")

    return box


def show_message_dialog(
    parent: QtWidgets.QWidget | None,
    title: str,
    text: str,
    *,
    tone: str = "info",
    informative_text: str | None = None,
    detailed_text: str | None = None,
    buttons: QtWidgets.QMessageBox.StandardButtons = QtWidgets.QMessageBox.StandardButton.Ok,
    default_button: QtWidgets.QMessageBox.StandardButton | None = QtWidgets.QMessageBox.StandardButton.Ok,
    primary_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (QtWidgets.QMessageBox.StandardButton.Ok,),
    danger_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (),
    ghost_buttons: Iterable[QtWidgets.QMessageBox.StandardButton] = (),
) -> QtWidgets.QMessageBox.StandardButton:
    """Show a standardized message box."""
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    if informative_text:
        box.setInformativeText(informative_text)
    if detailed_text:
        box.setDetailedText(detailed_text)
    box.setStandardButtons(buttons)
    if default_button is not None:
        box.setDefaultButton(default_button)
    configure_message_box(
        box,
        tone=tone,
        primary_buttons=primary_buttons,
        danger_buttons=danger_buttons,
        ghost_buttons=ghost_buttons,
    )
    return QtWidgets.QMessageBox.StandardButton(box.exec())


def ask_confirmation(
    parent: QtWidgets.QWidget | None,
    title: str,
    text: str,
    *,
    tone: str = "question",
    informative_text: str | None = None,
    confirm_button: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.StandardButton.Yes,
    cancel_button: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.StandardButton.No,
    default_button: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.StandardButton.No,
    confirm_variant: str = "primary",
) -> bool:
    """Show a standardized yes/no confirmation dialog."""
    primary_buttons = (confirm_button,) if confirm_variant == "primary" else ()
    danger_buttons = (confirm_button,) if confirm_variant == "danger" else ()
    result = show_message_dialog(
        parent,
        title,
        text,
        tone=tone,
        informative_text=informative_text,
        buttons=confirm_button | cancel_button,
        default_button=default_button,
        primary_buttons=primary_buttons,
        danger_buttons=danger_buttons,
        ghost_buttons=(cancel_button,),
    )
    return result == confirm_button


def show_choice_dialog(
    parent: QtWidgets.QWidget | None,
    title: str,
    text: str,
    *,
    tone: str = "question",
    informative_text: str | None = None,
    choices: Sequence[tuple[str, str, str, QtWidgets.QMessageBox.ButtonRole]] = (),
    default_choice: str | None = None,
) -> str | None:
    """Show a dialog with custom-labeled buttons and return the chosen key."""
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    if informative_text:
        box.setInformativeText(informative_text)
    configure_message_box(box, tone=tone)

    sm = get_style_manager()
    button_map: dict[str, QtWidgets.QAbstractButton] = {}
    for key, label, variant, role in choices:
        button = box.addButton(label, role)
        sm.style_button(button, variant)
        button_map[key] = button
        if key == default_choice:
            box.setDefaultButton(button)

    box.exec()
    clicked = box.clickedButton()
    for key, button in button_map.items():
        if clicked == button:
            return key
    return None


def style_dialog_button_box(
    button_box: QtWidgets.QDialogButtonBox,
    *,
    primary: QtWidgets.QDialogButtonBox.StandardButton | None = None,
    success: Iterable[QtWidgets.QDialogButtonBox.StandardButton] = (),
    danger: Iterable[QtWidgets.QDialogButtonBox.StandardButton] = (),
    ghost: Iterable[QtWidgets.QDialogButtonBox.StandardButton] = (),
) -> None:
    """Apply consistent variants to a dialog button box."""
    sm = get_style_manager()

    for button in button_box.buttons():
        sm.style_button(button, "default")

    if primary is not None:
        button = button_box.button(primary)
        if button is not None:
            sm.style_button(button, "primary")
            button.setDefault(True)

    for standard_button in success:
        button = button_box.button(standard_button)
        if button is not None:
            sm.style_button(button, "success")

    for standard_button in danger:
        button = button_box.button(standard_button)
        if button is not None:
            sm.style_button(button, "danger")

    for standard_button in ghost:
        button = button_box.button(standard_button)
        if button is not None:
            sm.style_button(button, "ghost")


def polish_form_controls(root: QtWidgets.QWidget) -> None:
    """Apply shared input/button styling to common controls in a widget tree."""
    sm = get_style_manager()

    for widget_type in INPUT_TYPES:
        for widget in root.findChildren(widget_type):
            sm.style_input(widget)

    for checkbox in root.findChildren(QtWidgets.QCheckBox):
        sm.style_checkbox(checkbox)

    for slider in root.findChildren(QtWidgets.QSlider):
        sm.style_slider(slider)

    for tabs in root.findChildren(QtWidgets.QTabWidget):
        sm.style_tabs(tabs)

    for button in root.findChildren(QtWidgets.QPushButton):
        if not button.property("variant"):
            sm.style_button(button, "default")


def build_loading_indicator(
    message: str = "Loading...",
    parent: QtWidgets.QWidget | None = None,
) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel, QtWidgets.QProgressBar]:
    """Create a standard loading indicator with progress bar and message.

    Returns:
        Tuple of (frame, label, progress_bar) for controlling visibility and text.
    """
    sm = get_style_manager()

    frame = QtWidgets.QFrame(parent)
    frame.setProperty("surface", "card")
    sm.polish(frame)

    layout = QtWidgets.QVBoxLayout(frame)
    apply_standard_layout(layout, margins=MARGINS_NORMAL, spacing=12)
    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    label = QtWidgets.QLabel(message)
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    sm.style_label(label, "muted")
    layout.addWidget(label)

    progress = QtWidgets.QProgressBar()
    progress.setRange(0, 0)  # Indeterminate
    progress.setTextVisible(False)
    progress.setMaximumWidth(300)
    style_progress_bar(progress, "default")
    layout.addWidget(progress, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

    return frame, label, progress


def build_empty_state(
    title: str,
    subtitle: str = "",
    action_text: str | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> tuple[QtWidgets.QFrame, QtWidgets.QLabel, QtWidgets.QPushButton | None]:
    """Create a standard empty state placeholder.

    Returns:
        Tuple of (frame, subtitle_label, action_button_or_None).
    """
    sm = get_style_manager()

    frame = QtWidgets.QFrame(parent)
    frame.setProperty("surface", "subtle")
    sm.polish(frame)

    layout = QtWidgets.QVBoxLayout(frame)
    apply_standard_layout(layout, margins=MARGINS_SPACIOUS, spacing=12)
    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    title_label = QtWidgets.QLabel(title)
    title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    sm.style_label(title_label, "sectionTitle")
    layout.addWidget(title_label)

    subtitle_label = QtWidgets.QLabel(subtitle)
    subtitle_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    subtitle_label.setWordWrap(True)
    sm.style_label(subtitle_label, "muted")
    layout.addWidget(subtitle_label)

    action_button = None
    if action_text:
        action_button = QtWidgets.QPushButton(action_text)
        action_button.setMinimumHeight(sm.theme.button_height_md)
        sm.style_button(action_button, "primary")
        layout.addWidget(action_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

    return frame, subtitle_label, action_button
