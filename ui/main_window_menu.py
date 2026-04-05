"""Menu, dialog, and secondary panel methods extracted from MainWindow."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from ui.dialogs import ChecklistDialog, DetectorSettingsDialog, RecordingSettingsDialog, StrikeZoneSettingsDialog
from ui.themes import GlassButton, get_style_manager, show_message_dialog


class MainWindowMenuMixin:
    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        capture_menu = menu_bar.addMenu("Capture")
        start_action = capture_menu.addAction("Start Capture")
        start_action.setShortcut(QtGui.QKeySequence("F5"))
        stop_action = capture_menu.addAction("Stop Capture")
        stop_action.setShortcut(QtGui.QKeySequence("F6"))
        restart_action = capture_menu.addAction("Restart Capture")
        restart_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+R"))
        capture_menu.addSeparator()
        record_action = capture_menu.addAction("Start Recording")
        record_action.setShortcut(QtGui.QKeySequence("Ctrl+R"))
        stop_record_action = capture_menu.addAction("Stop Recording")
        stop_record_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        capture_menu.addSeparator()
        training_action = capture_menu.addAction("Training Capture")
        training_action.setShortcut(QtGui.QKeySequence("Ctrl+T"))
        start_action.triggered.connect(self._start_capture)
        stop_action.triggered.connect(self._stop_capture)
        restart_action.triggered.connect(self._restart_capture)
        record_action.triggered.connect(self._start_recording)
        stop_record_action.triggered.connect(self._stop_recording)
        training_action.triggered.connect(self._start_training_capture)

        calibration_menu = menu_bar.addMenu("Calibration")
        guide_action = calibration_menu.addAction("Calibration Guide")
        guide_action.setShortcut(QtGui.QKeySequence("Ctrl+G"))
        wizard_action = calibration_menu.addAction("Calibration Wizard")
        wizard_action.setShortcut(QtGui.QKeySequence("Ctrl+W"))
        quick_action = calibration_menu.addAction("Quick Calibrate")
        quick_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        plate_action = calibration_menu.addAction("Plate Plane Calibrate")
        plate_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+P"))
        guide_action.triggered.connect(self._open_calibration_guide)
        wizard_action.triggered.connect(self._run_calibration_wizard)
        quick_action.triggered.connect(self._open_quick_calibrate)
        plate_action.triggered.connect(self._open_plate_calibrate)

        roi_menu = menu_bar.addMenu("ROI")
        lane_action = roi_menu.addAction("Edit Lane ROI")
        lane_action.setShortcut(QtGui.QKeySequence("Ctrl+1"))
        lane_right_action = roi_menu.addAction("Edit Right Lane ROI")
        lane_right_action.setShortcut(QtGui.QKeySequence("Ctrl+2"))
        plate_roi_action = roi_menu.addAction("Edit Plate ROI")
        plate_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+3"))
        roi_menu.addSeparator()
        clear_lane_action = roi_menu.addAction("Clear Lane ROI")
        clear_plate_action = roi_menu.addAction("Clear Plate ROI")
        roi_menu.addSeparator()
        save_roi_action = roi_menu.addAction("Save ROIs")
        save_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        load_roi_action = roi_menu.addAction("Load ROIs")
        load_roi_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        lane_action.triggered.connect(lambda: self._set_roi_mode("lane"))
        lane_right_action.triggered.connect(lambda: self._set_roi_mode("lane_right"))
        plate_roi_action.triggered.connect(lambda: self._set_roi_mode("plate"))
        clear_lane_action.triggered.connect(self._clear_lane)
        clear_plate_action.triggered.connect(self._clear_plate)
        save_roi_action.triggered.connect(self._save_rois)
        load_roi_action.triggered.connect(self._load_rois)

        settings_menu = menu_bar.addMenu("Settings")
        record_settings_action = settings_menu.addAction("Recording Settings")
        record_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        strike_settings_action = settings_menu.addAction("Strike Zone Settings")
        strike_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
        detector_settings_action = settings_menu.addAction("Detector Settings")
        detector_settings_action.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        record_settings_action.triggered.connect(self._open_record_settings)
        strike_settings_action.triggered.connect(self._open_strike_settings)
        detector_settings_action.triggered.connect(self._open_detector_settings)

        tools_menu = menu_bar.addMenu("Tools")
        refresh_action = tools_menu.addAction("Refresh Devices")
        refresh_action.setShortcut(QtGui.QKeySequence("F5"))
        checklist_action = tools_menu.addAction("Checklist")
        checklist_action.setShortcut(QtGui.QKeySequence("Ctrl+L"))
        low_perf_action = tools_menu.addAction("Low Perf Mode")
        low_perf_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+L"))
        cue_card_action = tools_menu.addAction("Cue Card Test")
        reset_game_action = tools_menu.addAction("Reset Game")
        reset_game_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+G"))
        target_mode_action = tools_menu.addAction("Target Mode")
        target_mode_action.setCheckable(True)
        target_mode_action.setChecked(False)
        target_mode_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        refresh_action.triggered.connect(self._refresh_devices)
        checklist_action.triggered.connect(self._open_checklist)
        low_perf_action.triggered.connect(self._apply_low_perf_mode)
        cue_card_action.triggered.connect(self._cue_card_test)
        reset_game_action.triggered.connect(self._reset_tic_tac_toe_game)
        target_mode_action.toggled.connect(self._set_target_mode)

        review_menu = menu_bar.addMenu("Review")
        replay_action = review_menu.addAction("Replay")
        replay_action.setShortcut(QtGui.QKeySequence("Ctrl+P"))
        pause_action = review_menu.addAction("Pause/Resume Replay")
        pause_action.setShortcut(QtGui.QKeySequence("Space"))
        step_action = review_menu.addAction("Step Replay")
        step_action.setShortcut(QtGui.QKeySequence("Right"))
        replay_action.triggered.connect(self._start_replay)
        pause_action.triggered.connect(self._toggle_replay_pause)
        step_action.triggered.connect(self._step_replay)

        view_menu = menu_bar.addMenu("View")
        self._health_toggle_action = QtGui.QAction("Show Health Panel", self)
        self._health_toggle_action.setCheckable(True)
        self._health_toggle_action.setChecked(True)
        self._health_toggle_action.setShortcut(QtGui.QKeySequence("F2"))
        self._health_toggle_action.toggled.connect(self._health_panel.setVisible)
        view_menu.addAction(self._health_toggle_action)
        self._right_camera_action = QtGui.QAction("Show Right Camera", self)
        self._right_camera_action.setCheckable(True)
        self._right_camera_action.setChecked(False)
        self._right_camera_action.setShortcut(QtGui.QKeySequence("F3"))
        self._right_camera_action.toggled.connect(self._right_view.setVisible)
        view_menu.addAction(self._right_camera_action)
        self._production_action = QtGui.QAction("Production Mode", self)
        self._production_action.setCheckable(True)
        self._production_action.setChecked(False)
        self._production_action.setShortcut(QtGui.QKeySequence("F11"))
        self._production_action.toggled.connect(self._set_production_mode)
        view_menu.addAction(self._production_action)

        help_menu = menu_bar.addMenu("Help")
        shortcuts_action = help_menu.addAction("Keyboard Shortcuts")
        shortcuts_action.setShortcut(QtGui.QKeySequence("F1"))
        about_action = help_menu.addAction("About")
        shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        about_action.triggered.connect(self._show_about)

    def _build_health_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Health")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._health_left)
        layout.addWidget(self._health_right)
        layout.addWidget(self._focus_left)
        layout.addWidget(self._focus_right)
        reset_focus_btn = GlassButton("Reset Focus Peaks", variant="ghost")
        reset_focus_btn.clicked.connect(self._reset_focus_peaks)
        layout.addWidget(reset_focus_btn)
        layout.addWidget(self._calib_summary)
        panel.setLayout(layout)
        return panel

    def _build_game_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Game")
        layout = QtWidgets.QVBoxLayout()
        sm = get_style_manager()
        self._game_status = QtWidgets.QLabel("Ready.")
        sm.style_label(self._game_status, "status")
        self._game_score = QtWidgets.QLabel("Score X:0  O:0  R:0")
        sm.style_label(self._game_score, "status")
        self._game_streak_label = QtWidgets.QLabel("Streak: 0")
        sm.style_label(self._game_streak_label, "status")
        reset = GlassButton("Reset Game", variant="ghost")
        reset.clicked.connect(self._reset_tic_tac_toe_game)
        layout.addWidget(self._game_status)
        layout.addWidget(self._game_score)
        layout.addWidget(self._game_streak_label)
        layout.addWidget(reset)
        panel.setLayout(layout)
        return panel

    def _build_detector_panel(self) -> QtWidgets.QGroupBox:
        panel = QtWidgets.QGroupBox("Detector (Quick)")
        form = QtWidgets.QFormLayout()
        for field in (
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_circ,
        ):
            field.setDecimals(2)
            field.setMaximum(10_000.0)
        self._bg_alpha.setMaximum(1.0)
        self._bg_alpha.setSingleStep(0.01)
        self._min_area.setMaximum(100_000)
        form.addRow("Mode", self._mode_combo)
        form.addRow("Frame diff", self._frame_diff)
        form.addRow("BG diff", self._bg_diff)
        form.addRow("BG alpha", self._bg_alpha)
        form.addRow("Edge thresh", self._edge_thresh)
        form.addRow("Blob thresh", self._blob_thresh)
        form.addRow("Min area", self._min_area)
        form.addRow("Min circularity", self._min_circ)
        form.addRow(self._apply_detector)
        panel.setLayout(form)
        return panel

    def _open_calibration_guide(self) -> None:
        self._calibration_manager.open_calibration_guide()

    def _open_quick_calibrate(self) -> None:
        self._calibration_manager.open_quick_calibrate()

    def _open_plate_calibrate(self) -> None:
        self._calibration_manager.open_plate_calibrate()

    def _update_calib_summary(self) -> None:
        self._calibration_manager.update_calib_summary()

    def _open_checklist(self) -> None:
        dialog = ChecklistDialog(self)
        dialog.exec()

    def _open_record_settings(self) -> None:
        dialog = RecordingSettingsDialog(
            self,
            session=self._session_name.text(),
            output_dir=self._output_dir.text(),
            speed_mph=self._manual_speed.value(),
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            session, output_dir, speed = dialog.values()
            self._session_name.setText(session)
            self._set_output_dir(output_dir)
            self._manual_speed.setValue(speed)
            self._set_manual_speed(speed)

    def _open_strike_settings(self) -> None:
        values = self._settings_manager.get_strike_dialog_values()
        dialog = StrikeZoneSettingsDialog(
            self,
            ball_type=values["ball_type"],
            batter_height=values["batter_height"],
            top_ratio=values["top_ratio"],
            bottom_ratio=values["bottom_ratio"],
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            ball_type, height, top_ratio, bottom_ratio = dialog.values()
            self._settings_manager.update_strike_settings(
                ball_type, height, top_ratio, bottom_ratio
            )
            self._save_strike_zone()

    def _open_detector_settings(self) -> None:
        values = self._settings_manager.get_detector_dialog_values()
        dialog = DetectorSettingsDialog(
            self,
            mode=values["mode"],
            frame_diff=values["frame_diff"],
            bg_diff=values["bg_diff"],
            bg_alpha=values["bg_alpha"],
            edge_thresh=values["edge_thresh"],
            blob_thresh=values["blob_thresh"],
            min_area=values["min_area"],
            min_circ=values["min_circ"],
            threading_mode=values["threading_mode"],
            worker_count=values["worker_count"],
            detector_type=values["detector_type"],
            model_path=values["model_path"],
            model_input_size=values["model_input_size"],
            model_conf_threshold=values["model_conf_threshold"],
            model_class_id=values["model_class_id"],
            model_format=values["model_format"],
        )
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            values = dialog.values()
            self._settings_manager.update_detector_settings(values)
            self._apply_detector_config()

    def _show_keyboard_shortcuts(self) -> None:
        shortcuts_path = Path("docs/KEYBOARD_SHORTCUTS.md")
        if not shortcuts_path.exists():
            show_message_dialog(
                self,
                "Keyboard Shortcuts",
                "Keyboard shortcuts documentation not found.\n\n"
                "Expected location: docs/KEYBOARD_SHORTCUTS.md",
                tone="info",
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(shortcuts_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", shortcuts_path], check=True)
            else:
                subprocess.run(["xdg-open", shortcuts_path], check=True)
        except Exception as exc:
            show_message_dialog(
                self,
                "Keyboard Shortcuts",
                f"Failed to open shortcuts documentation: {exc}\n\n"
                f"File location: {shortcuts_path.absolute()}",
                tone="warning",
            )

    def _show_about(self) -> None:
        git_commit = self._get_git_commit()
        version_text = f"PitchTracker v{APP_VERSION}"
        if git_commit:
            version_text += f"\nCommit: {git_commit}"

        about_text = (
            f"{version_text}\n"
            f"Schema: {SCHEMA_VERSION}\n\n"
            "A high-speed stereo vision system for baseball/softball pitch tracking.\n\n"
            "Features:\n"
            "  • 60 FPS stereo video capture\n"
            "  • Real-time ball detection and tracking\n"
            "  • Physics-based trajectory fitting\n"
            "  • Strike zone analysis\n"
            "  • Session recording and replay\n\n"
            "Documentation: docs/\n"
            "Issues: github.com/berginj/PitchTracker/issues"
        )

        show_message_dialog(self, "About PitchTracker", about_text, tone="info")

    def _set_target_overlay(self, enabled: bool) -> None:
        self._calibration_overlay.set_target_overlay(enabled)

    def _set_fiducial_overlay(self, enabled: bool) -> None:
        self._calibration_overlay.set_fiducial_overlay(enabled)

    def _propose_right_lane(self) -> None:
        lane_rect = self._roi_manager.lane_rect
        if lane_rect is None:
            show_message_dialog(
                self,
                "Propose Right Lane",
                "Draw the left lane ROI first.",
                tone="info",
            )
            return
        with self._latest_lock:
            left_frame = self._left_latest
            right_frame = self._right_latest
        if left_frame is None or right_frame is None:
            show_message_dialog(
                self,
                "Propose Right Lane",
                "Start capture before proposing the right lane.",
                tone="warning",
            )
            return
        left_w, left_h = left_frame.width, left_frame.height
        right_w, right_h = right_frame.width, right_frame.height
        x1, y1, x2, y2 = lane_rect
        nx1 = x1 / max(left_w, 1)
        ny1 = y1 / max(left_h, 1)
        nx2 = x2 / max(left_w, 1)
        ny2 = y2 / max(left_h, 1)
        rx1 = int(nx1 * right_w)
        ry1 = int(ny1 * right_h)
        rx2 = int(nx2 * right_w)
        ry2 = int(ny2 * right_h)
        shift = 0.0
        try:
            detections = self._service.get_latest_detections()
            left_id = self._device_manager.get_left_serial()
            right_id = self._device_manager.get_right_serial()
            left_dets = detections.get(left_id, [])
            right_dets = detections.get(right_id, [])
            if left_dets and right_dets:
                left_mean = sum(det.u for det in left_dets) / len(left_dets)
                right_mean = sum(det.u for det in right_dets) / len(right_dets)
                shift = right_mean - left_mean
        except Exception:
            shift = 0.0
        rx1 = int(rx1 + shift)
        rx2 = int(rx2 + shift)
        rx1 = max(0, min(rx1, right_w - 1))
        rx2 = max(0, min(rx2, right_w - 1))
        self._roi_manager.lane_rect_right = (rx1, ry1, rx2, ry2)
        self._status_label.setText("Proposed right lane ROI.")

    def _maybe_show_guide(self) -> None:
        marker = Path("configs/.first_run_done")
        if marker.exists():
            return
        QtCore.QTimer.singleShot(300, self._open_calibration_guide)
        try:
            marker.write_text("ok")
        except OSError:
            pass
