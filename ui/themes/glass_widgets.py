"""Glass-styled base widgets for consistent UI appearance.

Provides drop-in replacements for common Qt widgets with built-in
glass theme styling.
"""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from .dialog_helpers import apply_standard_layout
from .style_manager import get_style_manager


class GlassPanel(QtWidgets.QFrame):
    """Glass panel with frosted background effect.

    Use as a container for grouping related content with a
    semi-transparent glass appearance.
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        intensity: str = "normal",
    ):
        """Initialize glass panel.

        Args:
            parent: Parent widget
            intensity: "subtle", "normal", or "bold"
        """
        super().__init__(parent)
        self._intensity = intensity
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass panel style."""
        sm = get_style_manager()
        sm.style_panel(self, self._intensity)

    def set_intensity(self, intensity: str) -> None:
        """Change panel intensity.

        Args:
            intensity: "subtle", "normal", or "bold"
        """
        self._intensity = intensity
        self._apply_style()


class GlassGroupBox(QtWidgets.QGroupBox):
    """Glass-styled group box with title.

    Use for logically grouping related controls with a labeled border.
    """

    def __init__(
        self,
        title: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize glass group box.

        Args:
            title: Group box title
            parent: Parent widget
        """
        super().__init__(title, parent)
        # Styling handled by app-wide stylesheet


class GlassButton(QtWidgets.QPushButton):
    """Glass-styled button with hover effects.

    Variants:
        - default: Subtle glass button
        - primary: Blue accent (primary actions)
        - success: Green accent (confirm, start)
        - danger: Red accent (delete, stop)
        - ghost: Transparent until hover
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
        variant: str = "default",
    ):
        """Initialize glass button.

        Args:
            text: Button text
            parent: Parent widget
            variant: "default", "primary", "success", "danger", "ghost"
        """
        super().__init__(text, parent)
        self._variant = variant
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass button style."""
        sm = get_style_manager()
        sm.style_button(self, self._variant)

    def set_variant(self, variant: str) -> None:
        """Change button variant.

        Args:
            variant: "default", "primary", "success", "danger", "ghost"
        """
        self._variant = variant
        self._apply_style()


class GlassLabel(QtWidgets.QLabel):
    """Glass-styled label with optional status indicator styling.

    Variants:
        - default: Standard text
        - heading: Bold, larger text
        - status: Bordered status box
        - accent: Accent-colored text
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
        variant: str = "default",
    ):
        """Initialize glass label.

        Args:
            text: Label text
            parent: Parent widget
            variant: "default", "heading", "status", "accent"
        """
        super().__init__(text, parent)
        self._variant = variant
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass label style."""
        sm = get_style_manager()
        sm.style_label(self, self._variant)

    def set_variant(self, variant: str) -> None:
        """Change label variant.

        Args:
            variant: "default", "heading", "status", "accent"
        """
        self._variant = variant
        self._apply_style()


class GlassStatusLabel(QtWidgets.QLabel):
    """Status indicator label with colored background.

    Status types:
        - success: Green (good, complete)
        - warning: Amber (caution, in progress)
        - error: Red (problem, stopped)
        - info: Blue (neutral information)
    """

    def __init__(
        self,
        text: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
        status: str = "info",
    ):
        """Initialize status label.

        Args:
            text: Label text
            parent: Parent widget
            status: "success", "warning", "error", "info"
        """
        super().__init__(text, parent)
        self._status = status
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply status indicator style."""
        sm = get_style_manager()
        sm.style_status_indicator(self, self._status)

    def set_status(self, status: str) -> None:
        """Change status type.

        Args:
            status: "success", "warning", "error", "info"
        """
        self._status = status
        self._apply_style()


class GlassLineEdit(QtWidgets.QLineEdit):
    """Glass-styled line edit with focus effects."""

    def __init__(
        self,
        text: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize glass line edit.

        Args:
            text: Initial text
            parent: Parent widget
        """
        super().__init__(text, parent)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass input style."""
        sm = get_style_manager()
        sm.style_input(self)


class GlassComboBox(QtWidgets.QComboBox):
    """Glass-styled combo box with dropdown."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize glass combo box.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass input style."""
        sm = get_style_manager()
        sm.style_input(self)


class GlassSpinBox(QtWidgets.QSpinBox):
    """Glass-styled spin box."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize glass spin box.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass input style."""
        sm = get_style_manager()
        sm.style_input(self)


class GlassDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """Glass-styled double spin box."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize glass double spin box.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply glass input style."""
        sm = get_style_manager()
        sm.style_input(self)


class GlassDialog(QtWidgets.QDialog):
    """Glass-styled dialog base class.

    Provides consistent dark background and glass panel styling
    for all application dialogs.
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        title: str = "",
    ):
        """Initialize glass dialog.

        Args:
            parent: Parent widget
            title: Dialog window title
        """
        super().__init__(parent)
        self._style_manager = get_style_manager()

        if title:
            self.setWindowTitle(title)

        # Apply dark background via property system
        self.setProperty("surface", "dialog")
        self._style_manager.polish(self)

    def polish_controls(self) -> None:
        """Polish all form controls in the dialog.

        Call this after building the dialog UI with input widgets.
        """
        self._style_manager.polish_form_controls(self)

    def create_button_box(
        self,
        ok_text: str = "OK",
        cancel_text: str = "Cancel",
        ok_variant: str = "primary",
    ) -> QtWidgets.QHBoxLayout:
        """Create standard dialog button layout.

        Args:
            ok_text: Text for OK/confirm button
            cancel_text: Text for cancel button
            ok_variant: Button variant for OK button

        Returns:
            Layout containing Cancel and OK buttons
        """
        layout = QtWidgets.QHBoxLayout()
        apply_standard_layout(layout)
        layout.addStretch()

        self.cancel_button = GlassButton(cancel_text, variant="ghost")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

        self.ok_button = GlassButton(ok_text, variant=ok_variant)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        layout.addWidget(self.ok_button)

        return layout
