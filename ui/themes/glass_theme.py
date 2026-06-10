"""Centralized UI theme tokens and QSS generators.

The class name is kept for backwards compatibility with the existing theme
layer, but the visual language is now a restrained, light, application-style
system rather than a dark glassmorphism treatment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlassTheme:
    """Neutral light theme with a single restrained accent color."""

    name: str = "pitchtracker_modern"
    mode: str = "production"

    # Base surfaces
    background_dark: str = "#F4F7FB"
    background_medium: str = "#EEF3F8"
    surface_base: str = "#FFFFFF"
    surface_muted: str = "#F8FAFC"
    surface_elevated: str = "#FCFDFE"
    input_background: str = "#FFFFFF"
    preview_surface: str = "#0F172A"

    # Legacy aliases kept for existing widgets that still read theme fields
    surface_glass: str = "#FFFFFF"
    surface_glass_hover: str = "#F8FAFC"
    surface_glass_active: str = "#EEF4FF"
    border_glass: str = "#D7E0EA"
    border_glass_hover: str = "#BAC7D6"
    border_glass_accent: str = "#93B4F2"

    # Accent and states
    accent_primary: str = "#2563EB"
    accent_primary_dim: str = "#E8F0FF"
    accent_success: str = "#15803D"
    accent_success_dim: str = "#EAF7EE"
    accent_warning: str = "#B45309"
    accent_warning_dim: str = "#FFF3E8"
    accent_error: str = "#B42318"
    accent_error_dim: str = "#FDECEC"

    # Text
    text_primary: str = "#0F172A"
    text_secondary: str = "#475569"
    text_muted: str = "#64748B"
    text_on_accent: str = "#FFFFFF"

    # Metrics
    border_radius: int = 16
    border_radius_small: int = 12
    border_radius_tiny: int = 8
    border_width: int = 1
    padding_large: int = 24
    padding_medium: int = 16
    padding_small: int = 10

    # Type
    font_family: str = '"Segoe UI Variable Text", "Segoe UI", "SF Pro Text", sans-serif'
    font_size_large: int = 16
    font_size_medium: int = 13
    font_size_small: int = 12

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
        return f"""
            QMainWindow, QDialog {{
                background-color: {self.background_dark};
            }}

            QWidget {{
                color: {self.text_primary};
                font-family: {self.font_family};
                font-size: {self.font_size_medium}px;
            }}

            QWidget#AppShell,
            QWidget#LauncherShell,
            QWidget#WizardShell,
            QWidget#CoachShell,
            QWidget#ReviewShell {{
                background: transparent;
            }}

            QLabel {{
                background: transparent;
                color: {self.text_primary};
            }}

            QLabel[variant="title"] {{
                font-size: 28px;
                font-weight: 700;
                color: {self.text_primary};
            }}

            QLabel[variant="pageTitle"] {{
                font-size: 22px;
                font-weight: 700;
                color: {self.text_primary};
            }}

            QLabel[variant="sectionTitle"] {{
                font-size: 15px;
                font-weight: 700;
                color: {self.text_primary};
            }}

            QLabel[variant="eyebrow"] {{
                font-size: 11px;
                font-weight: 600;
                color: {self.text_muted};
            }}

            QLabel[variant="muted"] {{
                color: {self.text_secondary};
            }}

            QLabel[variant="accent"] {{
                color: {self.accent_primary};
                font-weight: 600;
            }}

            QLabel[variant="status"] {{
                color: {self.text_secondary};
                background-color: {self.surface_muted};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_tiny}px;
                padding: 6px 10px;
                font-weight: 600;
            }}

            QLabel[variant="status"][status="info"] {{
                color: {self.accent_primary};
                background-color: {self.accent_primary_dim};
                border-color: #C9DBFF;
            }}

            QLabel[variant="status"][status="success"] {{
                color: {self.accent_success};
                background-color: {self.accent_success_dim};
                border-color: #CFE8D7;
            }}

            QLabel[variant="status"][status="warning"] {{
                color: {self.accent_warning};
                background-color: {self.accent_warning_dim};
                border-color: #F3D4B8;
            }}

            QLabel[variant="status"][status="error"] {{
                color: {self.accent_error};
                background-color: {self.accent_error_dim};
                border-color: #F1C7C3;
            }}

            QLabel[role="panelMessage"],
            QTextEdit[role="panelMessage"] {{
                background-color: {self.surface_muted};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 10px 12px;
            }}

            QLabel[role="panelMessage"][tone="info"],
            QTextEdit[role="panelMessage"][tone="info"] {{
                background-color: {self.accent_primary_dim};
                border-color: #C9DBFF;
                color: {self.accent_primary};
            }}

            QLabel[role="panelMessage"][tone="neutral"],
            QTextEdit[role="panelMessage"][tone="neutral"] {{
                background-color: {self.surface_glass};
                border-color: {self.border_glass};
                color: {self.text_muted};
            }}

            QLabel[role="panelMessage"][tone="success"],
            QTextEdit[role="panelMessage"][tone="success"] {{
                background-color: {self.accent_success_dim};
                border-color: #CFE8D7;
                color: {self.accent_success};
            }}

            QLabel[role="panelMessage"][tone="warning"],
            QTextEdit[role="panelMessage"][tone="warning"] {{
                background-color: {self.accent_warning_dim};
                border-color: #F3D4B8;
                color: {self.accent_warning};
            }}

            QLabel[role="panelMessage"][tone="error"],
            QTextEdit[role="panelMessage"][tone="error"] {{
                background-color: {self.accent_error_dim};
                border-color: #F1C7C3;
                color: {self.accent_error};
            }}

            QLabel[variant="metric"] {{
                font-size: 18px;
                font-weight: 700;
                color: {self.text_primary};
            }}

            QLabel[variant="metricAccent"] {{
                font-size: 18px;
                font-weight: 700;
                color: {self.accent_primary};
            }}

            QFrame[surface="card"],
            QWidget[surface="card"],
            QFrame[surface="toolbar"],
            QWidget[surface="toolbar"],
            QFrame[surface="hero"],
            QWidget[surface="hero"],
            QFrame[surface="subtle"],
            QWidget[surface="subtle"],
            QFrame[surface="elevated"],
            QWidget[surface="elevated"] {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius}px;
            }}

            QFrame[surface="toolbar"],
            QWidget[surface="toolbar"] {{
                background-color: {self.surface_muted};
            }}

            QFrame[surface="subtle"],
            QWidget[surface="subtle"] {{
                background-color: {self.surface_muted};
            }}

            QFrame[surface="hero"],
            QWidget[surface="hero"] {{
                background-color: {self.surface_elevated};
            }}

            QFrame[notice="info"] {{
                background-color: {self.accent_primary_dim};
                border: 1px solid #C9DBFF;
                border-radius: {self.border_radius_small}px;
            }}

            QFrame[notice="warning"] {{
                background-color: {self.accent_warning_dim};
                border: 1px solid #F3D4B8;
                border-radius: {self.border_radius_small}px;
            }}

            QFrame[notice="error"] {{
                background-color: {self.accent_error_dim};
                border: 1px solid #F1C7C3;
                border-radius: {self.border_radius_small}px;
            }}

            QGroupBox {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius}px;
                margin-top: 18px;
                padding: {self.padding_medium}px;
                padding-top: 24px;
                font-size: {self.font_size_medium}px;
                font-weight: 600;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                top: 2px;
                padding: 0 6px;
                color: {self.text_secondary};
                background-color: {self.background_dark};
            }}

            QPushButton {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 10px 14px;
                font-size: {self.font_size_medium}px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background-color: {self.surface_glass_hover};
                border-color: {self.border_glass_hover};
            }}

            QPushButton:pressed {{
                background-color: {self.surface_glass_active};
                border-color: {self.border_glass_hover};
            }}

            QPushButton:disabled {{
                background-color: #F3F5F8;
                border-color: #E2E8F0;
                color: #98A2B3;
            }}

            QPushButton[variant="primary"] {{
                background-color: {self.accent_primary};
                border-color: {self.accent_primary};
                color: {self.text_on_accent};
            }}

            QPushButton[variant="primary"]:hover {{
                background-color: #1D4ED8;
                border-color: #1D4ED8;
            }}

            QPushButton[variant="primary"]:pressed {{
                background-color: #1E40AF;
                border-color: #1E40AF;
            }}

            QPushButton[variant="success"] {{
                background-color: {self.accent_success};
                border-color: {self.accent_success};
                color: {self.text_on_accent};
            }}

            QPushButton[variant="success"]:hover {{
                background-color: #166534;
                border-color: #166534;
            }}

            QPushButton[variant="danger"] {{
                background-color: {self.accent_error};
                border-color: {self.accent_error};
                color: {self.text_on_accent};
            }}

            QPushButton[variant="danger"]:hover {{
                background-color: #912018;
                border-color: #912018;
            }}

            QPushButton[variant="ghost"] {{
                background-color: transparent;
                border-color: transparent;
                color: {self.text_secondary};
            }}

            QPushButton[variant="ghost"]:hover {{
                background-color: {self.surface_muted};
                border-color: {self.border_glass};
                color: {self.text_primary};
            }}

            QPushButton[variant="role-card"] {{
                text-align: left;
                padding: 18px 20px;
                min-height: 140px;
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius}px;
            }}

            QPushButton[variant="role-card"]:hover {{
                background-color: {self.surface_muted};
                border-color: {self.border_glass_hover};
            }}

            QPushButton[variant="role-card"][accent="primary"] {{
                border-color: #BED4FF;
            }}

            QPushButton[variant="role-card"][accent="success"] {{
                border-color: #CDE5D3;
            }}

            QLineEdit,
            QTextEdit,
            QPlainTextEdit,
            QSpinBox,
            QDoubleSpinBox,
            QDateEdit,
            QTimeEdit,
            QDateTimeEdit,
            QComboBox {{
                background-color: {self.input_background};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                padding: 9px 12px;
                selection-background-color: {self.accent_primary_dim};
                selection-color: {self.text_primary};
            }}

            QLineEdit:focus,
            QTextEdit:focus,
            QPlainTextEdit:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QDateEdit:focus,
            QTimeEdit:focus,
            QDateTimeEdit:focus,
            QComboBox:focus {{
                border-color: {self.accent_primary};
            }}

            QPushButton:focus,
            QToolButton:focus {{
                border: 2px solid {self.accent_primary};
            }}

            QCheckBox:focus,
            QRadioButton:focus {{
                outline: 2px solid {self.accent_primary};
                outline-offset: 2px;
            }}

            QComboBox {{
                padding-right: 32px;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}

            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {self.text_muted};
                margin-right: 10px;
            }}

            QComboBox QAbstractItemView,
            QListWidget,
            QTreeWidget,
            QTableWidget,
            QTableView {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                color: {self.text_primary};
                alternate-background-color: #FAFCFF;
                outline: none;
                gridline-color: #E7EDF4;
                selection-background-color: {self.accent_primary_dim};
                selection-color: {self.text_primary};
            }}

            QListWidget::item,
            QTreeWidget::item,
            QTableWidget::item,
            QTableView::item {{
                padding: 8px;
            }}

            QListWidget::item:hover,
            QTreeWidget::item:hover,
            QTableWidget::item:hover,
            QTableView::item:hover {{
                background-color: #F7FAFF;
            }}

            QHeaderView::section {{
                background-color: {self.surface_muted};
                color: {self.text_secondary};
                border: none;
                border-bottom: 1px solid {self.border_glass};
                border-right: 1px solid #EDF2F7;
                padding: 10px 12px;
                font-weight: 700;
            }}

            QTabWidget::pane {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius}px;
                top: -1px;
            }}

            QTabBar::tab {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: {self.border_radius_small}px;
                color: {self.text_muted};
                padding: 10px 14px;
                margin-right: 4px;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {self.surface_muted};
                color: {self.text_primary};
            }}

            QTabBar::tab:selected {{
                background-color: {self.surface_base};
                border-color: {self.border_glass};
                color: {self.text_primary};
            }}

            QMenuBar {{
                background-color: {self.surface_base};
                border-bottom: 1px solid {self.border_glass};
                padding: 4px 8px;
            }}

            QMenuBar::item {{
                background: transparent;
                padding: 8px 10px;
                border-radius: {self.border_radius_tiny}px;
                color: {self.text_secondary};
            }}

            QMenuBar::item:selected {{
                background-color: {self.surface_muted};
                color: {self.text_primary};
            }}

            QMenu {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_small}px;
                padding: 6px;
            }}

            QMenu::item {{
                padding: 8px 18px;
                border-radius: {self.border_radius_tiny}px;
            }}

            QMenu::item:selected {{
                background-color: {self.accent_primary_dim};
            }}

            QStatusBar {{
                background-color: {self.surface_base};
                border-top: 1px solid {self.border_glass};
                color: {self.text_secondary};
            }}

            QProgressBar {{
                background-color: #EDF2F7;
                border: 1px solid #DFE7F0;
                border-radius: {self.border_radius_tiny}px;
                color: {self.text_secondary};
                text-align: center;
                min-height: 12px;
            }}

            QProgressBar::chunk {{
                background-color: {self.accent_primary};
                border-radius: {self.border_radius_tiny}px;
            }}

            QProgressBar[variant="success"]::chunk {{
                background-color: {self.accent_success};
            }}

            QProgressBar[variant="warning"]::chunk {{
                background-color: {self.accent_warning};
            }}

            QProgressBar[variant="danger"]::chunk {{
                background-color: {self.accent_error};
            }}

            QCheckBox {{
                color: {self.text_primary};
                spacing: 8px;
            }}

            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {self.border_glass_hover};
                border-radius: 6px;
                background-color: {self.surface_base};
            }}

            QCheckBox::indicator:checked {{
                background-color: {self.accent_primary};
                border-color: {self.accent_primary};
            }}

            QRadioButton {{
                color: {self.text_primary};
                spacing: 8px;
            }}

            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {self.border_glass_hover};
                border-radius: 9px;
                background-color: {self.surface_base};
            }}

            QRadioButton::indicator:checked {{
                border: 5px solid {self.accent_primary};
                background-color: {self.surface_base};
            }}

            QSlider::groove:horizontal {{
                background-color: #E7EDF4;
                height: 6px;
                border-radius: 3px;
            }}

            QSlider::sub-page:horizontal {{
                background-color: {self.accent_primary_dim};
                border-radius: 3px;
            }}

            QSlider::handle:horizontal {{
                background-color: {self.accent_primary};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}

            QScrollBar:vertical {{
                background-color: transparent;
                width: 12px;
                margin: 4px 0 4px 0;
            }}

            QScrollBar::handle:vertical {{
                background-color: #C5D2E0;
                border-radius: 6px;
                min-height: 28px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: #AEBFD2;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical,
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: transparent;
                border: none;
                width: 0px;
                height: 0px;
            }}

            QScrollBar:horizontal {{
                background-color: transparent;
                height: 12px;
                margin: 0 4px 0 4px;
            }}

            QScrollBar::handle:horizontal {{
                background-color: #C5D2E0;
                border-radius: 6px;
                min-width: 28px;
            }}

            QSplitter::handle {{
                background-color: #E4EAF2;
            }}

            QToolTip {{
                background-color: {self.surface_base};
                border: 1px solid {self.border_glass};
                border-radius: {self.border_radius_tiny}px;
                color: {self.text_primary};
                padding: 6px 8px;
            }}

            QLabel[surface="preview"] {{
                background-color: {self.preview_surface};
                color: #94A3B8;
                border: 1px solid #CBD5E1;
                border-radius: {self.border_radius_small}px;
            }}
        """

    def get_panel_style(self, intensity: str = "normal") -> str:
        """Return inline panel styling for compatibility with older widgets."""
        backgrounds = {
            "subtle": self.surface_muted,
            "normal": self.surface_base,
            "bold": self.surface_elevated,
        }
        return (
            f"background-color: {backgrounds.get(intensity, self.surface_base)};"
            f"border: {self.border_width}px solid {self.border_glass};"
            f"border-radius: {self.border_radius}px;"
        )

    def get_button_style(self, variant: str = "default") -> str:
        """Return inline button styling for compatibility with older widgets."""
        variants = {
            "default": (self.surface_base, self.border_glass, self.text_primary),
            "primary": (self.accent_primary, self.accent_primary, self.text_on_accent),
            "success": (self.accent_success, self.accent_success, self.text_on_accent),
            "danger": (self.accent_error, self.accent_error, self.text_on_accent),
            "ghost": ("transparent", "transparent", self.text_secondary),
        }
        bg, border, text = variants.get(variant, variants["default"])
        return (
            f"background-color: {bg};"
            f"border: {self.border_width}px solid {border};"
            f"border-radius: {self.border_radius_small}px;"
            f"color: {text};"
            f"padding: {self.padding_small}px {self.padding_medium}px;"
            f"font-weight: 600;"
        )

    def get_input_style(self) -> str:
        """Return inline input styling for compatibility with older widgets."""
        return (
            f"background-color: {self.input_background};"
            f"border: {self.border_width}px solid {self.border_glass};"
            f"border-radius: {self.border_radius_small}px;"
            f"padding: 9px 12px;"
            f"color: {self.text_primary};"
        )

    def get_label_style(self, variant: str = "default") -> str:
        """Return inline label styling for compatibility with older widgets."""
        if variant == "heading":
            return f"font-size: {self.font_size_large}px; font-weight: 700; color: {self.text_primary};"
        if variant == "status":
            return (
                f"background-color: {self.surface_muted};"
                f"border: {self.border_width}px solid {self.border_glass};"
                f"border-radius: {self.border_radius_tiny}px;"
                f"padding: 6px 10px;"
                f"color: {self.text_secondary};"
            )
        if variant == "accent":
            return f"color: {self.accent_primary}; font-weight: 600;"
        return f"color: {self.text_primary};"

    def get_status_indicator_style(self, status: str) -> str:
        """Return inline status styling for compatibility with older widgets."""
        styles = {
            "success": (self.accent_success_dim, self.accent_success),
            "warning": (self.accent_warning_dim, self.accent_warning),
            "error": (self.accent_error_dim, self.accent_error),
            "info": (self.accent_primary_dim, self.accent_primary),
        }
        bg, color = styles.get(status, styles["info"])
        return (
            f"background-color: {bg};"
            f"border: {self.border_width}px solid {color};"
            f"border-radius: {self.border_radius_tiny}px;"
            f"padding: 6px 10px;"
            f"color: {color};"
            f"font-weight: 600;"
        )

    def get_checkbox_style(self) -> str:
        """Return inline checkbox styling for compatibility."""
        return (
            f"QCheckBox {{ color: {self.text_primary}; spacing: 8px; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {self.border_glass_hover}; "
            f"border-radius: 6px; background-color: {self.surface_base}; }}"
            f"QCheckBox::indicator:checked {{ background-color: {self.accent_primary}; border-color: {self.accent_primary}; }}"
        )

    def get_slider_style(self) -> str:
        """Return inline slider styling for compatibility."""
        return (
            f"QSlider::groove:horizontal {{ background-color: #E7EDF4; height: 6px; border-radius: 3px; }}"
            f"QSlider::sub-page:horizontal {{ background-color: {self.accent_primary_dim}; border-radius: 3px; }}"
            f"QSlider::handle:horizontal {{ background-color: {self.accent_primary}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}"
        )

    def get_tab_style(self) -> str:
        """Return inline tab styling for compatibility."""
        return (
            f"QTabWidget::pane {{ background-color: {self.surface_base}; border: {self.border_width}px solid {self.border_glass}; "
            f"border-radius: {self.border_radius}px; }}"
            f"QTabBar::tab {{ background-color: transparent; border: 1px solid transparent; border-radius: {self.border_radius_small}px; "
            f"padding: 10px 14px; color: {self.text_muted}; }}"
            f"QTabBar::tab:selected {{ background-color: {self.surface_base}; border-color: {self.border_glass}; color: {self.text_primary}; }}"
        )


default_theme = GlassTheme()
