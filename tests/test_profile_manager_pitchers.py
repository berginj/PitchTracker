"""Tests for ProfileManager pitcher and selection behavior."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ui.controllers.profile_manager import ProfileManager


class TestAddPitcher:
    """Tests for pitcher addition."""

    @pytest.fixture
    def profile_manager(self):
        """Create ProfileManager with mocked widgets."""
        pm = ProfileManager(
            profile_combo=Mock(),
            profile_name_input=Mock(),
            pitcher_combo=Mock(),
            pitcher_name_input=Mock(),
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            roi_path=Path("/tmp/test.json"),
        )
        return pm

    def test_add_pitcher_empty_name(self, profile_manager):
        """add_pitcher should return False for empty name."""
        profile_manager._pitcher_name_input.text.return_value = ""

        result = profile_manager.add_pitcher()

        assert result is False

    @patch("ui.controllers.profile_manager.save_state")
    @patch("ui.controllers.profile_manager.load_state")
    @patch("ui.controllers.profile_manager.add_pitcher")
    def test_add_pitcher_success(self, mock_add, mock_load_state, mock_save_state, profile_manager):
        """add_pitcher should add valid pitcher."""
        profile_manager._pitcher_name_input.text.return_value = "John Doe"
        mock_add.return_value = ["John Doe", "Jane Doe"]
        mock_load_state.return_value = {}

        result = profile_manager.add_pitcher()

        assert result is True
        mock_add.assert_called_once_with("John Doe")
        profile_manager._pitcher_combo.setCurrentText.assert_called_with("John Doe")
        profile_manager._pitcher_name_input.clear.assert_called_once()


class TestSetPitcher:
    """Tests for pitcher selection."""

    @pytest.fixture
    def profile_manager(self):
        """Create ProfileManager with mocked widgets."""
        pm = ProfileManager(
            profile_combo=Mock(),
            profile_name_input=Mock(),
            pitcher_combo=Mock(),
            pitcher_name_input=Mock(),
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            roi_path=Path("/tmp/test.json"),
        )
        return pm

    @patch("ui.controllers.profile_manager.save_state")
    @patch("ui.controllers.profile_manager.load_state")
    def test_set_pitcher_updates_state(self, mock_load, mock_save, profile_manager):
        """set_pitcher should save selection to app state."""
        mock_load.return_value = {}

        profile_manager.set_pitcher("John Doe")

        assert profile_manager.pitcher_name == "John Doe"
        mock_save.assert_called_once()
        saved_state = mock_save.call_args[0][0]
        assert saved_state["last_pitcher"] == "John Doe"

    def test_set_pitcher_empty_clears_state(self, profile_manager):
        """set_pitcher with empty name should clear pitcher."""
        profile_manager.set_pitcher("")

        assert profile_manager.pitcher_name is None

    def test_set_pitcher_strips_whitespace(self, profile_manager):
        """set_pitcher should strip whitespace from name."""
        profile_manager.set_pitcher("  ")

        assert profile_manager.pitcher_name is None


class TestApplyStartupSelection:
    """Tests for startup selection application."""

    @pytest.fixture
    def profile_manager(self):
        """Create ProfileManager with mocked widgets."""
        pm = ProfileManager(
            profile_combo=Mock(),
            profile_name_input=Mock(),
            pitcher_combo=Mock(),
            pitcher_name_input=Mock(),
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            roi_path=Path("/tmp/test.json"),
        )
        return pm

    @patch("ui.controllers.profile_manager.add_pitcher")
    def test_apply_startup_with_both(self, mock_add, profile_manager):
        """apply_startup_selection should set both profile and pitcher."""
        profile_manager.apply_startup_selection("HomeField", "John")

        assert profile_manager.location_profile == "HomeField"
        assert profile_manager.pitcher_name == "John"
        profile_manager._profile_combo.setCurrentText.assert_called_with("HomeField")
        profile_manager._pitcher_combo.setCurrentText.assert_called_with("John")

    @patch("ui.controllers.profile_manager.add_pitcher")
    def test_apply_startup_profile_only(self, mock_add, profile_manager):
        """apply_startup_selection should handle profile only."""
        profile_manager.apply_startup_selection("HomeField", None)

        assert profile_manager.location_profile == "HomeField"
        assert profile_manager.pitcher_name is None

    def test_apply_startup_pitcher_only(self, profile_manager):
        """apply_startup_selection should handle pitcher only."""
        with patch("ui.controllers.profile_manager.add_pitcher"):
            profile_manager.apply_startup_selection(None, "John")

        assert profile_manager.location_profile is None
        assert profile_manager.pitcher_name == "John"


class TestSetComboByData:
    """Tests for the _set_combo_by_data helper method."""

    @pytest.fixture
    def profile_manager(self):
        """Create ProfileManager with mocked widgets."""
        pm = ProfileManager(
            profile_combo=Mock(),
            profile_name_input=Mock(),
            pitcher_combo=Mock(),
            pitcher_name_input=Mock(),
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            roi_path=Path("/tmp/test.json"),
        )
        return pm

    def test_set_combo_empty_value(self, profile_manager):
        """_set_combo_by_data should return False for empty value."""
        combo = Mock()

        result = profile_manager._set_combo_by_data(combo, "")

        assert result is False

    def test_set_combo_finds_by_data(self, profile_manager):
        """_set_combo_by_data should find item by data value."""
        combo = Mock()
        combo.count.return_value = 3
        combo.itemData.side_effect = ["111", "222", "333"]

        result = profile_manager._set_combo_by_data(combo, "222")

        assert result is True
        combo.setCurrentIndex.assert_called_with(1)

    def test_set_combo_fallback_to_text(self, profile_manager):
        """_set_combo_by_data should fallback to setCurrentText if not found."""
        combo = Mock()
        combo.count.return_value = 2
        combo.itemData.side_effect = ["111", "222"]

        result = profile_manager._set_combo_by_data(combo, "999")

        assert result is False
        combo.setCurrentText.assert_called_with("999")
