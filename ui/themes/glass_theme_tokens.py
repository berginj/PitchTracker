"""Public token definitions for the PitchTracker application theme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlassThemeTokens:
    """Stable color, typography, and spacing tokens used by UI code."""

    name: str = "pitchtracker_modern"
    mode: str = "production"

    background_dark: str = "#F4F7FB"
    background_medium: str = "#EEF3F8"
    surface_base: str = "#FFFFFF"
    surface_muted: str = "#F8FAFC"
    surface_elevated: str = "#FCFDFE"
    input_background: str = "#FFFFFF"
    preview_surface: str = "#0F172A"

    surface_glass: str = "#FFFFFF"
    surface_glass_hover: str = "#F8FAFC"
    surface_glass_active: str = "#EEF4FF"
    border_glass: str = "#D7E0EA"
    border_glass_hover: str = "#BAC7D6"
    border_glass_accent: str = "#93B4F2"

    accent_primary: str = "#2563EB"
    accent_primary_dim: str = "#E8F0FF"
    accent_success: str = "#15803D"
    accent_success_dim: str = "#EAF7EE"
    accent_warning: str = "#B45309"
    accent_warning_dim: str = "#FFF3E8"
    accent_error: str = "#B42318"
    accent_error_dim: str = "#FDECEC"

    text_primary: str = "#0F172A"
    text_secondary: str = "#475569"
    text_muted: str = "#64748B"
    text_on_accent: str = "#FFFFFF"

    border_radius: int = 16
    border_radius_small: int = 12
    border_radius_tiny: int = 8
    border_width: int = 1
    padding_large: int = 24
    padding_medium: int = 16
    padding_small: int = 10

    font_family: str = '"Segoe UI Variable Text", "Segoe UI", "SF Pro Text", sans-serif'
    font_size_hero: int = 28
    font_size_title: int = 22
    font_size_subtitle: int = 18
    font_size_large: int = 16
    font_size_body: int = 15
    font_size_medium: int = 13
    font_size_small: int = 12
    font_size_caption: int = 11

    button_height_lg: int = 48
    button_height_md: int = 40
    button_height_sm: int = 32

    margin_spacious: int = 24
    margin_normal: int = 16
    margin_tight: int = 8

    chart_blue: str = "#2563EB"
    chart_green: str = "#15803D"
    chart_orange: str = "#B45309"
    chart_red: str = "#B42318"
    chart_background: str = "#F8FAFC"

    dialog_width_large: int = 900
    dialog_height_large: int = 700
