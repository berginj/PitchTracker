"""Glass theme definition for Apple-style glassmorphism UI.

Defines color palette, metrics, and QSS style generators for the
frosted glass aesthetic throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GlassTheme:
    """Dark glassmorphism theme with adaptive intensity modes."""

    name: str = "glass_dark"
    mode: str = "production"  # "production" or "setup"

    # Base colors
    background_dark: str = "#0a0e14"
    background_medium: str = "#12181f"

    # Glass surfaces (mode-dependent opacity set in properties)
    _glass_base_rgb: str = "20, 30, 45"
    _glass_light_rgb: str = "30, 45, 65"

    # Surface overlays
    surface_glass: str = "rgba(255, 255, 255, 0.05)"
    surface_glass_hover: str = "rgba(255, 255, 255, 0.08)"
    surface_glass_active: str = "rgba(255, 255, 255, 0.12)"

    # Borders
    border_glass: str = "rgba(255, 255, 255, 0.1)"
    border_glass_hover: str = "rgba(255, 255, 255, 0.15)"
    border_glass_accent: str = "rgba(100, 200, 255, 0.3)"

    # Accent colors (icy palette)
    accent_primary: str = "#64C8FF"  # Icy blue
    accent_primary_dim: str = "rgba(100, 200, 255, 0.2)"
    accent_success: str = "#4FFFB0"  # Mint green
    accent_success_dim: str = "rgba(79, 255, 176, 0.2)"
    accent_warning: str = "#FFD060"  # Warm amber
    accent_warning_dim: str = "rgba(255, 208, 96, 0.2)"
    accent_error: str = "#FF6B6B"  # Soft red
    accent_error_dim: str = "rgba(255, 107, 107, 0.2)"

    # Text colors
    text_primary: str = "rgba(255, 255, 255, 0.95)"
    text_secondary: str = "rgba(255, 255, 255, 0.6)"
    text_muted: str = "rgba(255, 255, 255, 0.4)"
    text_on_accent: str = "#0a0e14"

    # Metrics
    border_radius: int = 12
    border_radius_small: int = 8
    border_radius_tiny: int = 4
    border_width: int = 1
    padding_large: int = 16
    padding_medium: int = 12
    padding_small: int = 8

    # Font
    font_family: str = "Segoe UI, SF Pro Display, -apple-system, sans-serif"
    font_size_large: int = 14
    font_size_medium: int = 13
    font_size_small: int = 12

    @property
    def glass_opacity(self) -> float:
        """Glass opacity based on mode."""
        return 0.75 if self.mode == "setup" else 0.88

    @property
    def background_glass(self) -> str:
        """Glass background color with mode-dependent opacity."""
        return f"rgba({self._glass_base_rgb}, {self.glass_opacity})"

    @property
    def background_glass_light(self) -> str:
        """Lighter glass layer with mode-dependent opacity."""
        opacity = 0.65 if self.mode == "setup" else 0.80
        return f"rgba({self._glass_light_rgb}, {opacity})"

    def get_app_stylesheet(self) -> str:
        """Generate base application stylesheet."""
        return f"""
            QMainWindow, QDialog, QWidget {{
                background-color: {self.background_dark};
                color: {self.text_primary};
                font-family: {self.font_family};
                font-size: {self.font_size_medium}px;
            }}

            QLabel {{
                color: {self.text_primary};
                background: transparent;
            }}

            QGroupBox {{
                background-color: {self.background_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius}px;
                margin-top: 12px;
                padding: {self.padding_medium}px;
                padding-top: 20px;
                font-weight: bold;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                color: {self.text_secondary};
                background-color: transparent;
            }}

            QMenuBar {{
                background-color: {self.background_glass};
                border-bottom: {self.border_width}px solid {self.border_glass};
                padding: 4px;
            }}

            QMenuBar::item {{
                background: transparent;
                padding: 6px 12px;
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
            }}

            QMenuBar::item:selected {{
                background-color: {self.surface_glass_hover};
            }}

            QMenu {{
                background-color: {self.background_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                padding: 4px;
            }}

            QMenu::item {{
                padding: 8px 24px;
                border-radius: {self.border_radius_tiny}px;
                color: {self.text_primary};
            }}

            QMenu::item:selected {{
                background-color: {self.surface_glass_hover};
            }}

            QMenu::separator {{
                height: 1px;
                background-color: {self.border_glass};
                margin: 4px 8px;
            }}

            QScrollBar:vertical {{
                background-color: transparent;
                width: 12px;
                margin: 4px 2px;
            }}

            QScrollBar::handle:vertical {{
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                min-height: 30px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: rgba(255, 255, 255, 0.25);
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                background-color: transparent;
                height: 12px;
                margin: 2px 4px;
            }}

            QScrollBar::handle:horizontal {{
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                min-width: 30px;
            }}

            QToolTip {{
                background-color: {self.background_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 6px 10px;
            }}
        """

    def get_panel_style(self, intensity: str = "normal") -> str:
        """Generate QSS for glass panels.

        Args:
            intensity: "subtle", "normal", or "bold"
        """
        if intensity == "subtle":
            bg = f"rgba({self._glass_base_rgb}, 0.6)"
            border = "rgba(255, 255, 255, 0.05)"
        elif intensity == "bold":
            bg = f"rgba({self._glass_base_rgb}, 0.9)"
            border = "rgba(255, 255, 255, 0.15)"
        else:  # normal
            bg = self.background_glass
            border = self.border_glass

        return f"""
            background-color: {bg};
            border: {self.border_width}px solid {border};
            border-radius: {self.border_radius}px;
        """

    def get_button_style(self, variant: str = "default") -> str:
        """Generate QSS for glass buttons.

        Args:
            variant: "default", "primary", "success", "danger", "ghost"
        """
        styles = {
            "default": {
                "bg": self.surface_glass,
                "bg_hover": self.surface_glass_hover,
                "bg_pressed": self.surface_glass_active,
                "border": self.border_glass_hover,
                "border_hover": self.border_glass_accent,
                "text": self.text_primary,
            },
            "primary": {
                "bg": self.accent_primary_dim,
                "bg_hover": "rgba(100, 200, 255, 0.3)",
                "bg_pressed": "rgba(100, 200, 255, 0.4)",
                "border": "rgba(100, 200, 255, 0.4)",
                "border_hover": self.accent_primary,
                "text": self.text_primary,
            },
            "success": {
                "bg": self.accent_success_dim,
                "bg_hover": "rgba(79, 255, 176, 0.3)",
                "bg_pressed": "rgba(79, 255, 176, 0.4)",
                "border": "rgba(79, 255, 176, 0.4)",
                "border_hover": self.accent_success,
                "text": self.text_primary,
            },
            "danger": {
                "bg": self.accent_error_dim,
                "bg_hover": "rgba(255, 107, 107, 0.3)",
                "bg_pressed": "rgba(255, 107, 107, 0.4)",
                "border": "rgba(255, 107, 107, 0.4)",
                "border_hover": self.accent_error,
                "text": self.text_primary,
            },
            "ghost": {
                "bg": "transparent",
                "bg_hover": self.surface_glass,
                "bg_pressed": self.surface_glass_hover,
                "border": "transparent",
                "border_hover": self.border_glass,
                "text": self.text_secondary,
            },
        }

        s = styles.get(variant, styles["default"])

        return f"""
            QPushButton {{
                background-color: {s['bg']};
                border: {self.border_width}px solid {s['border']};
                border-radius: {self.border_radius_small}px;
                color: {s['text']};
                padding: {self.padding_small}px {self.padding_medium}px;
                font-size: {self.font_size_medium}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {s['bg_hover']};
                border-color: {s['border_hover']};
            }}
            QPushButton:pressed {{
                background-color: {s['bg_pressed']};
            }}
            QPushButton:disabled {{
                background-color: rgba(255, 255, 255, 0.02);
                border-color: rgba(255, 255, 255, 0.05);
                color: {self.text_muted};
            }}
        """

    def get_input_style(self) -> str:
        """Generate QSS for input fields (QLineEdit, QComboBox, QSpinBox)."""
        return f"""
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: rgba(0, 0, 0, 0.3);
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 6px 10px;
                selection-background-color: {self.accent_primary_dim};
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {self.accent_primary};
            }}
            QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
                background-color: rgba(0, 0, 0, 0.15);
                color: {self.text_muted};
            }}

            QComboBox {{
                background-color: rgba(0, 0, 0, 0.3);
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 6px 10px;
                padding-right: 30px;
            }}
            QComboBox:hover {{
                border-color: {self.border_glass_hover};
            }}
            QComboBox:focus {{
                border-color: {self.accent_primary};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {self.text_secondary};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.background_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                selection-background-color: {self.surface_glass_hover};
                color: {self.text_primary};
                padding: 4px;
            }}
        """

    def get_label_style(self, variant: str = "default") -> str:
        """Generate QSS for styled labels.

        Args:
            variant: "default", "heading", "status", "accent"
        """
        if variant == "heading":
            return f"""
                color: {self.text_primary};
                font-size: {self.font_size_large}px;
                font-weight: bold;
            """
        elif variant == "status":
            return f"""
                background-color: {self.surface_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_secondary};
                padding: {self.padding_small}px {self.padding_medium}px;
            """
        elif variant == "accent":
            return f"""
                color: {self.accent_primary};
                font-weight: 500;
            """
        else:
            return f"""
                color: {self.text_primary};
            """

    def get_status_indicator_style(self, status: str) -> str:
        """Generate QSS for status indicator labels.

        Args:
            status: "success", "warning", "error", "info"
        """
        colors = {
            "success": (self.accent_success, self.accent_success_dim),
            "warning": (self.accent_warning, self.accent_warning_dim),
            "error": (self.accent_error, self.accent_error_dim),
            "info": (self.accent_primary, self.accent_primary_dim),
        }

        text_color, bg_color = colors.get(status, colors["info"])

        return f"""
            background-color: {bg_color};
            border: {self.border_width}px solid {text_color};
            border-radius: {self.border_radius_small}px;
            color: {text_color};
            padding: {self.padding_small}px {self.padding_medium}px;
            font-weight: 500;
        """

    def get_checkbox_style(self) -> str:
        """Generate QSS for checkboxes."""
        return f"""
            QCheckBox {{
                color: {self.text_primary};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: {self.border_width}px solid {self.border_glass_hover};
                border-radius: {self.border_radius_tiny}px;
                background-color: rgba(0, 0, 0, 0.2);
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.accent_primary};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.accent_primary};
                border-color: {self.accent_primary};
            }}
        """

    def get_slider_style(self) -> str:
        """Generate QSS for sliders."""
        return f"""
            QSlider::groove:horizontal {{
                background-color: rgba(255, 255, 255, 0.1);
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background-color: {self.accent_primary};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: #7DD3FF;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {self.accent_primary_dim};
                border-radius: 3px;
            }}
        """

    def get_tab_style(self) -> str:
        """Generate QSS for tab widgets."""
        return f"""
            QTabWidget::pane {{
                background-color: {self.background_glass};
                border: {self.border_width}px solid {self.border_glass};
                border-radius: {self.border_radius}px;
                padding: {self.padding_medium}px;
            }}
            QTabBar::tab {{
                background-color: transparent;
                border: none;
                padding: 10px 20px;
                color: {self.text_secondary};
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {self.accent_primary};
                border-bottom-color: {self.accent_primary};
            }}
            QTabBar::tab:hover:!selected {{
                color: {self.text_primary};
                background-color: {self.surface_glass};
            }}
        """


# Default theme instance
default_theme = GlassTheme()
