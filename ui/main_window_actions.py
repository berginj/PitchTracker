"""Action and preview methods extracted from MainWindow."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from PySide6 import QtWidgets

from configs.settings import load_config
from detect.config import DetectorConfig as CvDetectorConfig
from detect.config import Mode
from ui.dialogs import StartupDialog
from ui.drawing import frame_to_pixmap
from ui.geometry import Rect, roi_overlays
from ui.themes import show_message_dialog


class MainWindowActionsMixin:
    def _start_capture(self) -> None:
        self._capture_controller.start_capture()

    def _stop_capture(self) -> None:
        self._capture_controller.stop_capture()

    def _restart_capture(self) -> None:
        self._capture_controller.restart_capture()

    def _start_recording(self) -> None:
        self._recording_controller.start_recording()

    def _browse_output(self) -> None:
        self._recording_controller.browse_output()

    def _set_output_dir(self, path: str) -> None:
        self._recording_controller.set_output_dir(path)

    def _set_manual_speed(self, value: float) -> None:
        self._recording_controller.set_manual_speed(value)

    def _stop_recording(self) -> None:
        self._recording_controller.stop_recording()

    def _set_setup_mode(self, active: bool) -> None:
        for widget in (
            self._start_button,
            self._stop_button,
            self._restart_button,
            self._record_button,
            self._stop_record_button,
            self._training_button,
            self._replay_button,
            self._pause_button,
            self._step_button,
            self._record_settings_button,
            self._strike_settings_button,
            self._detector_settings_button,
            self._checklist_button,
        ):
            widget.setEnabled(not active)
        self._setup_group.setVisible(active)

    def _enter_app(self) -> None:
        self._set_setup_mode(False)

    def _refresh_profiles(self) -> None:
        self._profile_manager.refresh_profiles()

    def _refresh_pitchers(self) -> None:
        self._profile_manager.refresh_pitchers()

    def _load_profile(self) -> None:
        self._profile_manager.load_profile(self)

    def _save_profile(self) -> None:
        self._profile_manager.save_profile(self)

    def _add_pitcher(self) -> None:
        self._profile_manager.add_pitcher()

    def _set_pitcher(self, name: str) -> None:
        self._profile_manager.set_pitcher(name)

    def _run_startup_dialog(self) -> None:
        dialog = StartupDialog(self)
        result = dialog.exec()
        if result != QtWidgets.QDialog.Accepted:
            return
        profile_name, pitcher = dialog.values()
        self._profile_manager.apply_startup_selection(profile_name, pitcher)
        if profile_name:
            self._load_profile()
        self._calibration_manager.run_calibration_wizard()

    def _run_calibration_wizard(self) -> None:
        self._calibration_manager.run_calibration_wizard()

    def _cue_card_test(self) -> None:
        try:
            detections = self._service.get_latest_detections()
        except Exception:
            show_message_dialog(
                self,
                "Cue Card Test",
                "Start capture to run the cue card test.",
                tone="info",
            )
            return
        total = sum(len(items) for items in detections.values())
        show_message_dialog(
            self,
            "Cue Card Test",
            f"Detections in current frame: {total}\n" "Hold the cue card in the lane and confirm detections appear.",
            tone="info",
        )

    def _apply_low_perf_mode(self) -> None:
        if self._timer.isActive():
            show_message_dialog(
                self,
                "Low Perf Mode",
                "Stop capture before applying low performance settings.",
                tone="info",
            )
            return
        config_path = self._config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("camera", {})
        data.setdefault("ui", {})
        data["camera"]["width"] = 1280
        data["camera"]["height"] = 720
        data["camera"]["fps"] = 30
        data["ui"]["refresh_hz"] = 10
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self._config = load_config(config_path)
        self._load_detector_defaults()
        self._status_label.setText("Low performance mode applied.")

    def _default_session_name(self) -> Optional[str]:
        return self._recording_controller.default_session_name()

    def _upload_session(self, summary) -> None:
        self._export_manager.upload_session(summary)

    def _save_session_export(
        self,
        summary,
        session_dir: Optional[Path],
        export_type: Optional[str],
    ) -> None:
        del session_dir
        self._export_manager.save_export(summary, export_type)

    def _start_training_capture(self) -> None:
        self._recording_controller.start_training_capture()

    def _update_preview(self) -> None:
        if self._replay_controller.is_active:
            self._update_replay()
            return

        try:
            left_frame, right_frame = self._service.get_preview_frames()
        except RuntimeError as exc:
            self._status_label.setText(str(exc))
            return

        self._left_view.set_image_size(left_frame.width, left_frame.height)

        lane_rect = self._roi_manager.lane_rect
        plate_rect = self._roi_manager.plate_rect
        active_rect = self._roi_manager.active_rect
        overlays_left = roi_overlays(lane_rect, plate_rect, active_rect)
        lane_right = self._roi_manager.lane_rect_right or lane_rect
        overlays_right = roi_overlays(lane_right, plate_rect, active_rect)

        detections = self._service.get_latest_detections()
        gated = self._service.get_latest_gated_detections()
        left_dets = detections.get(left_frame.camera_id, [])
        right_dets = detections.get(right_frame.camera_id, [])
        left_gated = gated.get(left_frame.camera_id, {})
        right_gated = gated.get(right_frame.camera_id, {})

        strike = self._service.get_strike_result()
        zone = None
        if strike.zone_row is not None and strike.zone_col is not None:
            zone = (strike.zone_row, strike.zone_col)

        checkerboard, fiducials = self._calibration_overlay.process_frame(left_frame.image)
        focus_left, focus_right = self._focus_monitor.compute_scores(left_frame.image, right_frame.image)
        focus_overlay_left, focus_overlay_right = self._focus_monitor.get_overlay_scores(
            self._calibration_overlay.show_target
        )

        self._left_view.setPixmap(
            frame_to_pixmap(
                left_frame.image,
                overlays_left,
                left_dets,
                left_gated.get("lane", []),
                left_gated.get("plate", []),
                plate_rect=plate_rect,
                zone=zone,
                checkerboard=checkerboard,
                fiducials=fiducials,
                focus_score=focus_overlay_left,
            )
        )

        if self._right_view.isVisible():
            self._right_view.setPixmap(
                frame_to_pixmap(
                    right_frame.image,
                    overlays_right,
                    right_dets,
                    right_gated.get("lane", []),
                    right_gated.get("plate", []),
                    plate_rect=plate_rect,
                    zone=zone,
                    focus_score=focus_overlay_right,
                )
            )

        self._update_plate_map()

        stats = self._service.get_stats()
        plate_metrics = self._service.get_plate_metrics()
        if stats:
            left_stats = stats.get("left", {})
            right_stats = stats.get("right", {})

            self._health_left.setText(
                "L: fps={:.1f} jitter={:.1f}ms drops={}".format(
                    left_stats.get("fps_avg", 0.0),
                    left_stats.get("jitter_p95_ms", 0.0),
                    int(left_stats.get("dropped_frames", 0)),
                )
            )
            self._health_right.setText(
                "R: fps={:.1f} jitter={:.1f}ms drops={}".format(
                    right_stats.get("fps_avg", 0.0),
                    right_stats.get("jitter_p95_ms", 0.0),
                    int(right_stats.get("dropped_frames", 0)),
                )
            )

            self._focus_monitor.update_display(focus_left, focus_right)

            zone_label = "-"
            if strike.zone_row is not None and strike.zone_col is not None:
                zone_label = f"{strike.zone_row},{strike.zone_col}"
            self._status_label.setText(
                "fps L={:.1f} R={:.1f} drops L={} R={} run={:.2f} rise={:.2f} strike={} zone={}".format(
                    left_stats.get("fps_avg", 0.0),
                    right_stats.get("fps_avg", 0.0),
                    int(left_stats.get("dropped_frames", 0)),
                    int(right_stats.get("dropped_frames", 0)),
                    plate_metrics.run_in,
                    plate_metrics.rise_in,
                    "Y" if strike.is_strike else "N",
                    zone_label,
                )
            )

    def _start_replay(self) -> None:
        self._replay_controller.start_replay()

    def _stop_replay(self) -> None:
        self._replay_controller.stop_replay()

    def _update_replay(self) -> None:
        self._replay_controller.update_replay()

    def _toggle_replay_pause(self) -> None:
        self._replay_controller.toggle_pause()

    def _step_replay(self) -> None:
        self._replay_controller.step_frame()

    def _refresh_devices(self) -> None:
        self._device_manager.refresh_devices()

    def _set_roi_mode(self, mode: str) -> None:
        self._roi_manager.set_roi_mode(mode)

    def _on_rect_update(self, rect: Rect, final: bool) -> None:
        self._roi_manager.on_rect_update(rect, final)

    def _on_right_rect_update(self, rect: Rect, final: bool) -> None:
        self._roi_manager.on_right_rect_update(rect, final)

    def _clear_lane(self) -> None:
        self._roi_manager.clear_lane()

    def _clear_plate(self) -> None:
        self._roi_manager.clear_plate()

    def _reset_focus_peaks(self) -> None:
        self._focus_monitor.reset_peaks()
        self._status_label.setText("Focus peak values reset. Adjust lenses and watch for green.")

    def _save_rois(self) -> None:
        self._roi_manager.save_rois()

    def _load_rois(self) -> None:
        self._roi_manager.load_rois()

    def _load_detector_defaults(self) -> None:
        self._settings_manager.load_detector_defaults()

    def _apply_detector_config(self) -> None:
        self._settings_manager.apply_detector_config()

    def _apply_detector_to_service(
        self,
        detector_cfg: CvDetectorConfig,
        mode: Mode,
        ml_settings: dict,
    ) -> None:
        self._service.set_detector_config(
            detector_cfg,
            mode,
            detector_type=ml_settings["detector_type"],
            model_path=ml_settings["model_path"],
            model_input_size=ml_settings["model_input_size"],
            model_conf_threshold=ml_settings["model_conf_threshold"],
            model_class_id=ml_settings["model_class_id"],
            model_format=ml_settings["model_format"],
        )
        self._service.set_detection_threading(
            ml_settings["threading_mode"],
            ml_settings["worker_count"],
        )

    def _set_ball_type(self, ball_type: str) -> None:
        self._settings_manager.set_ball_type(ball_type)

    def _set_batter_height(self, value: float) -> None:
        self._settings_manager.set_batter_height(value)

    def _set_strike_ratios(self) -> None:
        self._settings_manager.set_strike_ratios()

    def _save_strike_zone(self) -> None:
        self._settings_manager.save_strike_zone()

    def _health_ok(self) -> bool:
        stats = self._service.get_stats()
        if not stats:
            return False
        left = stats.get("left", {})
        right = stats.get("right", {})
        fps_ok = left.get("fps_avg", 0.0) >= 58.0 and right.get("fps_avg", 0.0) >= 58.0
        drops_ok = int(left.get("dropped_frames", 0)) <= 2 and int(right.get("dropped_frames", 0)) <= 2
        return fps_ok and drops_ok

    def _update_plate_map_zone(self) -> None:
        self._game_visualizer.update_plate_map_zone()

    def _update_plate_map(self) -> None:
        summary = self._service.get_session_summary()
        self._game_visualizer.update_plate_map(summary)

    def _reset_tic_tac_toe_game(self) -> None:
        self._game_visualizer.reset_game()

    def _set_production_mode(self, enabled: bool) -> None:
        self._production_mode = enabled
        self._setup_group.setVisible(not enabled)
        if enabled:
            self._health_panel.setVisible(False)
            self._status_label.setVisible(False)
            self._controls_widget.setVisible(False)
            self._right_view.setVisible(False)
            self._right_camera_action.setChecked(False)
            self._views_layout.setStretch(0, 3)
            self._views_layout.setStretch(1, 4)
            self._views_layout.setStretch(2, 0)
        else:
            self._health_panel.setVisible(self._health_toggle_action.isChecked())
            self._status_label.setVisible(True)
            self._controls_widget.setVisible(True)
            self._right_view.setVisible(self._right_camera_action.isChecked())
            self._views_layout.setStretch(0, 3)
            self._views_layout.setStretch(1, 2)
            self._views_layout.setStretch(2, 2)
        if enabled:
            self._status_label.setText("Production mode.")

    def _set_target_mode(self, enabled: bool) -> None:
        self._game_visualizer.set_target_mode(enabled)
