"""Session export management controller.

Extracted from MainWindow to reduce god class complexity.
Manages session data export and upload workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

from PySide6 import QtWidgets

from ui.export import (
    upload_session,
    save_session_export,
)
from log_config.logger import get_logger

if TYPE_CHECKING:
    from configs.settings import AppConfig

logger = get_logger(__name__)


class ExportManager:
    """Manages session export and upload workflows.

    Responsibilities:
    - Uploading session data to remote API
    - Exporting session summaries (JSON, CSV)
    - Exporting training reports
    - Exporting manifest archives
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config_path: Path,
        roi_path: Path,
        get_config: Callable[[], "AppConfig"],
        get_session_dir: Callable[[], Optional[Path]],
        get_pitcher_name: Callable[[], Optional[str]],
        get_location_profile: Callable[[], Optional[str]],
    ):
        """Initialize export manager.

        Args:
            parent: Parent widget for dialogs
            config_path: Path to configuration file
            roi_path: Path to ROI configuration file
            get_config: Callback to get current config
            get_session_dir: Callback to get current session directory
            get_pitcher_name: Callback to get current pitcher name
            get_location_profile: Callback to get current location profile
        """
        self._parent = parent
        self._config_path = config_path
        self._roi_path = roi_path
        self._get_config = get_config
        self._get_session_dir = get_session_dir
        self._get_pitcher_name = get_pitcher_name
        self._get_location_profile = get_location_profile

        logger.debug(f"ExportManager initialized with config path: {config_path}")

    def upload_session(self, summary) -> None:
        """Upload session data to remote API.

        Args:
            summary: Session summary data to upload
        """
        config = self._get_config()
        session_dir = self._get_session_dir()
        pitcher = self._get_pitcher_name() or ""
        profile = self._get_location_profile() or ""

        logger.info(f"Uploading session (pitcher={pitcher}, profile={profile})")

        upload_session(
            parent=self._parent,
            summary=summary,
            config=config,
            session_dir=session_dir,
            pitcher_name=pitcher,
            location_profile=profile,
        )

    def save_export(self, summary, export_type: Optional[str]) -> None:
        """Save session export in specified format.

        Args:
            summary: Session summary data
            export_type: Export format (summary_json, summary_csv, training_report, manifests_zip)
        """
        session_dir = self._get_session_dir()
        pitcher = self._get_pitcher_name() or ""
        profile = self._get_location_profile() or ""

        logger.info(f"Exporting session as {export_type} (pitcher={pitcher})")

        save_session_export(
            parent=self._parent,
            summary=summary,
            session_dir=session_dir,
            export_type=export_type,
            config_path=self._config_path,
            roi_path=self._roi_path,
            pitcher_name=pitcher,
            location_profile=profile,
        )
