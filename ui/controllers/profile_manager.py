"""Profile and pitcher management controller.

Extracted from MainWindow to reduce god class complexity.
Manages location profiles and pitcher selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state
from configs.location_profiles import apply_profile, list_profiles, load_profile, save_profile
from configs.pitchers import add_pitcher, load_pitchers
from ui.device_utils import current_serial


class ProfileManager:
    """Manages location profiles and pitcher selection.

    Responsibilities:
    - Loading and saving location profiles
    - Managing pitcher list
    - Applying profile settings to camera/ROI configuration
    """

    def __init__(
        self,
        profile_combo: QtWidgets.QComboBox,
        profile_name_input: QtWidgets.QLineEdit,
        pitcher_combo: QtWidgets.QComboBox,
        pitcher_name_input: QtWidgets.QLineEdit,
        left_input: QtWidgets.QComboBox,
        right_input: QtWidgets.QComboBox,
        status_label: QtWidgets.QLabel,
        roi_path: Path,
        on_profile_loaded: Optional[Callable[[str], None]] = None,
        on_rois_changed: Optional[Callable[[], None]] = None,
    ):
        """Initialize profile manager.

        Args:
            profile_combo: Combo box for selecting profiles
            profile_name_input: Input for new profile name
            pitcher_combo: Combo box for selecting pitchers
            pitcher_name_input: Input for new pitcher name
            left_input: Left camera selection combo
            right_input: Right camera selection combo
            status_label: Label for status messages
            roi_path: Path to ROI configuration file
            on_profile_loaded: Callback when profile loaded (profile_name)
            on_rois_changed: Callback when ROIs need reloading
        """
        self._profile_combo = profile_combo
        self._profile_name_input = profile_name_input
        self._pitcher_combo = pitcher_combo
        self._pitcher_name_input = pitcher_name_input
        self._left_input = left_input
        self._right_input = right_input
        self._status_label = status_label
        self._roi_path = roi_path
        self._on_profile_loaded = on_profile_loaded
        self._on_rois_changed = on_rois_changed

        # Current state
        self._location_profile: Optional[str] = None
        self._pitcher_name: Optional[str] = None

    @property
    def location_profile(self) -> Optional[str]:
        """Get current location profile name."""
        return self._location_profile

    @property
    def pitcher_name(self) -> Optional[str]:
        """Get current pitcher name."""
        return self._pitcher_name

    def refresh_profiles(self) -> None:
        """Refresh the profile combo box with available profiles."""
        self._profile_combo.clear()
        self._profile_combo.addItems(list_profiles())

    def refresh_pitchers(self) -> None:
        """Refresh the pitcher combo box with available pitchers."""
        self._pitcher_combo.clear()
        self._pitcher_combo.addItems(load_pitchers())

        # Restore last selected pitcher from state
        state = load_state()
        last = state.get("last_pitcher")
        if last:
            self._pitcher_combo.setCurrentText(last)

    def load_profile(self, parent: QtWidgets.QWidget) -> None:
        """Load selected location profile.

        Args:
            parent: Parent widget for message boxes
        """
        name = self._profile_combo.currentText().strip()
        if not name:
            return

        try:
            profile = load_profile(name)
        except Exception as exc:  # noqa: BLE001 - show profile errors
            QtWidgets.QMessageBox.warning(parent, "Load Profile", str(exc))
            return

        # Set camera serials from profile
        left = str(profile.get("left_serial", ""))
        right = str(profile.get("right_serial", ""))

        if left:
            # Find item by data (serial) instead of text label
            for i in range(self._left_input.count()):
                if self._left_input.itemData(i) == left:
                    self._left_input.setCurrentIndex(i)
                    break
            else:
                # Fallback: try setting text directly (might work for old profiles)
                self._left_input.setCurrentText(left)

        if right:
            # Find item by data (serial) instead of text label
            for i in range(self._right_input.count()):
                if self._right_input.itemData(i) == right:
                    self._right_input.setCurrentIndex(i)
                    break
            else:
                # Fallback: try setting text directly (might work for old profiles)
                self._right_input.setCurrentText(right)

        # Apply profile settings (ROIs, etc.)
        apply_profile(profile, self._roi_path)

        # Notify parent to reload ROIs
        if self._on_rois_changed:
            self._on_rois_changed()

        # Update state
        self._location_profile = name
        self._status_label.setText(f"Loaded profile '{name}'.")

        # Notify parent
        if self._on_profile_loaded:
            self._on_profile_loaded(name)

    def save_profile(self, parent: QtWidgets.QWidget) -> None:
        """Save current configuration as a profile.

        Args:
            parent: Parent widget for message boxes
        """
        name = self._profile_name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.information(
                parent,
                "Save Profile",
                "Enter a profile name.",
            )
            return

        left = current_serial(self._left_input)
        right = current_serial(self._right_input)

        if not left and not right:
            QtWidgets.QMessageBox.information(
                parent,
                "Save Profile",
                "Select at least one device before saving.",
            )
            return

        # Save profile
        save_profile(name, left or "", right or "", self._roi_path)

        # Refresh and update state
        self.refresh_profiles()
        self._profile_name_input.clear()
        self._location_profile = name
        self._status_label.setText(f"Saved profile '{name}'.")

    def add_pitcher(self) -> None:
        """Add a new pitcher to the list."""
        name = self._pitcher_name_input.text().strip()
        if not name:
            return

        # Add pitcher and refresh list
        pitchers = add_pitcher(name)
        self._pitcher_combo.clear()
        self._pitcher_combo.addItems(pitchers)
        self._pitcher_combo.setCurrentText(name)
        self._pitcher_name_input.clear()

        # Set as current pitcher
        self.set_pitcher(name)

    def set_pitcher(self, name: str) -> None:
        """Set current pitcher.

        Args:
            name: Pitcher name
        """
        name = name.strip()
        self._pitcher_name = name if name else None

        # Save to state for persistence
        if name:
            state = load_state()
            state["last_pitcher"] = name
            save_state(state)

    def apply_startup_selection(self, profile_name: Optional[str], pitcher: Optional[str]) -> None:
        """Apply selections from startup dialog.

        Args:
            profile_name: Profile name to load
            pitcher: Pitcher name to select
        """
        if pitcher:
            self._pitcher_name = pitcher
            self._pitcher_combo.setCurrentText(pitcher)
            add_pitcher(pitcher)

        if profile_name:
            self._profile_combo.setCurrentText(profile_name)
            self._location_profile = profile_name
