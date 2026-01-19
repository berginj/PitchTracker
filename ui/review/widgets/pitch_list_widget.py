"""Pitch list widget with scoring functionality."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.review import PitchScore


class PitchListWidget(QtWidgets.QWidget):
    """Widget displaying list of pitches with scoring.

    Shows all pitches in the session with:
    - Pitch ID and metrics
    - Score buttons (Good/Partial/Missed)
    - Navigation to pitch
    - Statistics summary

    Signals:
        pitch_selected: Emitted when user clicks "Go to Pitch" (int pitch_index)
        pitch_scored: Emitted when pitch is scored (str pitch_id, PitchScore score)
    """

    # Signals
    pitch_selected = QtCore.Signal(int)
    pitch_scored = QtCore.Signal(str, PitchScore)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize pitch list widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        self._pitches = []
        self._pitch_scores = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Build pitch list UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Pitch List")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Pitch list (scrollable)
        self._pitch_list = QtWidgets.QListWidget()
        self._pitch_list.setAlternatingRowColors(True)
        self._pitch_list.currentRowChanged.connect(self._on_pitch_selection_changed)
        layout.addWidget(self._pitch_list, 1)  # Takes most space

        # Scoring buttons
        scoring_group = self._build_scoring_controls()
        layout.addWidget(scoring_group)

        # Statistics summary
        stats_group = self._build_statistics_panel()
        layout.addWidget(stats_group)

        # Navigation button
        nav_btn = QtWidgets.QPushButton("Go to Selected Pitch")
        nav_btn.setStyleSheet("font-weight: bold; background-color: #2196F3; color: white;")
        nav_btn.clicked.connect(self._on_go_to_pitch)
        layout.addWidget(nav_btn)

        self.setLayout(layout)
        self.setMaximumWidth(350)

    def _build_scoring_controls(self) -> QtWidgets.QGroupBox:
        """Build scoring button controls.

        Returns:
            Group box with scoring buttons
        """
        group = QtWidgets.QGroupBox("Score Selected Pitch")

        self._good_btn = QtWidgets.QPushButton("✓ Good")
        self._good_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self._good_btn.clicked.connect(lambda: self._score_current_pitch(PitchScore.GOOD))
        self._good_btn.setToolTip("Detection worked perfectly")

        self._partial_btn = QtWidgets.QPushButton("⚠ Partial")
        self._partial_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self._partial_btn.clicked.connect(lambda: self._score_current_pitch(PitchScore.PARTIAL))
        self._partial_btn.setToolTip("Some frames detected, some missed")

        self._missed_btn = QtWidgets.QPushButton("✗ Missed")
        self._missed_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self._missed_btn.clicked.connect(lambda: self._score_current_pitch(PitchScore.MISSED))
        self._missed_btn.setToolTip("Detection completely failed")

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._good_btn)
        layout.addWidget(self._partial_btn)
        layout.addWidget(self._missed_btn)

        group.setLayout(layout)
        return group

    def _build_statistics_panel(self) -> QtWidgets.QGroupBox:
        """Build statistics summary panel.

        Returns:
            Group box with statistics
        """
        group = QtWidgets.QGroupBox("Statistics")

        self._good_count_label = QtWidgets.QLabel("Good: 0 (0%)")
        self._good_count_label.setStyleSheet("color: #4CAF50; font-weight: bold;")

        self._partial_count_label = QtWidgets.QLabel("Partial: 0 (0%)")
        self._partial_count_label.setStyleSheet("color: #FF9800; font-weight: bold;")

        self._missed_count_label = QtWidgets.QLabel("Missed: 0 (0%)")
        self._missed_count_label.setStyleSheet("color: #f44336; font-weight: bold;")

        self._unscored_count_label = QtWidgets.QLabel("Unscored: 0")
        self._unscored_count_label.setStyleSheet("color: #888;")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._good_count_label)
        layout.addWidget(self._partial_count_label)
        layout.addWidget(self._missed_count_label)
        layout.addWidget(self._unscored_count_label)

        group.setLayout(layout)
        return group

    def load_pitches(self, pitches: list, pitch_scores: dict) -> None:
        """Load pitches into list.

        Args:
            pitches: List of LoadedPitch objects
            pitch_scores: Dictionary of pitch_id -> PitchScore
        """
        self._pitches = pitches
        self._pitch_scores = pitch_scores

        # Clear list
        self._pitch_list.clear()

        # Add pitches
        for i, pitch in enumerate(pitches):
            # Get pitch info from manifest
            manifest = pitch.manifest
            speed = manifest.get("measured_speed_mph", 0.0)
            pitch_id = manifest.get("pitch_id", f"pitch-{i+1:03d}")

            # Get score
            score = pitch_scores.get(pitch.pitch_id, PitchScore.UNSCORED)
            score_icon = self._get_score_icon(score)

            # Create list item
            item_text = f"{score_icon} {pitch_id} - {speed:.1f} mph"
            item = QtWidgets.QListWidgetItem(item_text)

            # Color based on score
            item.setForeground(self._get_score_color(score))

            self._pitch_list.addItem(item)

        # Update statistics
        self._update_statistics()

    def _get_score_icon(self, score: PitchScore) -> str:
        """Get icon for pitch score.

        Args:
            score: Pitch score

        Returns:
            Icon string
        """
        if score == PitchScore.GOOD:
            return "✓"
        elif score == PitchScore.PARTIAL:
            return "⚠"
        elif score == PitchScore.MISSED:
            return "✗"
        else:
            return "○"

    def _get_score_color(self, score: PitchScore) -> QtGui.QColor:
        """Get color for pitch score.

        Args:
            score: Pitch score

        Returns:
            QColor for score
        """
        if score == PitchScore.GOOD:
            return QtGui.QColor("#4CAF50")
        elif score == PitchScore.PARTIAL:
            return QtGui.QColor("#FF9800")
        elif score == PitchScore.MISSED:
            return QtGui.QColor("#f44336")
        else:
            return QtGui.QColor("#888")

    def _on_pitch_selection_changed(self, current_row: int) -> None:
        """Handle pitch selection change.

        Args:
            current_row: Selected row index
        """
        # Enable/disable scoring buttons based on selection
        has_selection = current_row >= 0
        self._good_btn.setEnabled(has_selection)
        self._partial_btn.setEnabled(has_selection)
        self._missed_btn.setEnabled(has_selection)

    def _score_current_pitch(self, score: PitchScore) -> None:
        """Score the currently selected pitch.

        Args:
            score: Pitch score
        """
        current_row = self._pitch_list.currentRow()
        if current_row < 0 or current_row >= len(self._pitches):
            return

        pitch = self._pitches[current_row]

        # Update score
        self._pitch_scores[pitch.pitch_id] = score

        # Update list item
        manifest = pitch.manifest
        speed = manifest.get("measured_speed_mph", 0.0)
        pitch_id = manifest.get("pitch_id", f"pitch-{current_row+1:03d}")
        score_icon = self._get_score_icon(score)
        item_text = f"{score_icon} {pitch_id} - {speed:.1f} mph"

        item = self._pitch_list.item(current_row)
        item.setText(item_text)
        item.setForeground(self._get_score_color(score))

        # Update statistics
        self._update_statistics()

        # Emit signal
        self.pitch_scored.emit(pitch.pitch_id, score)

    def _update_statistics(self) -> None:
        """Update statistics display."""
        if not self._pitch_scores:
            return

        # Count scores
        good_count = sum(1 for s in self._pitch_scores.values() if s == PitchScore.GOOD)
        partial_count = sum(1 for s in self._pitch_scores.values() if s == PitchScore.PARTIAL)
        missed_count = sum(1 for s in self._pitch_scores.values() if s == PitchScore.MISSED)
        unscored_count = sum(1 for s in self._pitch_scores.values() if s == PitchScore.UNSCORED)

        total_scored = good_count + partial_count + missed_count

        # Calculate percentages
        if total_scored > 0:
            good_pct = (good_count / total_scored) * 100
            partial_pct = (partial_count / total_scored) * 100
            missed_pct = (missed_count / total_scored) * 100
        else:
            good_pct = partial_pct = missed_pct = 0

        # Update labels
        self._good_count_label.setText(f"Good: {good_count} ({good_pct:.0f}%)")
        self._partial_count_label.setText(f"Partial: {partial_count} ({partial_pct:.0f}%)")
        self._missed_count_label.setText(f"Missed: {missed_count} ({missed_pct:.0f}%)")
        self._unscored_count_label.setText(f"Unscored: {unscored_count}")

    def _on_go_to_pitch(self) -> None:
        """Navigate to selected pitch."""
        current_row = self._pitch_list.currentRow()
        if current_row >= 0:
            self.pitch_selected.emit(current_row)

    def get_pitch_scores(self) -> dict:
        """Get current pitch scores.

        Returns:
            Dictionary of pitch_id -> PitchScore
        """
        return self._pitch_scores.copy()

    def clear(self) -> None:
        """Clear pitch list."""
        self._pitches = []
        self._pitch_scores = {}
        self._pitch_list.clear()
        self._update_statistics()
