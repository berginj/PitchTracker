"""Settings workflow for the coaching window."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, cast

from PySide6 import QtWidgets

from app.services.rig_profile import RigProfileService
from configs.app_state import load_state
from ui.coaching.widgets.mode_widgets import BaseModeWidget
from ui.themes import show_message_dialog

if TYPE_CHECKING:
    from ui.coaching.coach_window import CoachWindow

logger = logging.getLogger(__name__)


class SettingsWorkflow:
    """Coordinates coaching settings and capture restarts."""

    def __init__(self, host: "CoachWindow") -> None:
        self._host = host

    def show(self) -> None:
        """Show settings dialog."""
        h = self._host
        if h._session_active:
            show_message_dialog(
                h,
                "Session Active",
                "Cannot change settings during an active session.\n"
                "Please end the current session first.",
                tone="warning",
            )
            return

        from ui.coaching.dialogs.settings_dialog import SettingsDialog

        state = load_state()
        active_profile = RigProfileService(config_path=h._config_path).load_active()
        current_left = (
            active_profile.left_serial if active_profile else state.get("last_left_camera", "0")
        )
        current_right = (
            active_profile.right_serial if active_profile else state.get("last_right_camera", "1")
        )
        current_mound_distance = state.get(
            "mound_distance_ft", h._config.metrics.release_plane_z_ft
        )
        current_left = current_left if isinstance(current_left, str) else "0"
        current_right = current_right if isinstance(current_right, str) else "1"
        current_mound_distance = (
            float(current_mound_distance)
            if isinstance(current_mound_distance, (int, float))
            else float(h._config.metrics.release_plane_z_ft)
        )
        dialog = SettingsDialog(
            current_width=h._camera_width,
            current_height=h._camera_height,
            current_fps=h._camera_fps,
            current_left_camera=current_left,
            current_right_camera=current_right,
            current_mound_distance=current_mound_distance,
            current_ball_type=h._config.ball.type,
            current_color_mode=h._camera_color_mode,
            parent=h,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        if dialog.settings_changed:
            self._apply_changes(dialog, active_profile, current_mound_distance)

    def _apply_changes(self, dialog, active_profile, current_mound_distance) -> None:
        h = self._host
        h._camera_width = dialog.selected_width
        h._camera_height = dialog.selected_height
        h._camera_fps = dialog.fps
        h._camera_color_mode = dialog.color_mode
        if active_profile is not None:
            self._apply_profile_lock(dialog, active_profile)

        if dialog.mound_distance_ft != current_mound_distance:
            h._service.update_mound_distance(dialog.mound_distance_ft)
            logger.info("Updated mound distance to %.1f ft", dialog.mound_distance_ft)

        if h._service.is_capturing():
            self._restart_capture(dialog)
        else:
            show_message_dialog(
                h,
                "Settings Saved",
                f"Settings saved successfully.\n\n"
                f"Resolution: {h._camera_width}x{h._camera_height}@{h._camera_fps}fps\n"
                f"Settings will apply when you start the next session.",
                tone="success",
            )

    def _apply_profile_lock(self, dialog, active_profile) -> None:
        h = self._host
        rig_config = RigProfileService(config_path=h._config_path).apply_profile_to_config(
            h._config, active_profile, preserve_camera_mode=False
        )
        h._camera_width = rig_config.camera.width
        h._camera_height = rig_config.camera.height
        h._camera_fps = rig_config.camera.fps
        h._camera_color_mode = rig_config.camera.color_mode
        settings_differ = (
            dialog.selected_width != h._camera_width
            or dialog.selected_height != h._camera_height
            or dialog.fps != h._camera_fps
            or dialog.left_camera != active_profile.left_serial
            or dialog.right_camera != active_profile.right_serial
        )
        if settings_differ:
            show_message_dialog(
                h,
                "Rig Settings Locked",
                "Camera identity and capture mode are owned by the active rig profile. "
                "Run Setup Wizard to change and revalidate them; other session settings "
                "were retained.",
                tone="warning",
            )

    def _restart_capture(self, dialog) -> None:
        h = self._host
        h._set_status_message("Applying settings...", "info")
        QtWidgets.QApplication.processEvents()
        try:
            h._service.stop_capture()
            current_mode = h._mode_stack.currentWidget()
            if current_mode is None:
                raise RuntimeError("Coaching mode stack contains an unsupported widget")
            cast(BaseModeWidget, current_mode).clear()
            QtWidgets.QApplication.processEvents()
            coaching_config = replace(
                h._config,
                camera=replace(
                    h._config.camera,
                    width=h._camera_width,
                    height=h._camera_height,
                    fps=h._camera_fps,
                    color_mode=h._camera_color_mode,
                ),
            )
            coaching_config, left_camera, right_camera = self.apply_rig_capture_settings(
                coaching_config, dialog.left_camera, dialog.right_camera
            )
            h._service.start_capture(
                coaching_config, left_camera, right_camera, str(h._config_path)
            )
            h._set_status_message(
                f"Settings applied: {h._camera_width}x{h._camera_height}@{h._camera_fps}fps",
                "success",
            )
            logger.info(
                "Settings applied: %sx%s@%sfps",
                h._camera_width,
                h._camera_height,
                h._camera_fps,
            )
        except Exception as exc:
            show_message_dialog(
                h,
                "Settings Error",
                f"Failed to apply settings:\n{exc}\n\nYou may need to restart the application.",
                tone="error",
            )
            logger.exception("Failed to apply settings")
            h._set_status_message("Error applying settings", "error")

    def apply_rig_capture_settings(self, config, left_serial: str, right_serial: str):
        """Apply the active rig's calibrated mode and camera identities."""
        h = self._host
        service = RigProfileService(config_path=h._config_path)
        profile = service.load_active()
        if profile is None:
            return config, left_serial, right_serial
        config = service.apply_profile_to_config(config, profile, preserve_camera_mode=False)
        return config, profile.left_serial or left_serial, profile.right_serial or right_serial
