"""Theme manager for applying the centralized application design system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple
from weakref import WeakValueDictionary

from PySide6 import QtCore, QtWidgets

from .glass_theme import GlassTheme

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget


class StyleManager:
    """Singleton manager for the app's property-driven theme system."""

    _instance: Optional["StyleManager"] = None

    @classmethod
    def get_instance(cls) -> "StyleManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        if StyleManager._instance is not None:
            raise RuntimeError("Use StyleManager.get_instance() instead")

        self.theme = GlassTheme()
        self._app: Optional[QApplication] = None
        self._styled_widgets: WeakValueDictionary[int, QWidget] = WeakValueDictionary()
        self._widget_styles: Dict[int, Tuple[str, str]] = {}
        self._mode_change_callbacks: List[Callable[[str], None]] = []

    @property
    def mode(self) -> str:
        return self.theme.mode

    def set_mode(self, mode: str) -> None:
        if mode not in ("production", "setup"):
            raise ValueError(f"Invalid mode: {mode}. Use 'production' or 'setup'.")
        if self.theme.mode == mode:
            return

        self.theme.mode = mode
        if self._app is not None:
            self._app.setStyleSheet(self.theme.get_app_stylesheet())
        self._refresh_all_widgets()

        for callback in self._mode_change_callbacks:
            try:
                callback(mode)
            except Exception:
                pass

    def on_mode_change(self, callback: Callable[[str], None]) -> None:
        self._mode_change_callbacks.append(callback)

    def apply_to_app(self, app: QApplication) -> None:
        self._app = app
        app.setStyle("Fusion")
        if hasattr(app, "font") and hasattr(app, "setFont"):
            font = app.font()
            font.setFamily("Segoe UI Variable Text")
            font.setPointSize(self.theme.font_size_medium)
            app.setFont(font)
        if hasattr(app, "setStyleSheet"):
            app.setStyleSheet(self.theme.get_app_stylesheet())

    def polish(self, widget: QtWidgets.QWidget) -> None:
        """Re-polish a widget after dynamic property changes."""
        style = widget.style()
        if style is None:
            return
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def style_panel(self, widget: QWidget, intensity: str = "normal", track: bool = True) -> None:
        surface_map = {
            "subtle": "subtle",
            "normal": "card",
            "bold": "elevated",
        }
        widget.setProperty("surface", surface_map.get(intensity, "card"))
        self.polish(widget)
        if track:
            self._track_widget(widget, "panel", intensity)

    def style_button(self, button: QPushButton, variant: str = "default", track: bool = True) -> None:
        button.setProperty("variant", variant)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.polish(button)
        if track:
            self._track_widget(button, "button", variant)

    def style_input(self, widget: QWidget, track: bool = True) -> None:
        widget.setProperty("inputRole", "default")
        if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QAbstractSpinBox)):
            widget.setMinimumHeight(max(widget.minimumHeight(), 36))
        self.polish(widget)
        if track:
            self._track_widget(widget, "input", "default")

    def style_label(self, label: QtWidgets.QLabel, variant: str = "default", track: bool = True) -> None:
        label.setProperty("variant", variant)
        self.polish(label)
        if track:
            self._track_widget(label, "label", variant)

    def style_status_indicator(
        self,
        label: QtWidgets.QLabel,
        status: str,
        track: bool = True,
    ) -> None:
        label.setProperty("variant", "status")
        label.setProperty("status", status)
        self.polish(label)
        if track:
            self._track_widget(label, "status", status)

    def style_checkbox(self, checkbox: QtWidgets.QCheckBox) -> None:
        checkbox.setProperty("controlRole", "checkbox")
        self.polish(checkbox)

    def style_slider(self, slider: QtWidgets.QSlider) -> None:
        slider.setProperty("controlRole", "slider")
        self.polish(slider)

    def style_tabs(self, tab_widget: QtWidgets.QTabWidget) -> None:
        tab_widget.setProperty("controlRole", "tabs")
        self.polish(tab_widget)

    def get_color(self, name: str) -> str:
        return getattr(self.theme, name, self.theme.text_primary)

    def get_background_dark(self) -> str:
        return self.theme.background_dark

    def get_accent_primary(self) -> str:
        return self.theme.accent_primary

    def _track_widget(self, widget: QWidget, method: str, variant: str) -> None:
        widget_id = id(widget)
        self._styled_widgets[widget_id] = widget
        self._widget_styles[widget_id] = (method, variant)

    def _refresh_all_widgets(self) -> None:
        dead_ids = [widget_id for widget_id in self._widget_styles if widget_id not in self._styled_widgets]
        for widget_id in dead_ids:
            del self._widget_styles[widget_id]

        for widget_id, widget in list(self._styled_widgets.items()):
            if widget_id not in self._widget_styles:
                continue

            method, variant = self._widget_styles[widget_id]
            try:
                if method == "panel":
                    self.style_panel(widget, variant, track=False)
                elif method == "button":
                    self.style_button(widget, variant, track=False)
                elif method == "input":
                    self.style_input(widget, track=False)
                elif method == "label":
                    self.style_label(widget, variant, track=False)
                elif method == "status":
                    self.style_status_indicator(widget, variant, track=False)
            except RuntimeError:
                pass


def get_style_manager() -> StyleManager:
    """Convenience accessor for the singleton style manager."""
    return StyleManager.get_instance()
