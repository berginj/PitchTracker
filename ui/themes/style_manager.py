"""Style manager for applying glass theme throughout the application.

Provides a singleton manager for consistent theme application and
dynamic mode switching between production and setup modes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple
from weakref import WeakValueDictionary

from PySide6 import QtWidgets, QtCore

from .glass_theme import GlassTheme, default_theme

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton


class StyleManager:
    """Singleton manager for applying glass theme styles.

    Usage:
        # At app startup
        sm = StyleManager.get_instance()
        sm.apply_to_app(app)

        # Style individual widgets
        sm.style_button(my_button, "primary")
        sm.style_panel(my_frame)

        # Switch modes
        sm.set_mode("setup")  # Bolder glass effect
        sm.set_mode("production")  # Subtle glass effect
    """

    _instance: Optional[StyleManager] = None

    @classmethod
    def get_instance(cls) -> StyleManager:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize style manager with default theme."""
        if StyleManager._instance is not None:
            raise RuntimeError("Use StyleManager.get_instance() instead")

        self.theme = GlassTheme()
        self._app: Optional[QApplication] = None

        # Track styled widgets for mode switching (weak refs to avoid memory leaks)
        self._styled_widgets: WeakValueDictionary[int, QWidget] = WeakValueDictionary()
        self._widget_styles: Dict[int, Tuple[str, str]] = {}  # id -> (method, variant)

        # Callbacks for mode change notifications
        self._mode_change_callbacks: List[Callable[[str], None]] = []

    @property
    def mode(self) -> str:
        """Current theme mode."""
        return self.theme.mode

    def set_mode(self, mode: str) -> None:
        """Switch between 'production' and 'setup' modes.

        Args:
            mode: "production" for subtle glass, "setup" for bolder glass
        """
        if mode not in ("production", "setup"):
            raise ValueError(f"Invalid mode: {mode}. Use 'production' or 'setup'.")

        if self.theme.mode == mode:
            return

        self.theme.mode = mode

        # Refresh app stylesheet
        if self._app is not None:
            self._app.setStyleSheet(self.theme.get_app_stylesheet())

        # Refresh all tracked widgets
        self._refresh_all_widgets()

        # Notify callbacks
        for callback in self._mode_change_callbacks:
            try:
                callback(mode)
            except Exception:
                pass

    def on_mode_change(self, callback: Callable[[str], None]) -> None:
        """Register callback for mode changes.

        Args:
            callback: Function called with new mode name
        """
        self._mode_change_callbacks.append(callback)

    def apply_to_app(self, app: QApplication) -> None:
        """Apply base stylesheet to entire application.

        Args:
            app: Qt application instance
        """
        self._app = app
        app.setStyleSheet(self.theme.get_app_stylesheet())

    def style_panel(
        self, widget: QWidget, intensity: str = "normal", track: bool = True
    ) -> None:
        """Apply glass panel style to widget.

        Args:
            widget: Widget to style (typically QFrame or QGroupBox)
            intensity: "subtle", "normal", or "bold"
            track: Whether to track for mode switching
        """
        widget.setStyleSheet(self.theme.get_panel_style(intensity))

        if track:
            self._track_widget(widget, "panel", intensity)

    def style_button(
        self, button: QPushButton, variant: str = "default", track: bool = True
    ) -> None:
        """Apply glass button style.

        Args:
            button: Button to style
            variant: "default", "primary", "success", "danger", "ghost"
            track: Whether to track for mode switching
        """
        button.setStyleSheet(self.theme.get_button_style(variant))

        if track:
            self._track_widget(button, "button", variant)

    def style_input(self, widget: QWidget, track: bool = True) -> None:
        """Apply glass input style.

        Args:
            widget: Input widget (QLineEdit, QComboBox, QSpinBox)
            track: Whether to track for mode switching
        """
        widget.setStyleSheet(self.theme.get_input_style())

        if track:
            self._track_widget(widget, "input", "default")

    def style_label(
        self, label: QtWidgets.QLabel, variant: str = "default", track: bool = True
    ) -> None:
        """Apply styled label style.

        Args:
            label: Label to style
            variant: "default", "heading", "status", "accent"
            track: Whether to track for mode switching
        """
        label.setStyleSheet(self.theme.get_label_style(variant))

        if track:
            self._track_widget(label, "label", variant)

    def style_status_indicator(
        self, label: QtWidgets.QLabel, status: str, track: bool = True
    ) -> None:
        """Apply status indicator style to label.

        Args:
            label: Label to style
            status: "success", "warning", "error", "info"
            track: Whether to track for mode switching
        """
        label.setStyleSheet(self.theme.get_status_indicator_style(status))

        if track:
            self._track_widget(label, "status", status)

    def style_checkbox(self, checkbox: QtWidgets.QCheckBox) -> None:
        """Apply glass checkbox style."""
        checkbox.setStyleSheet(self.theme.get_checkbox_style())

    def style_slider(self, slider: QtWidgets.QSlider) -> None:
        """Apply glass slider style."""
        slider.setStyleSheet(self.theme.get_slider_style())

    def style_tabs(self, tab_widget: QtWidgets.QTabWidget) -> None:
        """Apply glass tab widget style."""
        tab_widget.setStyleSheet(self.theme.get_tab_style())

    def get_color(self, name: str) -> str:
        """Get theme color by name.

        Args:
            name: Color attribute name (e.g., "accent_primary", "text_secondary")

        Returns:
            Color string
        """
        return getattr(self.theme, name, self.theme.text_primary)

    def get_background_dark(self) -> str:
        """Get dark background color."""
        return self.theme.background_dark

    def get_accent_primary(self) -> str:
        """Get primary accent color."""
        return self.theme.accent_primary

    def _track_widget(self, widget: QWidget, method: str, variant: str) -> None:
        """Track widget for mode switching updates."""
        widget_id = id(widget)
        self._styled_widgets[widget_id] = widget
        self._widget_styles[widget_id] = (method, variant)

    def _refresh_all_widgets(self) -> None:
        """Refresh all tracked widgets with current theme."""
        # Clean up dead references
        dead_ids = [
            wid for wid in self._widget_styles if wid not in self._styled_widgets
        ]
        for wid in dead_ids:
            del self._widget_styles[wid]

        # Refresh live widgets
        for widget_id, widget in list(self._styled_widgets.items()):
            if widget_id not in self._widget_styles:
                continue

            method, variant = self._widget_styles[widget_id]

            try:
                if method == "panel":
                    widget.setStyleSheet(self.theme.get_panel_style(variant))
                elif method == "button":
                    widget.setStyleSheet(self.theme.get_button_style(variant))
                elif method == "input":
                    widget.setStyleSheet(self.theme.get_input_style())
                elif method == "label":
                    widget.setStyleSheet(self.theme.get_label_style(variant))
                elif method == "status":
                    widget.setStyleSheet(self.theme.get_status_indicator_style(variant))
            except RuntimeError:
                # Widget was deleted
                pass


def get_style_manager() -> StyleManager:
    """Convenience function to get style manager instance."""
    return StyleManager.get_instance()
