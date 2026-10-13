"""Unit tests for GameVisualizer controller.

Tests the extracted GameVisualizer class from MainWindow refactoring.
Covers tic-tac-toe game logic and plate map visualization.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ui.controllers.game_visualizer import GameVisualizer, _tic_tac_toe_winner


class TestTicTacToeWinner:
    """Tests for _tic_tac_toe_winner helper function."""

    def test_winner_row(self):
        """Should detect row winner."""
        board = [["X", "X", "X"], ["", "", ""], ["", "", ""]]
        assert _tic_tac_toe_winner(board) == "X"

    def test_winner_column(self):
        """Should detect column winner."""
        board = [["O", "", ""], ["O", "", ""], ["O", "", ""]]
        assert _tic_tac_toe_winner(board) == "O"

    def test_winner_diagonal(self):
        """Should detect diagonal winner."""
        board = [["X", "", ""], ["", "X", ""], ["", "", "X"]]
        assert _tic_tac_toe_winner(board) == "X"

    def test_winner_anti_diagonal(self):
        """Should detect anti-diagonal winner."""
        board = [["", "", "O"], ["", "O", ""], ["O", "", ""]]
        assert _tic_tac_toe_winner(board) == "O"

    def test_draw(self):
        """Should detect draw when board is full with no winner."""
        board = [["X", "O", "X"], ["X", "O", "O"], ["O", "X", "X"]]
        assert _tic_tac_toe_winner(board) == "draw"

    def test_ongoing_game(self):
        """Should return None for ongoing game."""
        board = [["X", "", ""], ["", "O", ""], ["", "", ""]]
        assert _tic_tac_toe_winner(board) is None


class TestGameVisualizerInit:
    """Tests for GameVisualizer initialization."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies for GameVisualizer."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        return {
            "plate_map": Mock(),
            "status_label": Mock(),
            "score_label": Mock(),
            "streak_label": Mock(),
            "get_config": Mock(return_value=config),
            "get_pitch_paths": Mock(return_value=[]),
            "build_strike_zone": Mock(return_value=Mock()),
        }

    def test_initialization(self, mock_deps):
        """GameVisualizer should initialize with provided dependencies."""
        gv = GameVisualizer(**mock_deps)
        assert gv.board == [["", "", ""], ["", "", ""], ["", "", ""]]
        assert gv.target_mode is False

    def test_board_starts_empty(self, mock_deps):
        """Board should be empty on initialization."""
        gv = GameVisualizer(**mock_deps)
        for row in gv.board:
            for cell in row:
                assert cell == ""


class TestResetGame:
    """Tests for game reset functionality."""

    @pytest.fixture
    def game_visualizer(self):
        """Create GameVisualizer with mocked dependencies."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        return GameVisualizer(
            plate_map=Mock(),
            status_label=Mock(),
            score_label=Mock(),
            streak_label=Mock(),
            get_config=Mock(return_value=config),
            get_pitch_paths=Mock(return_value=[]),
            build_strike_zone=Mock(return_value=Mock()),
        )

    def test_reset_clears_board(self, game_visualizer):
        """reset_game should clear the board."""
        # Play some moves
        game_visualizer._board[0][0] = "X"
        game_visualizer._board[1][1] = "O"

        game_visualizer.reset_game()

        for row in game_visualizer.board:
            for cell in row:
                assert cell == ""

    def test_reset_clears_scores(self, game_visualizer):
        """reset_game should reset scores."""
        game_visualizer._score_x = 5
        game_visualizer._score_o = 3
        game_visualizer._round = 8
        game_visualizer._streak = 2

        game_visualizer.reset_game()

        assert game_visualizer._score_x == 0
        assert game_visualizer._score_o == 0
        assert game_visualizer._round == 0
        assert game_visualizer._streak == 0

    def test_reset_updates_ui(self, game_visualizer):
        """reset_game should update UI elements."""
        game_visualizer.reset_game()

        game_visualizer._status_label.setText.assert_called_with("Ready.")
        game_visualizer._plate_map.set_board.assert_called()
        game_visualizer._plate_map.set_target_cell.assert_called_with(None)


class TestTargetMode:
    """Tests for target mode functionality."""

    @pytest.fixture
    def game_visualizer(self):
        """Create GameVisualizer with mocked dependencies."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        return GameVisualizer(
            plate_map=Mock(),
            status_label=Mock(),
            score_label=Mock(),
            streak_label=Mock(),
            get_config=Mock(return_value=config),
            get_pitch_paths=Mock(return_value=[]),
            build_strike_zone=Mock(return_value=Mock()),
        )

    def test_enable_target_mode(self, game_visualizer):
        """set_target_mode should enable target mode."""
        game_visualizer.set_target_mode(True)

        assert game_visualizer.target_mode is True
        game_visualizer._status_label.setText.assert_called_with("Hit the highlighted target.")
        game_visualizer._plate_map.set_target_cell.assert_called()

    def test_disable_target_mode(self, game_visualizer):
        """set_target_mode should disable target mode."""
        game_visualizer.set_target_mode(True)
        game_visualizer.set_target_mode(False)

        assert game_visualizer.target_mode is False
        game_visualizer._plate_map.set_target_cell.assert_called_with(None)


class TestUpdatePlateMapZone:
    """Tests for plate map zone updates."""

    @pytest.fixture
    def game_visualizer(self):
        """Create GameVisualizer with mocked dependencies."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        mock_zone = Mock()
        return GameVisualizer(
            plate_map=Mock(),
            status_label=Mock(),
            score_label=Mock(),
            streak_label=Mock(),
            get_config=Mock(return_value=config),
            get_pitch_paths=Mock(return_value=[]),
            build_strike_zone=Mock(return_value=mock_zone),
        )

    def test_update_plate_map_zone(self, game_visualizer):
        """update_plate_map_zone should call build_strike_zone and set_zone."""
        game_visualizer.update_plate_map_zone()

        game_visualizer._build_strike_zone.assert_called_once()
        game_visualizer._plate_map.set_zone.assert_called_once()


class TestUpdatePlateMap:
    """Tests for plate map updates."""

    @pytest.fixture
    def game_visualizer(self):
        """Create GameVisualizer with mocked dependencies."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        return GameVisualizer(
            plate_map=Mock(),
            status_label=Mock(),
            score_label=Mock(),
            streak_label=Mock(),
            get_config=Mock(return_value=config),
            get_pitch_paths=Mock(return_value=["path1", "path2"]),
            build_strike_zone=Mock(return_value=Mock()),
        )

    def test_update_plate_map_no_pitches(self, game_visualizer):
        """update_plate_map should handle empty pitch list."""
        summary = Mock()
        summary.pitches = []

        game_visualizer.update_plate_map(summary)

        game_visualizer._plate_map.set_pitch_paths.assert_called()
        game_visualizer._plate_map.set_crossing_point.assert_called_with(None)

    def test_update_plate_map_with_pitch(self, game_visualizer):
        """update_plate_map should process new pitch."""
        pitch = Mock()
        pitch.pitch_id = "test123"
        pitch.zone_row = 2
        pitch.zone_col = 2
        pitch.trajectory_plate_x_ft = 0.5
        pitch.trajectory_plate_y_ft = 2.5

        summary = Mock()
        summary.pitches = [pitch]

        game_visualizer.update_plate_map(summary)

        game_visualizer._plate_map.set_pitch_paths.assert_called()
        game_visualizer._plate_map.set_crossing_point.assert_called_with((0.5, 2.5))


class TestApplyPitchToTicTacToe:
    """Tests for pitch application to game."""

    @pytest.fixture
    def game_visualizer(self):
        """Create GameVisualizer with mocked dependencies."""
        config = Mock()
        config.metrics.plate_plane_z_ft = 0.0
        config.strike_zone.plate_width_in = 17.0
        config.strike_zone.plate_length_in = 17.0
        config.strike_zone.batter_height_in = 72.0
        config.strike_zone.top_ratio = 0.55
        config.strike_zone.bottom_ratio = 0.28

        return GameVisualizer(
            plate_map=Mock(),
            status_label=Mock(),
            score_label=Mock(),
            streak_label=Mock(),
            get_config=Mock(return_value=config),
            get_pitch_paths=Mock(return_value=[]),
            build_strike_zone=Mock(return_value=Mock()),
        )

    def test_pitch_marks_x(self, game_visualizer):
        """Pitch in valid zone should mark X."""
        pitch = Mock()
        pitch.zone_row = 2
        pitch.zone_col = 2

        game_visualizer._apply_pitch_to_tic_tac_toe(pitch)

        assert game_visualizer._board[1][1] == "X"

    def test_pitch_out_of_zone_marks_ai(self, game_visualizer):
        """Pitch outside zone should trigger AI move."""
        pitch = Mock()
        pitch.zone_row = None
        pitch.zone_col = None

        game_visualizer._apply_pitch_to_tic_tac_toe(pitch)

        # AI should have marked a cell
        o_count = sum(1 for row in game_visualizer._board for cell in row if cell == "O")
        assert o_count == 1

    def test_occupied_cell_marks_ai(self, game_visualizer):
        """Pitch in occupied cell should trigger AI move."""
        game_visualizer._board[1][1] = "X"

        pitch = Mock()
        pitch.zone_row = 2
        pitch.zone_col = 2

        game_visualizer._apply_pitch_to_tic_tac_toe(pitch)

        # AI should have marked another cell
        o_count = sum(1 for row in game_visualizer._board for cell in row if cell == "O")
        assert o_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
