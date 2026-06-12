"""Trajectory comparison diagnostics for review mode."""

from __future__ import annotations

from typing import Any, Optional

from PySide6 import QtWidgets

from ui.themes import get_style_manager


class TrajectoryDiagnosticsPanel(QtWidgets.QWidget):
    """Compact selected-pitch trajectory diagnostics."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()
        self.clear()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("Trajectory Diagnostics")
        self._style_manager.style_label(title, "sectionTitle")
        layout.addWidget(title)

        self._mode_label = QtWidgets.QLabel()
        self._fallback_label = QtWidgets.QLabel()
        self._ray_rmse_label = QtWidgets.QLabel()
        self._time_offset_label = QtWidgets.QLabel()
        self._failure_codes_label = QtWidgets.QLabel()
        self._failure_codes_label.setWordWrap(True)

        for label in (
            self._mode_label,
            self._fallback_label,
            self._ray_rmse_label,
            self._time_offset_label,
            self._failure_codes_label,
        ):
            self._style_manager.style_label(label, "body")
            layout.addWidget(label)

        self.setLayout(layout)
        self.setMaximumWidth(350)
        self.setProperty("surface", "card")
        self._style_manager.polish(self)

    def load_pitch(self, pitch: Any) -> None:
        """Load diagnostics from a LoadedPitch-like object."""
        raw_manifest = getattr(pitch, "manifest", {}) or {}
        manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
        trajectory = _trajectory_block(manifest)
        comparison = _comparison_data(manifest, trajectory)

        mode = _first_present(trajectory, manifest, "mode", "trajectory_mode")
        ray_rmse = _first_present(trajectory, manifest, "ray_rmse_px", "ray_rmse_px")
        time_offset = _first_present(
            trajectory,
            manifest,
            "estimated_camera_time_offset_ms",
            "estimated_camera_time_offset_ms",
        )

        self._mode_label.setText(f"Mode: {_format_value(mode)}")
        self._fallback_label.setText(f"Fallback: {_format_fallback(comparison)}")
        self._ray_rmse_label.setText(f"Ray RMSE: {_format_number(ray_rmse, ' px')}")
        self._time_offset_label.setText(
            f"Camera offset: {_format_number(time_offset, ' ms')}"
        )
        self._failure_codes_label.setText(
            f"Mode failures: {_format_failure_codes(comparison)}"
        )

    def clear(self) -> None:
        """Clear diagnostics when no pitch is selected."""
        self._mode_label.setText("Mode: -")
        self._fallback_label.setText("Fallback: -")
        self._ray_rmse_label.setText("Ray RMSE: -")
        self._time_offset_label.setText("Camera offset: -")
        self._failure_codes_label.setText("Mode failures: -")


def _trajectory_block(manifest: dict[str, Any]) -> dict[str, Any]:
    trajectory = manifest.get("trajectory")
    return trajectory if isinstance(trajectory, dict) else {}


def _comparison_data(
    manifest: dict[str, Any],
    trajectory: dict[str, Any],
) -> dict[str, Any]:
    comparison = trajectory.get("comparison") or manifest.get("trajectory_comparison")
    return comparison if isinstance(comparison, dict) else {}


def _first_present(
    trajectory: dict[str, Any],
    manifest: dict[str, Any],
    trajectory_key: str,
    manifest_key: str,
) -> Any:
    trajectory_value = trajectory.get(trajectory_key)
    if trajectory_value is not None and trajectory_value != "":
        return trajectory_value
    return manifest.get(manifest_key)


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _format_number(value: Any, unit: str) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.2f}{unit}"
    except (TypeError, ValueError):
        return str(value)


def _format_fallback(comparison: dict[str, Any]) -> str:
    if not comparison:
        return "-"

    for result in comparison.values():
        if not isinstance(result, dict):
            continue
        fallback = result.get("fallback_used")
        if fallback:
            return f"Yes, used {fallback}"
    return "No"


def _format_failure_codes(comparison: dict[str, Any]) -> str:
    if not comparison:
        return "-"

    entries: list[str] = []
    for mode, result in comparison.items():
        diagnostics = result.get("diagnostics") if isinstance(result, dict) else None
        codes = diagnostics.get("failure_codes") if isinstance(diagnostics, dict) else None
        if codes:
            entries.append(f"{mode}: {', '.join(str(code) for code in codes)}")
        else:
            entries.append(f"{mode}: OK")

    return "; ".join(entries) if entries else "-"
