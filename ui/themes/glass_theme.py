"""Centralized UI theme tokens and QSS generators.

The class name remains stable for compatibility while token ownership and style
generation live in focused collaborators.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtGui

from .glass_theme_styles import (
    build_app_stylesheet,
    build_button_style,
    build_checkbox_style,
    build_input_style,
    build_label_style,
    build_panel_style,
    build_slider_style,
    build_status_indicator_style,
    build_tab_style,
)
from .glass_theme_tokens import GlassThemeTokens


@dataclass
class GlassTheme(GlassThemeTokens):
    """Neutral light theme with a single restrained accent color."""

    @property
    def background_glass(self) -> str:
        """Compatibility alias for panel background styling."""
        return self.surface_base

    @property
    def background_glass_light(self) -> str:
        """Compatibility alias for lighter panel styling."""
        return self.surface_muted

    def get_app_stylesheet(self) -> str:
        """Generate the global application stylesheet."""
        return build_app_stylesheet(self)

    @property
    def surface_secondary(self) -> str:
        return self.surface_muted

    @property
    def border(self) -> str:
        return self.border_glass

    @property
    def text(self) -> str:
        return self.text_primary

    @property
    def accent_danger(self) -> str:
        return self.accent_error

    @property
    def accent_info(self) -> str:
        return self.accent_primary

    def get_font(
        self,
        size: int | str | None = None,
        bold: bool = False,
        weight: str | None = None,
    ) -> QtGui.QFont:
        """Build a font from the shared family and size tokens."""
        font = QtGui.QFont("Segoe UI Variable Text")
        named_sizes = {
            "caption": self.font_size_caption,
            "body": self.font_size_body,
            "heading": self.font_size_subtitle,
            "title": self.font_size_title,
        }
        point_size = named_sizes.get(size, self.font_size_medium) if isinstance(size, str) else size
        font.setPointSize(point_size if point_size is not None else self.font_size_medium)
        font.setBold(bold or weight == "bold")
        return font

    def get_panel_style(self, intensity: str = "normal") -> str:
        """Return inline panel styling for compatibility with older widgets."""
        return build_panel_style(self, intensity)

    def get_button_style(self, variant: str = "default") -> str:
        """Return inline button styling for compatibility with older widgets."""
        return build_button_style(self, variant)

    def get_input_style(self) -> str:
        """Return inline input styling for compatibility with older widgets."""
        return build_input_style(self)

    def get_label_style(self, variant: str = "default") -> str:
        """Return inline label styling for compatibility with older widgets."""
        return build_label_style(self, variant)

    def get_status_indicator_style(self, status: str) -> str:
        """Return inline status styling for compatibility with older widgets."""
        return build_status_indicator_style(self, status)

    def get_checkbox_style(self) -> str:
        """Return inline checkbox styling for compatibility."""
        return build_checkbox_style(self)

    def get_slider_style(self) -> str:
        """Return inline slider styling for compatibility."""
        return build_slider_style(self)

    def get_tab_style(self) -> str:
        """Return inline tab styling for compatibility."""
        return build_tab_style(self)


default_theme = GlassTheme()
