"""Team roster management UI for multi-pitcher support.

Provides:
- View and manage team roster
- Add/edit/delete pitcher profiles
- Quick pitcher selection
- Profile photo management
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from configs.pitchers import add_pitcher, load_pitchers, save_pitchers

logger = logging.getLogger(__name__)


class PitcherCard(QtWidgets.QFrame):
    """Visual card representing a pitcher in the roster.

    Shows pitcher name, stats preview, and actions.
    """

    clicked = QtCore.Signal(str)  # pitcher_name
    edit_requested = QtCore.Signal(str)  # pitcher_name
    delete_requested = QtCore.Signal(str)  # pitcher_name

    def __init__(
        self,
        pitcher_name: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pitcher_name = pitcher_name
        self._selected = False

        self._build_ui()
        self._apply_style()

        # Enable click detection
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def _build_ui(self) -> None:
        """Build the card UI."""
        # Name label
        self._name_label = QtWidgets.QLabel(self._pitcher_name)
        self._name_label.setObjectName("pitcher_card_name")

        # Edit button
        self._edit_btn = QtWidgets.QPushButton("Edit")
        self._edit_btn.setObjectName("pitcher_card_button")
        self._edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._pitcher_name))
        self._edit_btn.setMaximumWidth(50)

        # Delete button
        self._delete_btn = QtWidgets.QPushButton("X")
        self._delete_btn.setObjectName("pitcher_card_delete")
        self._delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._pitcher_name))
        self._delete_btn.setMaximumWidth(30)

        # Layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._name_label, 1)
        layout.addWidget(self._edit_btn)
        layout.addWidget(self._delete_btn)

        self.setLayout(layout)
        self.setMinimumHeight(50)

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager
            theme = get_style_manager().theme

            base_style = f"""
                PitcherCard {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    margin: 2px;
                }}
                PitcherCard:hover {{
                    background-color: {theme.surface_glass_hover};
                    border-color: {theme.accent_primary_dim};
                }}
                #pitcher_card_name {{
                    font-size: 13px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}
                #pitcher_card_button {{
                    background-color: transparent;
                    border: 1px solid {theme.border_glass};
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: {theme.text_secondary};
                    font-size: 10px;
                }}
                #pitcher_card_button:hover {{
                    background-color: {theme.accent_primary_dim};
                    color: {theme.accent_primary};
                }}
                #pitcher_card_delete {{
                    background-color: transparent;
                    border: 1px solid {theme.accent_error_dim};
                    border-radius: 4px;
                    padding: 4px;
                    color: {theme.accent_error};
                    font-size: 10px;
                }}
                #pitcher_card_delete:hover {{
                    background-color: {theme.accent_error_dim};
                }}
            """

            self.setStyleSheet(base_style)

        except ImportError:
            self.setStyleSheet("""
                PitcherCard {
                    background-color: rgba(30, 40, 55, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
            """)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._pitcher_name)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        """Set selection state.

        Args:
            selected: True if card is selected
        """
        self._selected = selected
        # Update visual state
        if selected:
            try:
                from ui.themes import get_style_manager
                theme = get_style_manager().theme
                self.setStyleSheet(self.styleSheet() + f"""
                    PitcherCard {{
                        border: 2px solid {theme.accent_primary};
                        background-color: {theme.accent_primary_dim};
                    }}
                """)
            except ImportError:
                pass
        else:
            self._apply_style()


class TeamManager(QtWidgets.QDialog):
    """Dialog for managing team roster and pitcher profiles.

    Features:
    - View all pitchers in roster
    - Add new pitchers
    - Edit existing pitcher profiles
    - Delete pitchers
    - Select pitcher for session
    """

    pitcher_selected = QtCore.Signal(str)  # Emitted when a pitcher is selected

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Team Roster")
        self.setMinimumSize(400, 500)

        self._selected_pitcher: Optional[str] = None
        self._pitcher_cards: List[PitcherCard] = []

        self._build_ui()
        self._apply_style()
        self._load_roster()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Header
        header = QtWidgets.QLabel("TEAM ROSTER")
        header.setObjectName("team_header")

        # Search/filter
        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("Search pitchers...")
        self._search_edit.textChanged.connect(self._filter_roster)
        self._search_edit.setObjectName("team_search")

        # Roster list (scrollable)
        self._roster_list = QtWidgets.QWidget()
        self._roster_layout = QtWidgets.QVBoxLayout()
        self._roster_layout.setSpacing(4)
        self._roster_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self._roster_list.setLayout(self._roster_layout)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._roster_list)
        scroll.setObjectName("team_scroll")

        # Add pitcher section
        add_section = self._build_add_section()

        # Action buttons
        self._select_btn = QtWidgets.QPushButton("Select Pitcher")
        self._select_btn.setObjectName("team_select_btn")
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select_clicked)

        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self._cancel_btn)
        button_layout.addWidget(self._select_btn)

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(self._search_edit)
        layout.addWidget(scroll, 1)
        layout.addWidget(add_section)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _build_add_section(self) -> QtWidgets.QWidget:
        """Build add pitcher section."""
        widget = QtWidgets.QWidget()
        widget.setObjectName("team_add_section")

        self._new_pitcher_edit = QtWidgets.QLineEdit()
        self._new_pitcher_edit.setPlaceholderText("New pitcher name...")
        self._new_pitcher_edit.returnPressed.connect(self._add_pitcher)

        self._add_btn = QtWidgets.QPushButton("+ Add")
        self._add_btn.setObjectName("team_add_btn")
        self._add_btn.clicked.connect(self._add_pitcher)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._new_pitcher_edit, 1)
        layout.addWidget(self._add_btn)

        widget.setLayout(layout)
        return widget

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager
            theme = get_style_manager().theme

            self.setStyleSheet(f"""
                TeamManager {{
                    background-color: {theme.background_dark};
                }}
                #team_header {{
                    font-size: 16px;
                    font-weight: bold;
                    color: {theme.accent_primary};
                    padding-bottom: 8px;
                }}
                #team_search {{
                    background-color: {theme.input_background};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px;
                    color: {theme.text_primary};
                }}
                #team_search:focus {{
                    border-color: {theme.accent_primary};
                }}
                #team_scroll {{
                    background-color: transparent;
                    border: none;
                }}
                #team_add_section {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px;
                }}
                #team_add_btn {{
                    background-color: {theme.accent_success_dim};
                    border: 1px solid {theme.accent_success};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px 16px;
                    color: {theme.accent_success};
                    font-weight: bold;
                }}
                #team_add_btn:hover {{
                    background-color: {theme.accent_success};
                    color: white;
                }}
                #team_select_btn {{
                    background-color: {theme.accent_primary_dim};
                    border: 1px solid {theme.accent_primary};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px 16px;
                    color: {theme.accent_primary};
                    font-weight: bold;
                }}
                #team_select_btn:hover {{
                    background-color: {theme.accent_primary};
                    color: white;
                }}
                #team_select_btn:disabled {{
                    background-color: transparent;
                    color: {theme.text_muted};
                }}
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px 16px;
                    color: {theme.text_secondary};
                }}
                QPushButton:hover {{
                    background-color: {theme.surface_glass_hover};
                }}
            """)
        except ImportError:
            pass

    def _load_roster(self) -> None:
        """Load pitcher roster from storage."""
        pitchers = load_pitchers()
        self._update_roster_display(pitchers)

    def _update_roster_display(self, pitchers: List[str]) -> None:
        """Update roster display with pitcher list.

        Args:
            pitchers: List of pitcher names
        """
        # Clear existing cards
        for card in self._pitcher_cards:
            card.deleteLater()
        self._pitcher_cards.clear()

        # Add cards for each pitcher
        for name in sorted(pitchers):
            card = PitcherCard(name)
            card.clicked.connect(self._on_pitcher_clicked)
            card.edit_requested.connect(self._on_edit_pitcher)
            card.delete_requested.connect(self._on_delete_pitcher)
            self._roster_layout.addWidget(card)
            self._pitcher_cards.append(card)

        # Add spacer at end
        self._roster_layout.addStretch()

    def _filter_roster(self, text: str) -> None:
        """Filter roster by search text.

        Args:
            text: Search text
        """
        search = text.lower().strip()
        for card in self._pitcher_cards:
            visible = not search or search in card._pitcher_name.lower()
            card.setVisible(visible)

    def _add_pitcher(self) -> None:
        """Add new pitcher to roster."""
        name = self._new_pitcher_edit.text().strip()
        if not name:
            return

        # Add to storage
        pitchers = add_pitcher(name)

        # Refresh display
        self._update_roster_display(pitchers)
        self._new_pitcher_edit.clear()

        # Select the new pitcher
        self._selected_pitcher = name
        self._update_selection()

        logger.info(f"Added pitcher: {name}")

    def _on_pitcher_clicked(self, name: str) -> None:
        """Handle pitcher card click.

        Args:
            name: Pitcher name
        """
        self._selected_pitcher = name
        self._update_selection()

    def _update_selection(self) -> None:
        """Update selection visual state."""
        for card in self._pitcher_cards:
            card.set_selected(card._pitcher_name == self._selected_pitcher)

        self._select_btn.setEnabled(self._selected_pitcher is not None)

    def _on_edit_pitcher(self, name: str) -> None:
        """Handle edit pitcher request.

        Args:
            name: Pitcher name to edit
        """
        # Show simple rename dialog
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Edit Pitcher",
            f"Rename '{name}' to:",
            QtWidgets.QLineEdit.EchoMode.Normal,
            name,
        )

        if ok and new_name and new_name != name:
            # Update storage
            pitchers = load_pitchers()
            if name in pitchers:
                pitchers.remove(name)
                pitchers.append(new_name)
                save_pitchers(pitchers)
                self._update_roster_display(pitchers)

                if self._selected_pitcher == name:
                    self._selected_pitcher = new_name
                    self._update_selection()

                logger.info(f"Renamed pitcher: {name} -> {new_name}")

    def _on_delete_pitcher(self, name: str) -> None:
        """Handle delete pitcher request.

        Args:
            name: Pitcher name to delete
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Pitcher",
            f"Are you sure you want to remove '{name}' from the roster?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Update storage
            pitchers = load_pitchers()
            if name in pitchers:
                pitchers.remove(name)
                save_pitchers(pitchers)
                self._update_roster_display(pitchers)

                if self._selected_pitcher == name:
                    self._selected_pitcher = None
                    self._update_selection()

                logger.info(f"Deleted pitcher: {name}")

    def _on_select_clicked(self) -> None:
        """Handle select button click."""
        if self._selected_pitcher:
            self.pitcher_selected.emit(self._selected_pitcher)
            self.accept()

    def get_selected_pitcher(self) -> Optional[str]:
        """Get the selected pitcher name.

        Returns:
            Selected pitcher name or None
        """
        return self._selected_pitcher


__all__ = ["TeamManager", "PitcherCard"]
