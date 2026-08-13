"""QSS and compatibility style generation for :mod:`ui.themes.glass_theme`."""

from __future__ import annotations

from typing import Protocol


class ThemeTokens(Protocol):
    background_dark: str
    surface_base: str
    surface_muted: str
    surface_elevated: str
    surface_glass: str
    surface_glass_hover: str
    surface_glass_active: str
    input_background: str
    preview_surface: str
    border_glass: str
    border_glass_hover: str
    accent_primary: str
    accent_primary_dim: str
    accent_success: str
    accent_success_dim: str
    accent_warning: str
    accent_warning_dim: str
    accent_error: str
    accent_error_dim: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    font_family: str
    font_size_hero: int
    font_size_title: int
    font_size_subtitle: int
    font_size_large: int
    font_size_body: int
    font_size_medium: int
    font_size_caption: int
    border_radius: int
    border_radius_small: int
    border_radius_tiny: int
    border_width: int
    padding_medium: int
    padding_small: int


def build_app_stylesheet(theme: ThemeTokens) -> str:
    """Build the global property-driven application stylesheet."""
    return (
        _build_foundation_styles(theme)
        + _build_button_and_input_styles(theme)
        + _build_collection_and_navigation_styles(theme)
        + _build_control_styles(theme)
    )


def _build_foundation_styles(t: ThemeTokens) -> str:
    return f"""
QMainWindow, QDialog {{ background-color: {t.background_dark}; }}
QWidget {{
    color: {t.text_primary};
    font-family: {t.font_family};
    font-size: {t.font_size_medium}px;
}}
QWidget#AppShell, QWidget#LauncherShell, QWidget#WizardShell,
QWidget#CoachShell, QWidget#ReviewShell {{ background: transparent; }}
QLabel {{ background: transparent; color: {t.text_primary}; }}
QLabel[variant="title"] {{
    font-size: {t.font_size_hero}px; font-weight: 700; color: {t.text_primary};
}}
QLabel[variant="pageTitle"] {{
    font-size: {t.font_size_title}px; font-weight: 700; color: {t.text_primary};
}}
QLabel[variant="sectionTitle"] {{
    font-size: {t.font_size_body}px; font-weight: 700; color: {t.text_primary};
}}
QLabel[variant="eyebrow"] {{
    font-size: {t.font_size_caption}px; font-weight: 600; color: {t.text_muted};
}}
QLabel[variant="muted"] {{ color: {t.text_secondary}; }}
QLabel[variant="accent"] {{ color: {t.accent_primary}; font-weight: 600; }}
QLabel[variant="status"] {{
    color: {t.text_secondary}; background-color: {t.surface_muted};
    border: 1px solid {t.border_glass}; border-radius: {t.border_radius_tiny}px;
    padding: 6px 10px; font-weight: 600;
}}
QLabel[variant="status"][status="info"] {{
    color: {t.accent_primary}; background-color: {t.accent_primary_dim}; border-color: #C9DBFF;
}}
QLabel[variant="status"][status="success"] {{
    color: {t.accent_success}; background-color: {t.accent_success_dim}; border-color: #CFE8D7;
}}
QLabel[variant="status"][status="warning"] {{
    color: {t.accent_warning}; background-color: {t.accent_warning_dim}; border-color: #F3D4B8;
}}
QLabel[variant="status"][status="error"] {{
    color: {t.accent_error}; background-color: {t.accent_error_dim}; border-color: #F1C7C3;
}}
QLabel[role="panelMessage"], QTextEdit[role="panelMessage"] {{
    background-color: {t.surface_muted}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_small}px; color: {t.text_primary}; padding: 10px 12px;
}}
QLabel[role="panelMessage"][tone="info"], QTextEdit[role="panelMessage"][tone="info"] {{
    background-color: {t.accent_primary_dim}; border-color: #C9DBFF; color: {t.accent_primary};
}}
QLabel[role="panelMessage"][tone="neutral"], QTextEdit[role="panelMessage"][tone="neutral"] {{
    background-color: {t.surface_glass}; border-color: {t.border_glass}; color: {t.text_muted};
}}
QLabel[role="panelMessage"][tone="success"], QTextEdit[role="panelMessage"][tone="success"] {{
    background-color: {t.accent_success_dim}; border-color: #CFE8D7; color: {t.accent_success};
}}
QLabel[role="panelMessage"][tone="warning"], QTextEdit[role="panelMessage"][tone="warning"] {{
    background-color: {t.accent_warning_dim}; border-color: #F3D4B8; color: {t.accent_warning};
}}
QLabel[role="panelMessage"][tone="error"], QTextEdit[role="panelMessage"][tone="error"] {{
    background-color: {t.accent_error_dim}; border-color: #F1C7C3; color: {t.accent_error};
}}
QLabel[variant="metric"] {{
    font-size: {t.font_size_subtitle}px; font-weight: 700; color: {t.text_primary};
}}
QLabel[variant="metricAccent"] {{
    font-size: {t.font_size_subtitle}px; font-weight: 700; color: {t.accent_primary};
}}
QFrame[surface="card"], QWidget[surface="card"], QFrame[surface="toolbar"],
QWidget[surface="toolbar"], QFrame[surface="hero"], QWidget[surface="hero"],
QFrame[surface="subtle"], QWidget[surface="subtle"], QFrame[surface="elevated"],
QWidget[surface="elevated"] {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius}px;
}}
QFrame[surface="toolbar"], QWidget[surface="toolbar"],
QFrame[surface="subtle"], QWidget[surface="subtle"] {{ background-color: {t.surface_muted}; }}
QFrame[surface="hero"], QWidget[surface="hero"] {{ background-color: {t.surface_elevated}; }}
QFrame[notice="info"] {{
    background-color: {t.accent_primary_dim}; border: 1px solid #C9DBFF;
    border-radius: {t.border_radius_small}px;
}}
QFrame[notice="warning"] {{
    background-color: {t.accent_warning_dim}; border: 1px solid #F3D4B8;
    border-radius: {t.border_radius_small}px;
}}
QFrame[notice="error"] {{
    background-color: {t.accent_error_dim}; border: 1px solid #F1C7C3;
    border-radius: {t.border_radius_small}px;
}}
QGroupBox {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius}px; margin-top: 18px; padding: {t.padding_medium}px;
    padding-top: 24px; font-size: {t.font_size_medium}px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left; left: 14px; top: 2px;
    padding: 0 6px; color: {t.text_secondary}; background-color: {t.background_dark};
}}
"""


def _build_button_and_input_styles(t: ThemeTokens) -> str:
    return f"""
QPushButton {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_small}px; color: {t.text_primary};
    padding: 10px 14px; font-size: {t.font_size_medium}px; font-weight: 600;
}}
QPushButton:hover {{
    background-color: {t.surface_glass_hover}; border-color: {t.border_glass_hover};
}}
QPushButton:pressed {{
    background-color: {t.surface_glass_active}; border-color: {t.border_glass_hover};
}}
QPushButton:disabled {{ background-color: #F3F5F8; border-color: #E2E8F0; color: #98A2B3; }}
QPushButton[variant="primary"] {{
    background-color: {t.accent_primary}; border-color: {t.accent_primary}; color: {t.text_on_accent};
}}
QPushButton[variant="primary"]:hover {{ background-color: #1D4ED8; border-color: #1D4ED8; }}
QPushButton[variant="primary"]:pressed {{ background-color: #1E40AF; border-color: #1E40AF; }}
QPushButton[variant="success"] {{
    background-color: {t.accent_success}; border-color: {t.accent_success}; color: {t.text_on_accent};
}}
QPushButton[variant="success"]:hover {{ background-color: #166534; border-color: #166534; }}
QPushButton[variant="success"]:pressed {{ background-color: #14532D; border-color: #14532D; }}
QPushButton[variant="danger"] {{
    background-color: {t.accent_error}; border-color: {t.accent_error}; color: {t.text_on_accent};
}}
QPushButton[variant="danger"]:hover {{ background-color: #912018; border-color: #912018; }}
QPushButton[variant="danger"]:pressed {{ background-color: #7F1D1D; border-color: #7F1D1D; }}
QPushButton[variant="ghost"] {{
    background-color: transparent; border-color: transparent; color: {t.text_secondary};
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {t.surface_muted}; border-color: {t.border_glass}; color: {t.text_primary};
}}
QPushButton[variant="ghost"]:pressed {{
    background-color: {t.surface_glass_active}; border-color: {t.border_glass_hover};
    color: {t.text_primary};
}}
QPushButton[variant="role-card"] {{
    text-align: left; padding: 18px 20px; min-height: 140px;
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius}px;
}}
QPushButton[variant="role-card"]:hover {{
    background-color: {t.surface_muted}; border-color: {t.border_glass_hover};
}}
QPushButton[variant="role-card"][accent="primary"] {{ border-color: #BED4FF; }}
QPushButton[variant="role-card"][accent="success"] {{ border-color: #CDE5D3; }}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit,
QTimeEdit, QDateTimeEdit, QComboBox {{
    background-color: {t.input_background}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_small}px; color: {t.text_primary}; padding: 9px 12px;
    selection-background-color: {t.accent_primary_dim}; selection-color: {t.text_primary};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus,
QComboBox:focus {{ border-color: {t.accent_primary}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {t.accent_primary}; }}
QCheckBox:focus, QRadioButton:focus {{
    outline: 2px solid {t.accent_primary}; outline-offset: 2px;
}}
QComboBox {{ padding-right: 32px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    image: none; width: 0px; height: 0px; border-left: 5px solid transparent;
    border-right: 5px solid transparent; border-top: 6px solid {t.text_muted};
    margin-right: 10px;
}}
"""


def _build_collection_and_navigation_styles(t: ThemeTokens) -> str:
    return f"""
QComboBox QAbstractItemView, QListWidget, QTreeWidget, QTableWidget, QTableView {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_small}px; color: {t.text_primary};
    alternate-background-color: #FAFCFF; outline: none; gridline-color: #E7EDF4;
    selection-background-color: {t.accent_primary_dim}; selection-color: {t.text_primary};
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item, QTableView::item {{ padding: 8px; }}
QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover,
QTableView::item:hover {{ background-color: #F7FAFF; }}
QHeaderView::section {{
    background-color: {t.surface_muted}; color: {t.text_secondary}; border: none;
    border-bottom: 1px solid {t.border_glass}; border-right: 1px solid #EDF2F7;
    padding: 10px 12px; font-weight: 700;
}}
QTabWidget::pane {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius}px; top: -1px;
}}
QTabBar::tab {{
    background-color: transparent; border: 1px solid transparent;
    border-radius: {t.border_radius_small}px; color: {t.text_muted};
    padding: 10px 14px; margin-right: 4px;
}}
QTabBar::tab:hover:!selected {{ background-color: {t.surface_muted}; color: {t.text_primary}; }}
QTabBar::tab:selected {{
    background-color: {t.surface_base}; border-color: {t.border_glass}; color: {t.text_primary};
}}
QMenuBar {{
    background-color: {t.surface_base}; border-bottom: 1px solid {t.border_glass}; padding: 4px 8px;
}}
QMenuBar::item {{
    background: transparent; padding: 8px 10px; border-radius: {t.border_radius_tiny}px;
    color: {t.text_secondary};
}}
QMenuBar::item:selected {{ background-color: {t.surface_muted}; color: {t.text_primary}; }}
QMenu {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_small}px; padding: 6px;
}}
QMenu::item {{ padding: 8px 18px; border-radius: {t.border_radius_tiny}px; }}
QMenu::item:selected {{ background-color: {t.accent_primary_dim}; }}
QStatusBar {{
    background-color: {t.surface_base}; border-top: 1px solid {t.border_glass};
    color: {t.text_secondary};
}}
"""


def _build_control_styles(t: ThemeTokens) -> str:
    return f"""
QProgressBar {{
    background-color: #EDF2F7; border: 1px solid #DFE7F0;
    border-radius: {t.border_radius_tiny}px; color: {t.text_secondary};
    text-align: center; min-height: 12px;
}}
QProgressBar::chunk {{
    background-color: {t.accent_primary}; border-radius: {t.border_radius_tiny}px;
}}
QProgressBar[variant="success"]::chunk {{ background-color: {t.accent_success}; }}
QProgressBar[variant="warning"]::chunk {{ background-color: {t.accent_warning}; }}
QProgressBar[variant="danger"]::chunk {{ background-color: {t.accent_error}; }}
QCheckBox {{ color: {t.text_primary}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border: 1px solid {t.border_glass_hover};
    border-radius: 6px; background-color: {t.surface_base};
}}
QCheckBox::indicator:checked {{
    background-color: {t.accent_primary}; border-color: {t.accent_primary};
}}
QRadioButton {{ color: {t.text_primary}; spacing: 8px; }}
QRadioButton::indicator {{
    width: 18px; height: 18px; border: 1px solid {t.border_glass_hover};
    border-radius: 9px; background-color: {t.surface_base};
}}
QRadioButton::indicator:checked {{
    border: 5px solid {t.accent_primary}; background-color: {t.surface_base};
}}
QSlider::groove:horizontal {{ background-color: #E7EDF4; height: 6px; border-radius: 3px; }}
QSlider::sub-page:horizontal {{
    background-color: {t.accent_primary_dim}; border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background-color: {t.accent_primary}; width: 16px; height: 16px;
    margin: -5px 0; border-radius: 8px;
}}
QScrollBar:vertical {{
    background-color: transparent; width: 12px; margin: 4px 0 4px 0;
}}
QScrollBar::handle:vertical {{
    background-color: #C5D2E0; border-radius: 6px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background-color: #AEBFD2; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent; border: none; width: 0px; height: 0px;
}}
QScrollBar:horizontal {{
    background-color: transparent; height: 12px; margin: 0 4px 0 4px;
}}
QScrollBar::handle:horizontal {{
    background-color: #C5D2E0; border-radius: 6px; min-width: 28px;
}}
QSplitter::handle {{ background-color: #E4EAF2; }}
QToolTip {{
    background-color: {t.surface_base}; border: 1px solid {t.border_glass};
    border-radius: {t.border_radius_tiny}px; color: {t.text_primary}; padding: 6px 8px;
}}
QLabel[surface="preview"] {{
    background-color: {t.preview_surface}; color: #94A3B8; border: 1px solid #CBD5E1;
    border-radius: {t.border_radius_small}px;
}}
"""


def build_panel_style(t: ThemeTokens, intensity: str) -> str:
    backgrounds = {
        "subtle": t.surface_muted,
        "normal": t.surface_base,
        "bold": t.surface_elevated,
    }
    return (
        f"background-color: {backgrounds.get(intensity, t.surface_base)};"
        f"border: {t.border_width}px solid {t.border_glass};"
        f"border-radius: {t.border_radius}px;"
    )


def build_button_style(t: ThemeTokens, variant: str) -> str:
    variants = {
        "default": (t.surface_base, t.border_glass, t.text_primary),
        "primary": (t.accent_primary, t.accent_primary, t.text_on_accent),
        "success": (t.accent_success, t.accent_success, t.text_on_accent),
        "danger": (t.accent_error, t.accent_error, t.text_on_accent),
        "ghost": ("transparent", "transparent", t.text_secondary),
    }
    bg, border, text = variants.get(variant, variants["default"])
    return (
        f"background-color: {bg};border: {t.border_width}px solid {border};"
        f"border-radius: {t.border_radius_small}px;color: {text};"
        f"padding: {t.padding_small}px {t.padding_medium}px;font-weight: 600;"
    )


def build_input_style(t: ThemeTokens) -> str:
    return (
        f"background-color: {t.input_background};border: {t.border_width}px solid {t.border_glass};"
        f"border-radius: {t.border_radius_small}px;padding: 9px 12px;color: {t.text_primary};"
    )


def build_label_style(t: ThemeTokens, variant: str) -> str:
    if variant == "heading":
        return f"font-size: {t.font_size_large}px; font-weight: 700; color: {t.text_primary};"
    if variant == "status":
        return (
            f"background-color: {t.surface_muted};border: {t.border_width}px solid {t.border_glass};"
            f"border-radius: {t.border_radius_tiny}px;padding: 6px 10px;color: {t.text_secondary};"
        )
    if variant == "accent":
        return f"color: {t.accent_primary}; font-weight: 600;"
    return f"color: {t.text_primary};"


def build_status_indicator_style(t: ThemeTokens, status: str) -> str:
    styles = {
        "success": (t.accent_success_dim, t.accent_success),
        "warning": (t.accent_warning_dim, t.accent_warning),
        "error": (t.accent_error_dim, t.accent_error),
        "info": (t.accent_primary_dim, t.accent_primary),
    }
    bg, color = styles.get(status, styles["info"])
    return (
        f"background-color: {bg};border: {t.border_width}px solid {color};"
        f"border-radius: {t.border_radius_tiny}px;padding: 6px 10px;"
        f"color: {color};font-weight: 600;"
    )


def build_checkbox_style(t: ThemeTokens) -> str:
    return (
        f"QCheckBox {{ color: {t.text_primary}; spacing: 8px; }}"
        f"QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {t.border_glass_hover}; "
        f"border-radius: 6px; background-color: {t.surface_base}; }}"
        f"QCheckBox::indicator:checked {{ background-color: {t.accent_primary}; "
        f"border-color: {t.accent_primary}; }}"
    )


def build_slider_style(t: ThemeTokens) -> str:
    return (
        "QSlider::groove:horizontal { background-color: #E7EDF4; height: 6px; border-radius: 3px; }"
        f"QSlider::sub-page:horizontal {{ background-color: {t.accent_primary_dim}; border-radius: 3px; }}"
        f"QSlider::handle:horizontal {{ background-color: {t.accent_primary}; width: 16px; "
        "height: 16px; margin: -5px 0; border-radius: 8px; }"
    )


def build_tab_style(t: ThemeTokens) -> str:
    return (
        f"QTabWidget::pane {{ background-color: {t.surface_base}; border: {t.border_width}px solid "
        f"{t.border_glass}; border-radius: {t.border_radius}px; }}"
        "QTabBar::tab { background-color: transparent; border: 1px solid transparent; "
        f"border-radius: {t.border_radius_small}px; padding: 10px 14px; color: {t.text_muted}; }}"
        f"QTabBar::tab:selected {{ background-color: {t.surface_base}; border-color: {t.border_glass}; "
        f"color: {t.text_primary}; }}"
    )
