"""Characterization tests for the public GlassTheme contract."""

from ui.themes.glass_theme import GlassTheme


def test_theme_keeps_public_tokens_and_keyword_overrides():
    theme = GlassTheme(accent_primary="#123456", font_size_medium=17)
    positional_theme = GlassTheme("custom", "setup", "#111111")

    assert theme.background_glass == theme.surface_base
    assert theme.background_glass_light == theme.surface_muted
    assert theme.chart_blue == "#2563EB"
    assert theme.accent_primary == "#123456"
    assert theme.font_size_medium == 17
    assert positional_theme.background_dark == "#111111"


def test_app_stylesheet_uses_current_tokens_and_core_selectors():
    theme = GlassTheme(accent_primary="#123456", surface_base="#ABCDEF")

    stylesheet = theme.get_app_stylesheet()

    assert "QMainWindow, QDialog" in stylesheet
    assert 'QPushButton[variant="primary"]' in stylesheet
    assert "QComboBox QAbstractItemView" in stylesheet
    assert "QLabel[surface=\"preview\"]" in stylesheet
    assert "#123456" in stylesheet
    assert "#ABCDEF" in stylesheet


def test_compatibility_style_helpers_keep_variants():
    theme = GlassTheme()

    assert theme.accent_primary in theme.get_button_style("primary")
    assert theme.surface_elevated in theme.get_panel_style("bold")
    assert theme.input_background in theme.get_input_style()
    assert theme.accent_warning in theme.get_status_indicator_style("warning")
    assert "QCheckBox::indicator:checked" in theme.get_checkbox_style()
    assert "QSlider::handle:horizontal" in theme.get_slider_style()
    assert "QTabBar::tab:selected" in theme.get_tab_style()
