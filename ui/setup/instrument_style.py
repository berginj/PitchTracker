"""Scoped setup styling; the rest of the desktop retains the shared theme."""

from dataclasses import replace

from ui.themes import get_style_manager


def instrument_stylesheet(*, dark: bool = False) -> str:
    t = replace(get_style_manager().theme, font_size_medium=14, border_radius=8,
                border_radius_small=6, border_radius_tiny=5)
    if dark:
        t = replace(
            t, background_dark="#111821", background_medium="#15202B", surface_base="#19222B",
            surface_muted="#202C39", surface_elevated="#22323E", input_background="#111A24",
            surface_glass="#19222B", surface_glass_hover="#263748", surface_glass_active="#203753",
            border_glass="#364556", border_glass_hover="#52677D", border_glass_accent="#80A8FF",
            accent_primary="#80A8FF", accent_primary_dim="#203753", text_on_accent="#0B1420",
            accent_success="#64CB8B", accent_success_dim="#183E2D", accent_warning="#F2C26B",
            accent_warning_dim="#42311B", accent_error="#FFA79F", accent_error_dim="#42212A",
            text_primary="#ECF2FA", text_secondary="#BBC9DA", text_muted="#9CAEC1",
        )
    hover = "#A9C4FF" if dark else "#1D4ED8"
    pressed = "#6B9CF5" if dark else "#1E40AF"
    return t.get_app_stylesheet() + f"""
QWidget#StereoWizardShell {{ background: {t.background_dark}; }}
QScrollArea#SetupScroll, QWidget#SetupViewport, QWidget#SetupStage,
QStackedWidget#SetupStageStack {{ background: {t.background_dark}; }}
QFrame#SetupChrome, QWidget#SetupRail {{ background: {t.surface_base}; }}
QFrame#SetupChrome {{ border-bottom: 1px solid {t.border_glass}; }}
QWidget#SetupRail {{ border-right: 1px solid {t.border_glass}; }}
QLabel#SetupBrand {{ font-size: 20px; font-weight: 700; }}
QLabel#SetupContext {{ color: {t.text_muted}; font-size: 12px; }}
QLabel[role="setupHeadline"] {{ font-size: 28px; font-weight: 700; }}
QLabel[role="setupStage"] {{
    padding: 12px 10px; border: none; border-radius: 6px;
    color: {t.text_secondary}; background: transparent; font-size: 13px;
}}
QLabel[role="setupStage"][stepState="current"] {{
    background: {t.accent_primary_dim}; color: {t.accent_primary}; font-weight: 700;
}}
QLabel[role="setupStage"][stepState="complete"] {{ color: {t.accent_success}; }}
QLabel#SetupPreview {{
    background: {t.preview_surface}; color: #BBC9DA; border-radius: 8px; padding: 0;
}}
QLabel#SetupModeSummary {{
    color: {t.text_secondary}; padding: 12px 0; border-bottom: 1px solid {t.border_glass};
}}
QToolButton#SetupDisclosure {{
    background: transparent; border: none; color: {t.text_primary};
    padding: 8px 0; font-size: 13px;
}}
QToolButton#SetupDisclosure:focus {{ border: 2px solid {t.accent_primary}; border-radius: 4px; }}
QFrame#SetupCollection {{
    background: {t.surface_base}; border: 1px solid {t.border_glass}; border-radius: 8px;
}}
QProgressBar#SetupPairProgress {{
    background: {t.border_glass}; border: none; border-radius: 3px; min-height: 6px; max-height: 6px;
}}
QProgressBar#SetupPairProgress::chunk {{ background: {t.accent_primary}; border-radius: 3px; }}
QWidget#StereoWizardShell QPushButton {{ border-radius: 6px; min-height: 20px; }}
QWidget#StereoWizardShell QPushButton[variant="primary"]:hover {{
    background: {hover}; border-color: {hover}; color: {t.text_on_accent};
}}
QWidget#StereoWizardShell QPushButton[variant="primary"]:pressed {{
    background: {pressed}; border-color: {pressed}; color: {t.text_on_accent};
}}
QWidget#StereoWizardShell QPushButton:disabled {{
    background: {t.surface_muted}; border-color: {t.border_glass}; color: {t.text_muted};
}}
QWidget#StereoWizardShell QComboBox, QWidget#StereoWizardShell QAbstractSpinBox {{
    border-radius: 6px; min-height: 30px;
}}
QWidget#StereoWizardShell QLabel[variant="status"] {{
    border: none; border-radius: 5px; padding: 5px 8px;
}}
"""
