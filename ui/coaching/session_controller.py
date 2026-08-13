"""Session lifecycle controller for CoachWindow.

Handles setup, recording start/stop/pause, settings, lane adjustment,
and pitcher switching — all the action methods that mutate session state.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from app.services.rig_profile import RigProfileService
from configs.app_state import load_state, save_state
from ui.themes import ask_confirmation, show_choice_dialog, show_message_dialog

if TYPE_CHECKING:
    from ui.coaching.coach_window import CoachWindow

logger = logging.getLogger(__name__)


class SessionController:
    """Encapsulates session lifecycle logic for the coaching window.

    This is a mixin-style helper that operates on CoachWindow state via
    a reference to the host window.  It holds no independent state.
    """

    def __init__(self, host: "CoachWindow") -> None:
        self._host = host

    # ------------------------------------------------------------------
    # Camera cache warming
    # ------------------------------------------------------------------

    def warm_camera_cache_async(self) -> None:
        """Proactively warm camera cache in background thread."""

        def _warm_cache():
            try:
                from ui.device_utils import (
                    DEFAULT_OPENCV_MAX_INDEX,
                    probe_opencv_indices,
                    probe_uvc_devices,
                )

                logger.debug("Background: Warming camera cache...")
                probe_uvc_devices(use_cache=True)
                probe_opencv_indices(
                    max_index=DEFAULT_OPENCV_MAX_INDEX, parallel=False, use_cache=True
                )
                logger.info("Background: Camera cache warmed successfully")
            except Exception as e:
                logger.warning(f"Background: Camera cache warming failed: {e}")

        thread = threading.Thread(target=_warm_cache, daemon=True, name="CameraCache")
        thread.start()

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------

    def setup_session(self) -> None:
        """Setup coaching session (cameras and configuration only)."""
        from ui.coaching.dialogs import SessionStartDialog

        h = self._host
        dialog = SessionStartDialog(
            h._config,
            parent=h,
            backend=h._backend,
            config_path=h._config_path,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        h._session_name = dialog.session_name
        h._pitcher_name = dialog.pitcher_name
        h._pitch_count = 0
        h._last_pitch_count = 0
        h._processed_pitch_ids.clear()
        h._pitch_snapshot = []

        if dialog.batter_height_in != h._config.strike_zone.batter_height_in:
            h._service.set_batter_height_in(dialog.batter_height_in)
            h._config = replace(
                h._config,
                strike_zone=replace(
                    h._config.strike_zone,
                    batter_height_in=dialog.batter_height_in,
                ),
            )

        if dialog.ball_type != h._config.ball.type:
            h._service.set_ball_type(dialog.ball_type)
            h._config = replace(h._config, ball=replace(h._config.ball, type=dialog.ball_type))

        h._pitch_display.apply_strike_zone_overlay_config(dialog.batter_height_in)

        left_serial = dialog.left_serial
        right_serial = dialog.right_serial

        try:
            if not h._service.is_capturing():
                logger.info(f"Starting capture with left={left_serial}, right={right_serial}")
                h._set_status_message("Starting cameras...", "info")
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
                coaching_config, left_serial, right_serial = self._apply_active_rig_capture_settings(
                    coaching_config, left_serial, right_serial
                )
                h._service.start_capture(
                    coaching_config, left_serial, right_serial, str(h._config_path)
                )
                logger.info(
                    "Capture started successfully with %sx%s@%sfps",
                    coaching_config.camera.width,
                    coaching_config.camera.height,
                    coaching_config.camera.fps,
                )
            else:
                logger.info("Capture already running, skipping camera start")

            state = load_state()
            state["last_left_camera"] = left_serial
            state["last_right_camera"] = right_serial
            save_state(state)
            logger.info(f"Saved camera selections: left={left_serial}, right={right_serial}")

        except Exception as e:
            logger.error(f"Failed to setup session: {e}", exc_info=True)
            show_message_dialog(
                h, "Session Setup Error", f"Failed to setup session:\n{str(e)}", tone="error"
            )
            return

        # Update UI
        h._session_label.setText(f"Session: {h._session_name}")
        h._pitcher_label.setText(f"Pitcher: {h._pitcher_name}")
        h._pitch_count_label.setText("Pitches: 0")

        for mode in (h._broadcast_mode, h._progression_mode, h._game_mode):
            mode.clear()
        h._session_tracker.clear()

        h._setup_button.setEnabled(False)
        h._start_recording_button.setEnabled(True)
        h._end_button.setEnabled(True)
        h._set_status_message(
            "Session ready. Click 'Start Recording' when ready to pitch.", "warning"
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(self) -> None:
        """Start recording pitches."""
        h = self._host
        if not h._service.is_capturing():
            show_message_dialog(
                h,
                "No Cameras",
                "Cameras are not running. Please setup the session first.",
                tone="warning",
            )
            return

        try:
            logger.info(f"Starting recording for session: {h._session_name}")
            h._set_status_message("Starting recording...", "info")
            QtWidgets.QApplication.processEvents()

            disk_warning = h._service.start_recording(
                pitch_id="session", session_name=h._session_name, mode="session"
            )
            logger.info("Recording started successfully")

            if disk_warning:
                show_message_dialog(
                    h,
                    "Disk Space Warning",
                    disk_warning + "\n\nYou can continue, but recording may fail if disk fills up.",
                    tone="warning",
                )
        except Exception as e:
            logger.error(f"Failed to start recording: {e}", exc_info=True)
            show_message_dialog(
                h, "Recording Start Error", f"Failed to start recording:\n{str(e)}", tone="error"
            )
            return

        h._recording_indicator.show()
        h._start_recording_button.setEnabled(False)
        h._pause_button.setEnabled(True)
        h._pause_button.setText("Pause")
        h._set_status_message("Recording in progress. Ready to track pitches.", "success")
        h._style_manager.style_status_indicator(h._status_label, "success")

        h._session_active = True
        h._session_paused = False

    def pause_session(self) -> None:
        """Toggle pause/resume for the current recording session."""
        h = self._host
        if not h._session_active:
            return

        try:
            if h._session_paused:
                h._service.resume_recording()
                h._session_paused = False
                h._pause_button.setText("Pause")
                h._recording_indicator.show()
                h._set_status_message("Recording resumed. Ready to track pitches.", "success")
            else:
                h._service.pause_recording()
                h._session_paused = True
                h._pause_button.setText("Resume")
                h._recording_indicator.hide()
                h._set_status_message(
                    "Session paused. Cameras remain live until you resume.", "warning"
                )
        except Exception as e:
            logger.error(f"Failed to toggle pause state: {e}", exc_info=True)
            show_message_dialog(
                h, "Pause Error", f"Unable to update the session state:\n{e}", tone="error"
            )

    def end_session(self) -> None:
        """End current session and show summary."""
        h = self._host
        if not ask_confirmation(
            h,
            "End Session",
            f"End session '{h._session_name}' with {h._pitch_count} pitches?\n\n"
            "Session summary will be displayed.",
            confirm_variant="danger",
        ):
            return

        h._set_status_message("Stopping recording...", "info")
        QtWidgets.QApplication.processEvents()

        try:
            h._service.stop_recording()
        except Exception as e:
            logger.error("Failed to end session cleanly: %s", e, exc_info=True)
            show_message_dialog(
                h,
                "Session End Error",
                f"Error stopping session:\n{str(e)}\n\n"
                "The session is still active. Resolve the error and try End Session again.",
                tone="error",
            )
            h._set_status_message(
                "Session stop failed. Session remains active; retry End Session.", "error"
            )
            return

        try:
            summary = h._service.get_last_session_summary()
        except Exception as e:
            logger.error("Session stopped but final summary could not be read: %s", e, exc_info=True)
            summary = None
            show_message_dialog(
                h,
                "Session Summary Unavailable",
                f"The session was saved, but its final summary could not be displayed:\n{e}",
                tone="warning",
            )

        if summary:
            show_message_dialog(
                h,
                "Session Complete",
                f"Session: {h._session_name}\n"
                f"Pitcher: {h._pitcher_name}\n"
                f"Pitches: {summary.pitch_count}\n"
                f"Strikes: {summary.strikes}\n"
                f"Balls: {summary.balls}\n\n"
                f"Session data saved.",
                tone="success",
            )

        h._session_label.setText("Session: <not started>")
        h._pitcher_label.setText("Pitcher: <not selected>")
        h._pitch_count_label.setText("Pitches: 0")
        h._recording_indicator.hide()

        h._setup_button.setEnabled(True)
        h._start_recording_button.setEnabled(False)
        h._pause_button.setEnabled(False)
        h._pause_button.setText("Pause")
        h._end_button.setEnabled(False)

        h._set_status_message("Session ended. Ready for the next session.", "info")
        h._session_active = False
        h._session_paused = False

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def show_settings(self) -> None:
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
            h._camera_width = dialog.width
            h._camera_height = dialog.height
            h._camera_fps = dialog.fps
            h._camera_color_mode = dialog.color_mode
            if active_profile is not None:
                rig_config = RigProfileService(config_path=h._config_path).apply_profile_to_config(
                    h._config, active_profile, preserve_camera_mode=False
                )
                h._camera_width = rig_config.camera.width
                h._camera_height = rig_config.camera.height
                h._camera_fps = rig_config.camera.fps
                h._camera_color_mode = rig_config.camera.color_mode
                if (
                    dialog.width != h._camera_width
                    or dialog.height != h._camera_height
                    or dialog.fps != h._camera_fps
                    or dialog.left_camera != active_profile.left_serial
                    or dialog.right_camera != active_profile.right_serial
                ):
                    show_message_dialog(
                        h,
                        "Rig Settings Locked",
                        "Camera identity and capture mode are owned by the active rig profile. "
                        "Run Setup Wizard to change and revalidate them; other session settings "
                        "were retained.",
                        tone="warning",
                    )

            if dialog.mound_distance_ft != current_mound_distance:
                h._service.update_mound_distance(dialog.mound_distance_ft)
                logger.info(f"Updated mound distance to {dialog.mound_distance_ft:.1f} ft")

            if h._service.is_capturing():
                self._restart_capture_with_settings(dialog, active_profile)
            else:
                show_message_dialog(
                    h,
                    "Settings Saved",
                    f"Settings saved successfully.\n\n"
                    f"Resolution: {h._camera_width}x{h._camera_height}@{h._camera_fps}fps\n"
                    f"Settings will apply when you start the next session.",
                    tone="success",
                )

    def _restart_capture_with_settings(self, dialog, active_profile) -> None:
        """Restart capture after settings change."""
        h = self._host
        h._set_status_message("Applying settings...", "info")
        QtWidgets.QApplication.processEvents()

        try:
            h._service.stop_capture()
            current_mode = h._mode_stack.currentWidget()
            current_mode.clear()
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
            coaching_config, left_camera, right_camera = self._apply_active_rig_capture_settings(
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
                f"Settings applied: {h._camera_width}x{h._camera_height}@{h._camera_fps}fps"
            )
        except Exception as e:
            show_message_dialog(
                h,
                "Settings Error",
                f"Failed to apply settings:\n{e}\n\nYou may need to restart the application.",
                tone="error",
            )
            logger.exception("Failed to apply settings")
            h._set_status_message("Error applying settings", "error")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _apply_active_rig_capture_settings(self, config, left_serial: str, right_serial: str):
        """Apply the active rig's calibrated mode and camera identities."""
        h = self._host
        profile = RigProfileService(config_path=h._config_path).load_active()
        if profile is None:
            return config, left_serial, right_serial
        config = RigProfileService(config_path=h._config_path).apply_profile_to_config(
            config, profile, preserve_camera_mode=False
        )
        return config, profile.left_serial or left_serial, profile.right_serial or right_serial

    def adjust_lane(self) -> None:
        """Show lane ROI adjustment dialog."""
        h = self._host
        if not h._service.is_capturing():
            show_message_dialog(
                h,
                "Cameras Not Running",
                "Please start a session first to view the camera feed.\n\n"
                "The lane ROI adjustment requires a live camera preview.",
                tone="warning",
            )
            return

        from ui.coaching.dialogs.lane_adjust_dialog import LaneAdjustDialog

        dialog = LaneAdjustDialog(camera_service=h._service, parent=h)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            show_message_dialog(
                h,
                "Lane ROI Updated",
                "Lane ROI has been updated.\n\n"
                "Changes will take effect for new pitches tracked during this session.",
                tone="success",
            )

    def switch_pitcher(self) -> None:
        """Show team manager dialog to switch pitchers."""
        from ui.team import TeamManager

        h = self._host
        dialog = TeamManager(parent=h)
        dialog.pitcher_selected.connect(self._on_pitcher_switched)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_pitcher()
            if selected:
                self._on_pitcher_switched(selected)

    def _on_pitcher_switched(self, pitcher_name: str) -> None:
        """Handle pitcher switch."""
        h = self._host
        old_pitcher = h._pitcher_name
        h._pitcher_name = pitcher_name
        h._pitcher_label.setText(f"Pitcher: {pitcher_name}")
        h._fatigue_indicator.reset()
        logger.info(f"Switched pitcher: {old_pitcher} -> {pitcher_name}")
        h._status_label.setText(f"Switched to pitcher: {pitcher_name}")

    def handle_close_event(self, event) -> None:
        """Handle window close — stop capture and recording."""
        h = self._host
        h._preview_timer.stop()
        h._metrics_timer.stop()

        if h._session_active:
            reply = show_choice_dialog(
                h,
                "Session Active",
                "A session is currently active. End session before closing?",
                choices=(
                    ("end", "End Session", "primary", QtWidgets.QMessageBox.ButtonRole.AcceptRole),
                    (
                        "close",
                        "Close Without Ending",
                        "ghost",
                        QtWidgets.QMessageBox.ButtonRole.DestructiveRole,
                    ),
                    ("cancel", "Cancel", "ghost", QtWidgets.QMessageBox.ButtonRole.RejectRole),
                ),
                default_choice="cancel",
            )
            if reply == "cancel":
                event.ignore()
                h._preview_timer.start(33)
                h._metrics_timer.start(100)
                return
            elif reply == "end":
                try:
                    h._service.stop_recording()
                except Exception:
                    pass

        try:
            if h._service.is_capturing():
                h._service.stop_capture()
        except Exception:
            pass

        event.accept()

    def open_review_mode(self) -> None:
        """Open review mode window."""
        from ui.review import ReviewWindow

        review_window = ReviewWindow(parent=self._host)
        review_window.show()
        logger.info("Opened review mode window")
