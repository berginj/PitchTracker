"""Export routing controller for ReviewWindow."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6 import QtWidgets

from app.review import ReviewService
from ui.themes import show_message_dialog

logger = logging.getLogger(__name__)


class ExportController:
    """Routes config and annotation export operations."""

    def __init__(
        self,
        service: ReviewService,
        *,
        parent_widget: QtWidgets.QWidget,
        get_pitch_scores: callable,
    ) -> None:
        self._service = service
        self._parent = parent_widget
        self._get_pitch_scores = get_pitch_scores

    def export_config(self) -> None:
        """Export tuned detector configuration."""
        if not self._service.session:
            show_message_dialog(self._parent, "No Session", "Please load a session first.", tone="warning")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._parent,
            "Export Detector Config",
            "config_tuned.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            self._service.export_config(Path(file_path))
            show_message_dialog(
                self._parent,
                "Export Successful",
                f"Detector configuration exported to:\n{file_path}",
                tone="success",
            )
            logger.info(f"Exported config to {file_path}")
        except Exception as e:
            logger.exception(f"Failed to export config: {e}")
            show_message_dialog(self._parent, "Export Error", f"Failed to export config:\n{str(e)}", tone="error")

    def export_annotations(self) -> None:
        """Export annotations to JSON file."""
        if not self._service.session:
            show_message_dialog(self._parent, "No Session", "Please load a session first.", tone="warning")
            return

        # Sync pitch scores from UI to service
        pitch_scores = self._get_pitch_scores()
        for pitch_id, score in pitch_scores.items():
            self._service.score_pitch(pitch_id, score)

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._parent,
            "Export Annotations",
            "annotations.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            self._service.export_annotations(Path(file_path))

            summary = self._service.get_pitch_score_summary()
            stats_text = (
                f"Annotations exported to:\n{file_path}\n\n"
                f"Statistics:\n"
                f"Good: {summary['good']}\n"
                f"Partial: {summary['partial']}\n"
                f"Missed: {summary['missed']}\n"
                f"Unscored: {summary['unscored']}"
            )

            show_message_dialog(self._parent, "Export Successful", stats_text, tone="success")
            logger.info(f"Exported annotations to {file_path}")
        except Exception as e:
            logger.exception(f"Failed to export annotations: {e}")
            show_message_dialog(
                self._parent, "Export Error", f"Failed to export annotations:\n{str(e)}", tone="error"
            )
