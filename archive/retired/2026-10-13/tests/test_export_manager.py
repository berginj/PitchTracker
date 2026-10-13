"""Unit tests for ExportManager controller.

Tests the extracted ExportManager class from MainWindow refactoring.
Covers session export and upload workflows.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ui.controllers.export_manager import ExportManager


class TestExportManagerInit:
    """Tests for ExportManager initialization."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for ExportManager."""
        return {
            "parent": Mock(),
            "config_path": tmp_path / "config.yaml",
            "roi_path": tmp_path / "rois.json",
            "get_config": Mock(),
            "get_session_dir": Mock(return_value=tmp_path / "session"),
            "get_pitcher_name": Mock(return_value="John Doe"),
            "get_location_profile": Mock(return_value="Home Field"),
        }

    def test_initialization(self, mock_deps):
        """ExportManager should initialize with provided dependencies."""
        em = ExportManager(**mock_deps)
        assert em._parent is mock_deps["parent"]
        assert em._config_path == mock_deps["config_path"]
        assert em._roi_path == mock_deps["roi_path"]


class TestUploadSession:
    """Tests for session upload functionality."""

    @pytest.fixture
    def export_manager(self, tmp_path):
        """Create ExportManager with mocked dependencies."""
        mock_config = Mock()
        return ExportManager(
            parent=Mock(),
            config_path=tmp_path / "config.yaml",
            roi_path=tmp_path / "rois.json",
            get_config=Mock(return_value=mock_config),
            get_session_dir=Mock(return_value=tmp_path / "session"),
            get_pitcher_name=Mock(return_value="John Doe"),
            get_location_profile=Mock(return_value="Home Field"),
        )

    @patch("ui.controllers.export_manager.upload_session")
    def test_upload_session_calls_export_function(self, mock_upload, export_manager):
        """upload_session should delegate to ui.export.upload_session."""
        mock_summary = Mock()

        export_manager.upload_session(mock_summary)

        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["summary"] is mock_summary
        assert call_kwargs["pitcher_name"] == "John Doe"
        assert call_kwargs["location_profile"] == "Home Field"

    @patch("ui.controllers.export_manager.upload_session")
    def test_upload_session_handles_none_pitcher(self, mock_upload, tmp_path):
        """upload_session should handle None pitcher name."""
        em = ExportManager(
            parent=Mock(),
            config_path=tmp_path / "config.yaml",
            roi_path=tmp_path / "rois.json",
            get_config=Mock(),
            get_session_dir=Mock(return_value=None),
            get_pitcher_name=Mock(return_value=None),
            get_location_profile=Mock(return_value=None),
        )
        mock_summary = Mock()

        em.upload_session(mock_summary)

        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["pitcher_name"] == ""
        assert call_kwargs["location_profile"] == ""


class TestSaveExport:
    """Tests for session export functionality."""

    @pytest.fixture
    def export_manager(self, tmp_path):
        """Create ExportManager with mocked dependencies."""
        return ExportManager(
            parent=Mock(),
            config_path=tmp_path / "config.yaml",
            roi_path=tmp_path / "rois.json",
            get_config=Mock(),
            get_session_dir=Mock(return_value=tmp_path / "session"),
            get_pitcher_name=Mock(return_value="Jane Doe"),
            get_location_profile=Mock(return_value="Away Field"),
        )

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_json(self, mock_save, export_manager):
        """save_export should delegate to ui.export.save_session_export for JSON."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, "summary_json")

        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["summary"] is mock_summary
        assert call_kwargs["export_type"] == "summary_json"
        assert call_kwargs["pitcher_name"] == "Jane Doe"
        assert call_kwargs["location_profile"] == "Away Field"

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_csv(self, mock_save, export_manager):
        """save_export should handle CSV export type."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, "summary_csv")

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["export_type"] == "summary_csv"

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_training_report(self, mock_save, export_manager):
        """save_export should handle training report export type."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, "training_report")

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["export_type"] == "training_report"

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_manifests_zip(self, mock_save, export_manager):
        """save_export should handle manifests zip export type."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, "manifests_zip")

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["export_type"] == "manifests_zip"

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_none_type(self, mock_save, export_manager):
        """save_export should handle None export type."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, None)

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["export_type"] is None

    @patch("ui.controllers.export_manager.save_session_export")
    def test_save_export_passes_config_and_roi_paths(self, mock_save, export_manager, tmp_path):
        """save_export should pass config_path and roi_path."""
        mock_summary = Mock()

        export_manager.save_export(mock_summary, "summary_json")

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["config_path"] == tmp_path / "config.yaml"
        assert call_kwargs["roi_path"] == tmp_path / "rois.json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
