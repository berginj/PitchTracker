"""Team roster management UI for multi-pitcher support."""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from configs.pitchers import add_pitcher, load_pitchers, rename_pitcher, remove_pitcher
from contracts.pitcher import PitcherSelection
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_dialog_header,
    get_style_manager,
    polish_form_controls,
)

logger = logging.getLogger(__name__)


class PitcherCard(QtWidgets.QFrame):
    """Visual card representing a pitcher in the roster."""

    clicked = QtCore.Signal(str)
    edit_requested = QtCore.Signal(str)
    delete_requested = QtCore.Signal(str)

    def __init__(
        self,
        pitcher_name: str,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._pitcher_name = pitcher_name
        self._selected = False

        self._build_ui()
        self._apply_state_style()
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Select pitcher {pitcher_name}")

    def _build_ui(self) -> None:
        """Build the pitcher card UI."""
        self._name_label = QtWidgets.QLabel(self._pitcher_name)
        self._name_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._name_label.setWordWrap(True)
        self._style_manager.style_label(self._name_label, "sectionTitle")

        self._edit_btn = QtWidgets.QPushButton("Edit")
        self._edit_btn.setAccessibleName(f"Edit pitcher {self._pitcher_name}")
        self._edit_btn.setMaximumWidth(64)
        self._style_manager.style_button(self._edit_btn, "ghost")
        self._edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._pitcher_name))

        self._delete_btn = QtWidgets.QPushButton("Remove")
        self._delete_btn.setAccessibleName(f"Remove pitcher {self._pitcher_name} from roster")
        self._delete_btn.setMaximumWidth(84)
        self._style_manager.style_button(self._delete_btn, "danger")
        self._delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._pitcher_name))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(self._name_label, 1)
        layout.addWidget(self._edit_btn)
        layout.addWidget(self._delete_btn)

        self.setMinimumHeight(56)

    def _apply_state_style(self) -> None:
        """Apply card styling for selected or default state."""
        self.setProperty("surface", "hero" if self._selected else "card")
        self._style_manager.polish(self)
        self._style_manager.style_label(
            self._name_label,
            "accent" if self._selected else "sectionTitle",
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse click selection."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(self._pitcher_name)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        """Update visual selection state."""
        self._selected = selected
        self._apply_state_style()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return):
            self.clicked.emit(self._pitcher_name)
            event.accept()
        else:
            super().keyPressEvent(event)


class TeamManager(QtWidgets.QDialog):
    """Dialog for managing team roster and pitcher profiles."""

    pitcher_selected = QtCore.Signal(str)
    active_pitcher_requested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, browse_only: bool = False) -> None:
        super().__init__(parent)
        self._browse_only = browse_only
        self._style_manager = get_style_manager()
        self.setWindowTitle("Team Roster")
        self.setMinimumSize(480, 560)

        self._selected_pitcher: Optional[str] = None
        self._pitcher_cards: List[PitcherCard] = []
        self._activation_permitted = True

        self._build_ui()
        self._load_roster()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)

        layout.addWidget(
            build_dialog_header(
                "Players" if self._browse_only else "Choose pitcher",
                "Browse recorded history or explicitly choose the active pitcher. Roster edits preserve recorded history."
                if self._browse_only else "Choose a pitcher. An underway pitch keeps its recorded attribution.",
                eyebrow="Profiles",
            )
        )

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setPlaceholderText("Search pitchers...")
        self._search_edit.setAccessibleName("Search saved pitchers")
        self._search_edit.textChanged.connect(self._filter_roster)
        self._style_manager.style_input(self._search_edit)
        layout.addWidget(self._search_edit)

        roster_shell = QtWidgets.QFrame()
        self._style_manager.style_panel(roster_shell, "normal")
        roster_layout = QtWidgets.QVBoxLayout(roster_shell)
        roster_layout.setContentsMargins(0, 0, 0, 0)
        roster_layout.setSpacing(0)

        self._roster_list = QtWidgets.QWidget()
        self._roster_layout = QtWidgets.QVBoxLayout(self._roster_list)
        self._roster_layout.setContentsMargins(12, 12, 12, 12)
        self._roster_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self._empty_state = QtWidgets.QLabel("No pitchers yet. Add one below to get started.")
        self._empty_state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(self._empty_state, "muted")
        self._empty_state.hide()
        self._roster_layout.addWidget(self._empty_state)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self._roster_list)
        roster_layout.addWidget(scroll)
        layout.addWidget(roster_shell, 1)

        add_section = QtWidgets.QFrame()
        self._style_manager.style_panel(add_section, "subtle")
        add_layout = QtWidgets.QHBoxLayout(add_section)
        add_layout.setContentsMargins(14, 12, 14, 12)

        self._new_pitcher_edit = QtWidgets.QLineEdit()
        self._new_pitcher_edit.setPlaceholderText("New pitcher name...")
        self._new_pitcher_edit.setAccessibleName("New pitcher name")
        self._new_pitcher_edit.returnPressed.connect(self._add_pitcher)
        self._style_manager.style_input(self._new_pitcher_edit)

        self._add_btn = QtWidgets.QPushButton("Add Pitcher")
        self._style_manager.style_button(self._add_btn, "success")
        self._add_btn.clicked.connect(self._add_pitcher)

        add_layout.addWidget(self._new_pitcher_edit, 1)
        add_layout.addWidget(self._add_btn)
        layout.addWidget(add_section)

        self._select_btn = QtWidgets.QPushButton("Select Pitcher")
        if self._browse_only:
            self._select_btn.setText("View Sessions")
        self._style_manager.style_button(self._select_btn, "primary")
        self._select_btn.setEnabled(False)
        self._select_btn.setAccessibleName("View selected player's recorded sessions" if self._browse_only else "Confirm pitcher selection")
        self._select_btn.clicked.connect(self._on_select_clicked)

        self._cancel_btn = QtWidgets.QPushButton("Cancel")
        self._style_manager.style_button(self._cancel_btn, "ghost")
        self._cancel_btn.clicked.connect(self.reject)
        self._cancel_btn.setVisible(not self._browse_only)
        self._active_btn = QtWidgets.QPushButton("Use as active pitcher")
        self._active_btn.setAccessibleName("Explicitly use selected player as active pitcher")
        self._active_btn.setEnabled(False)
        self._active_btn.setVisible(self._browse_only)
        self._active_btn.clicked.connect(lambda: self.active_pitcher_requested.emit(self._selected_pitcher) if self._selected_pitcher else None)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self._cancel_btn)
        button_layout.addWidget(self._select_btn)
        button_layout.addWidget(self._active_btn)
        layout.addLayout(button_layout)
        self._feedback = QtWidgets.QLabel("Browsing does not change the active pitcher." if self._browse_only else "Confirm a selection to change pitchers.")
        self._feedback.setWordWrap(True)
        self._feedback.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._feedback)
        self._active_status = QtWidgets.QLabel()
        self._active_status.setWordWrap(True)
        self._active_status.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._active_status)

        polish_form_controls(self)

    def _load_roster(self) -> None:
        """Load pitcher roster from storage."""
        try:
            self._update_roster_display(load_pitchers())
        except (ValueError, OSError) as exc:
            self._feedback.setText(f"Roster unavailable: {exc}. Restore the local roster file and reopen Players.")

    def _update_roster_display(self, pitchers: List[str]) -> None:
        """Update roster display with the current pitcher list."""
        for card in self._pitcher_cards:
            self._roster_layout.removeWidget(card)
            card.deleteLater()
        self._pitcher_cards.clear()
        if self._selected_pitcher not in pitchers:
            self._selected_pitcher = None

        for name in sorted(pitchers):
            card = PitcherCard(name)
            card.clicked.connect(self._on_pitcher_clicked)
            card.edit_requested.connect(self._on_edit_pitcher)
            card.delete_requested.connect(self._on_delete_pitcher)
            self._roster_layout.addWidget(card)
            self._pitcher_cards.append(card)

        self._empty_state.setVisible(not self._pitcher_cards)
        self._update_selection()
        self._filter_roster(self._search_edit.text())

    def _filter_roster(self, text: str) -> None:
        """Filter roster by search text."""
        search = text.lower().strip()
        visible_cards = 0
        for card in self._pitcher_cards:
            visible = not search or search in card._pitcher_name.lower()
            card.setVisible(visible)
            if visible:
                visible_cards += 1

        self._empty_state.setVisible(visible_cards == 0)
        if visible_cards == 0 and search:
            self._empty_state.setText("No pitchers match your search.")
        elif not self._pitcher_cards:
            self._empty_state.setText("No pitchers yet. Add one below to get started.")
        else:
            self._empty_state.setText("No pitchers yet. Add one below to get started.")

    def _add_pitcher(self) -> None:
        """Add a new pitcher to the roster."""
        name = self._new_pitcher_edit.text().strip()
        try:
            pitchers = add_pitcher(name)
        except (ValueError, OSError) as exc:
            self._feedback.setText(str(exc))
            return
        self._update_roster_display(pitchers)
        self._new_pitcher_edit.clear()

        self._selected_pitcher = name
        self._update_selection()
        self._feedback.setText("Pitcher saved. Browsing and active-pitcher changes remain separate actions.")
        logger.info("Added pitcher: %s", name)

    def _on_pitcher_clicked(self, name: str) -> None:
        """Handle pitcher card selection."""
        self._selected_pitcher = name
        self._update_selection()

    def _update_selection(self) -> None:
        """Update selection visual state."""
        for card in self._pitcher_cards:
            card.set_selected(card._pitcher_name == self._selected_pitcher)
        self._select_btn.setEnabled(self._selected_pitcher is not None)
        self._active_btn.setEnabled(self._selected_pitcher is not None and self._activation_permitted)

    def set_active_context(self, selection: PitcherSelection, *, permitted: bool = True) -> None:
        self._activation_permitted = permitted
        text = f"Active pitcher: {selection.active_name or 'not selected'}"
        if selection.pending_name:
            text += f" · Next pitch: {selection.pending_name}; current pitch keeps its attribution."
        if not permitted:
            text += " · Finish the pending session operation before changing pitchers."
        self._active_status.setText(text)
        self._update_selection()

    def _on_edit_pitcher(self, name: str) -> None:
        """Handle edit pitcher request."""
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Edit Pitcher",
            f"Rename '{name}' to:",
            QtWidgets.QLineEdit.EchoMode.Normal,
            name,
        )

        new_name = new_name.strip() if ok else ""
        if not new_name or new_name == name:
            return

        try:
            pitchers = rename_pitcher(name, new_name)
        except (ValueError, OSError) as exc:
            self._feedback.setText(str(exc))
            return
        if self._selected_pitcher == name:
            self._selected_pitcher = new_name
        self._update_roster_display(pitchers)
        self._feedback.setText("Roster name updated. Recorded history and the active pitcher remain unchanged.")

    def _on_delete_pitcher(self, name: str) -> None:
        """Handle delete pitcher request."""
        if not ask_confirmation(
            self,
            "Delete Pitcher",
            f"Remove '{name}' from the roster?",
            informative_text="This removes the profile from the roster list.",
            confirm_variant="danger",
        ):
            return

        try:
            pitchers = remove_pitcher(name)
        except (ValueError, OSError) as exc:
            self._feedback.setText(str(exc))
            return
        if self._selected_pitcher == name:
            self._selected_pitcher = None
        self._update_roster_display(pitchers)
        self._feedback.setText("Removed from the roster. Recordings and the active pitcher remain unchanged.")

    def _on_select_clicked(self) -> None:
        """Handle select button click."""
        if self._selected_pitcher:
            self.pitcher_selected.emit(self._selected_pitcher)
            if not self._browse_only:
                self.accept()

    def get_selected_pitcher(self) -> Optional[str]:
        """Return the currently selected pitcher."""
        return self._selected_pitcher


__all__ = ["TeamManager", "PitcherCard"]
