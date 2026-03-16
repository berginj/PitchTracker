"""Glass theme system for Apple-style glassmorphism UI.

This module provides a centralized theme system with:
- GlassTheme: Color palette and style generators
- StyleManager: Singleton for applying and switching themes
- Glass widgets: Drop-in replacements with built-in styling

Usage:
    from ui.themes import get_style_manager, GlassPanel, GlassButton

    # At app startup
    sm = get_style_manager()
    sm.apply_to_app(app)

    # Use glass widgets
    panel = GlassPanel(parent, intensity="normal")
    button = GlassButton("Click me", parent, variant="primary")

    # Switch modes
    sm.set_mode("setup")  # Bolder glass for setup wizard
"""

from .glass_theme import GlassTheme, default_theme
from .style_manager import StyleManager, get_style_manager
from .glass_widgets import (
    GlassPanel,
    GlassGroupBox,
    GlassButton,
    GlassLabel,
    GlassStatusLabel,
    GlassLineEdit,
    GlassComboBox,
    GlassSpinBox,
    GlassDoubleSpinBox,
    GlassDialog,
)

__all__ = [
    # Theme
    "GlassTheme",
    "default_theme",
    # Manager
    "StyleManager",
    "get_style_manager",
    # Widgets
    "GlassPanel",
    "GlassGroupBox",
    "GlassButton",
    "GlassLabel",
    "GlassStatusLabel",
    "GlassLineEdit",
    "GlassComboBox",
    "GlassSpinBox",
    "GlassDoubleSpinBox",
    "GlassDialog",
]
