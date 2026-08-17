"""Recording lifecycle management controller.

Extracted from MainWindow to reduce god class complexity.
Manages recording start/stop and training capture.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

import yaml
from PySide6 import QtWidgets

from log_config.logger import get_logger
from ui.dialogs.session_summary_dialog import SessionSummaryDialog
from ui.export import upload_session, save_session_export
from ui.themes import show_message_dialog

if TYPE_CHECKING:
    from app.contracts import SessionSummary
    from configs.settings import AppConfig

logger = get_logger(__name__)


class RecordingController:
    """Manages recording lifecycle.

    Responsibilities:
    - Starting and stopping recording sessions
    - Training capture mode
    - Output directory management
    - Manual speed override
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        status_label: QtWidgets.QLabel,
        get_config: Callable[[], "AppConfig"],
        get_config_path: Callable[[], Path],
        get_session_name: Callable[[], str],
        set_session_name: Callable[[str], None],
        get_output_dir: Callable[[], str],
        set_output_dir_widget: Callable[[str], None],
        get_roi_path: Callable[[], Path],
        get_pitcher_name: Callable[[], Optional[str]],
        get_location_profile: Callable[[], Optional[str]],
        health_check: Callable[[], bool],
        start_recording_service: Callable[[str, str], object],
        stop_recording_service: Callable[[], object],
        set_record_directory: Callable[[Path], None],
        set_manual_speed_mph: Callable[[Optional[float]], None],
        get_session_summary: Callable[[], "SessionSummary"],
        get_session_dir: Callable[[], Optional[Path]],
    ):
        """Initialize recording controller.

        Args:
            parent: Parent widget for dialogs
            status_label: Label for status messages
            get_config: Callback to get current config
            get_config_path: Callback to get config file path
            get_session_name: Callback to get session name text
            set_session_name: Callback to set session name text
            get_output_dir: Callback to get output directory text
            set_output_dir_widget: Callback to set output directory widget text
            get_roi_path: Callback to get ROI file path
            get_pitcher_name: Callback to get current pitcher name
            get_location_profile: Callback to get current location profile
            health_check: Callback to check system health
            start_recording_service: Callback to start recording (session_name, mode)
            stop_recording_service: Callback to stop recording
            set_record_directory: Callback to set recording directory
            set_manual_speed_mph: Callback to set manual speed
            get_session_summary: Callback to get session summary
            get_session_dir: Callback to get session directory
        """
        self._parent = parent
        self._status_label = status_label
        self._get_config = get_config
        self._get_config_path = get_config_path
        self._get_session_name = get_session_name
        self._set_session_name = set_session_name
        self._get_output_dir = get_output_dir
        self._set_output_dir_widget = set_output_dir_widget
        self._get_roi_path = get_roi_path
        self._get_pitcher_name = get_pitcher_name
        self._get_location_profile = get_location_profile
        self._health_check = health_check
        self._start_recording_service = start_recording_service
        self._stop_recording_service = stop_recording_service
        self._set_record_directory = set_record_directory
        self._set_manual_speed_mph = set_manual_speed_mph
        self._get_session_summary = get_session_summary
        self._get_session_dir = get_session_dir

        logger.debug("RecordingController initialized")

    def default_session_name(self) -> str:
        """Generate default session name.

        Returns:
            Session name in format: pitcher-YYYYMMDD-HHMMSS
        """
        pitcher = self._get_pitcher_name() or "pitcher"
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        return f"{pitcher}-{timestamp}"

    def start_recording(self) -> bool:
        """Start recording session.

        Returns:
            True if recording started successfully, False otherwise
        """
        if not self._health_check():
            show_message_dialog(
                self._parent,
                "Health Check",
                "Health check failed. Verify FPS and drops before recording.",
                tone="warning",
            )
            return False

        session = self._get_session_name().strip() or self.default_session_name()
        if session:
            self._set_session_name(session)

        self._start_recording_service(session, "review")
        self._status_label.setText("Recording...")
        logger.info(f"Recording started: session={session}")
        return True

    def stop_recording(self) -> None:
        """Stop recording and show summary dialog."""
        self._stop_recording_service()
        summary = self._get_session_summary()
        self._status_label.setText(f"Recorded pitches: {summary.pitch_count}")
        session_dir = self._get_session_dir()

        pitcher_name = self._get_pitcher_name() or "Unknown"
        location_profile = self._get_location_profile() or "Unknown"
        config = self._get_config()
        config_path = self._get_config_path()
        roi_path = self._get_roi_path()

        dialog = SessionSummaryDialog(
            self._parent,
            summary,
            lambda: upload_session(
                self._parent,
                summary,
                config,
                session_dir,
                pitcher_name,
                location_profile,
            ),
            lambda export_type: save_session_export(
                self._parent,
                summary,
                session_dir,
                export_type,
                config_path,
                roi_path,
                pitcher_name,
                location_profile,
            ),
            session_dir=session_dir,
        )
        dialog.exec()
        logger.info(f"Recording stopped: {summary.pitch_count} pitches")

    def start_training_capture(self) -> bool:
        """Start training capture mode.

        Returns:
            True if training capture started successfully, False otherwise
        """
        if not self._health_check():
            show_message_dialog(
                self._parent,
                "Health Check",
                "Health check failed. Verify FPS and drops before recording.",
                tone="warning",
            )
            return False

        session = self._get_session_name().strip() or self.default_session_name()
        if session:
            self._set_session_name(session)

        if not session:
            show_message_dialog(
                self._parent,
                "Training Capture",
                "Set a session name before starting training capture.",
                tone="info",
            )
            return False

        self._start_recording_service(session, "training")
        self._status_label.setText("Training capture...")
        logger.info(f"Training capture started: session={session}")
        return True

    def browse_output(self) -> Optional[str]:
        """Browse for output directory.

        Returns:
            Selected path if chosen, None otherwise
        """
        path = QtWidgets.QFileDialog.getExistingDirectory(self._parent, "Select output folder")
        if path:
            self.set_output_dir(path)
            return path
        return None

    def set_output_dir(self, path: str) -> None:
        """Set output directory and save to config.

        Args:
            path: Directory path
        """
        if not path:
            return

        self._set_output_dir_widget(path)
        self._set_record_directory(Path(path))

        config_path = self._get_config_path()
        data = yaml.safe_load(config_path.read_text())
        data.setdefault("recording", {})
        data["recording"]["output_dir"] = path
        config_path.write_text(yaml.safe_dump(data, sort_keys=False))
        logger.debug(f"Output directory set: {path}")

    def set_manual_speed(self, value: float) -> None:
        """Set manual speed override.

        Args:
            value: Speed in mph, or 0 to disable override
        """
        speed = value if value > 0 else None
        self._set_manual_speed_mph(speed)
        logger.debug(f"Manual speed set: {speed}")
