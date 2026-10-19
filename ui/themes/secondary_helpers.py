"""Shared scrollable secondary content with an always reachable Close action."""

from PySide6 import QtWidgets

from .dialog_helpers import apply_standard_layout, polish_form_controls


def secondary_content(dialog: QtWidgets.QDialog) -> QtWidgets.QVBoxLayout:
    outer = QtWidgets.QVBoxLayout(dialog)
    apply_standard_layout(outer)
    layout = scrollable_content(outer, f"{dialog.windowTitle()} content")
    close = QtWidgets.QPushButton("Close")
    close.setAccessibleName(f"Close {dialog.windowTitle()}")
    close.clicked.connect(dialog.reject)
    outer.addWidget(close)
    return layout


def scrollable_content(outer: QtWidgets.QVBoxLayout, accessible_name: str) -> QtWidgets.QVBoxLayout:
    """Add a scrollable body; callers keep their command row outside it."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    scroll.setAccessibleName(accessible_name)
    content = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(content)
    apply_standard_layout(layout, margins=(0, 0, 0, 0))
    scroll.setWidget(content)
    outer.addWidget(scroll, 1)
    return layout


def label_form_fields(root: QtWidgets.QWidget) -> None:
    """Give direct QFormLayout fields their visible label as an accessible name."""
    for form in root.findChildren(QtWidgets.QFormLayout):
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QtWidgets.QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QtWidgets.QFormLayout.ItemRole.FieldRole)
            if label_item is None or field_item is None:
                continue
            label, field = label_item.widget(), field_item.widget()
            if isinstance(label, QtWidgets.QLabel) and field is not None:
                if not field.accessibleName():
                    field.setAccessibleName(label.text().replace("&", "").rstrip(":"))
                label.setBuddy(field)
    polish_form_controls(root)
