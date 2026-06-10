"""Profile and pitcher management controller.

Extracted from MainWindow to reduce god class complexity.
Manages location profiles and pitcher selection.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Callable

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state
from configs.location_profiles import apply_profile, list_profiles, load_profile, save_profile
from configs.pitchers import add_pitcher, load_pitchers
from ui.device_utils import current_serial
from log_config.logger import get_logger
from ui.themes import show_message_dialog

logger = get_logger(__name__)


def validate_name(name: str, existing_names: list[str]) -> tuple[bool, str]:
    """Validate profile or pitcher name.

    Args:
        name: Name to validate
        existing_names: List of existing names to check for conflicts

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Name cannot be empty."

    if len(name) > 100:
        return False, "Name too long (max 100 characters)."

    # Allow alphanumeric, spaces, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9 _-]+$", name):
        return False, "Name contains invalid characters.\n\nAllowed: letters, numbers, spaces, hyphens, underscores."

    # Check for conflicts
    if name in existing_names:
        return False, f"'{name}' already exists.\n\nChoose a different name."

    return True, ""


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

    def _set_combo_by_data(self, combo: QtWidgets.QComboBox, value: str) -> bool:
        """Set combo box selection by item data.

        Args:
            combo: Combo box widget
            value: Value to match against itemData

        Returns:
            True if item found and set, False otherwise
        """
        if not value:
            return False

        # Try finding by data first
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                logger.debug(f"Set combo box to index {i} (data={value})")
                return True

        # Fallback: try setting text directly (for legacy profiles)
        combo.setCurrentText(value)
        logger.debug(f"Set combo box by text fallback (value={value})")
        return False

    def refresh_profiles(self) -> None:
        """Refresh the profile combo box with available profiles."""
        profiles = list_profiles()
        logger.debug(f"Refreshing profiles: found {len(profiles)} profiles")
        self._profile_combo.clear()
        self._profile_combo.addItems(profiles)

    def refresh_pitchers(self) -> None:
        """Refresh the pitcher combo box with available pitchers."""
        pitchers = load_pitchers()
        logger.debug(f"Refreshing pitchers: found {len(pitchers)} pitchers")
        self._pitcher_combo.clear()
        self._pitcher_combo.addItems(pitchers)

        # Restore last selected pitcher from state
        state = load_state()
        last = state.get("last_pitcher")
        if last:
            self._pitcher_combo.setCurrentText(last)
            logger.debug(f"Restored last pitcher from state: '{last}'")

    def load_profile(self, parent: QtWidgets.QWidget) -> bool:
        """Load selected location profile.

        Args:
            parent: Parent widget for message boxes

        Returns:
            True if profile loaded successfully, False otherwise
        """
        name = self._profile_combo.currentText().strip()
        if not name:
            logger.debug("Load profile aborted: no profile selected")
            return False

        logger.info(f"Loading profile: '{name}'")

        try:
            profile = load_profile(name)
            logger.debug(f"Profile data loaded: {profile.keys() if isinstance(profile, dict) else 'unknown format'}")
        except FileNotFoundError as exc:
            logger.warning(f"Profile '{name}' not found: {exc}")
            show_message_dialog(
                parent,
                "Load Profile",
                f"Profile '{name}' not found.\n\n"
                f"Available profiles:\n• " + "\n• ".join(list_profiles() or ["(none)"]),
            )
            return False
        except Exception as exc:
            logger.exception(f"Unexpected error loading profile '{name}'")
            show_message_dialog(
                parent,
                "Load Profile",
                f"Failed to load profile '{name}'.\n\n" f"Error: {exc}\n\n" f"Check logs for details.",
                tone="error",
            )
            return False

        # Set camera serials from profile using helper method
        left = str(profile.get("left_serial", ""))
        right = str(profile.get("right_serial", ""))

        if left:
            self._set_combo_by_data(self._left_input, left)
        if right:
            self._set_combo_by_data(self._right_input, right)

        # Apply profile settings (ROIs, etc.)
        try:
            apply_profile(profile, self._roi_path)
            logger.debug(f"Applied profile settings to ROI path: {self._roi_path}")
        except Exception as exc:
            logger.error(f"Failed to apply profile settings: {exc}", exc_info=True)
            show_message_dialog(
                parent,
                "Load Profile",
                f"Profile loaded but failed to apply ROI settings.\n\nError: {exc}",
                tone="warning",
            )
            # Continue anyway - cameras are set

        # Notify parent to reload ROIs
        if self._on_rois_changed:
            self._on_rois_changed()

        # Update state
        self._location_profile = name
        self._status_label.setText(f"Loaded profile '{name}'.")
        logger.info(f"Successfully loaded profile '{name}'")

        # Notify parent
        if self._on_profile_loaded:
            self._on_profile_loaded(name)

        return True

    def save_profile(self, parent: QtWidgets.QWidget) -> bool:
        """Save current configuration as a profile.

        Args:
            parent: Parent widget for message boxes

        Returns:
            True if profile saved successfully, False otherwise
        """
        name = self._profile_name_input.text().strip()
        logger.info(f"Attempting to save profile: '{name}'")

        # Validate name
        is_valid, error_msg = validate_name(name, list_profiles())
        if not is_valid:
            logger.warning(f"Profile name validation failed: {error_msg}")
            show_message_dialog(parent, "Save Profile", error_msg, tone="warning")
            return False

        # Check camera selection
        left = current_serial(self._left_input)
        right = current_serial(self._right_input)

        if not left and not right:
            logger.warning("Save profile aborted: no cameras selected")
            show_message_dialog(
                parent,
                "Save Profile",
                "Select at least one camera before saving.",
                tone="info",
            )
            return False

        # Save profile
        try:
            save_profile(name, left or "", right or "", self._roi_path)
            logger.info(f"Saved profile '{name}' (left={left or 'none'}, right={right or 'none'})")
        except Exception as exc:
            logger.exception(f"Failed to save profile '{name}'")
            show_message_dialog(
                parent,
                "Save Profile",
                f"Failed to save profile.\n\nError: {exc}\n\nCheck logs for details.",
                tone="error",
            )
            return False

        # Refresh and update state
        self.refresh_profiles()
        self._profile_name_input.clear()
        self._location_profile = name
        self._status_label.setText(f"Saved profile '{name}'.")
        logger.info(f"Profile '{name}' saved and UI updated")

        return True

    def add_pitcher(self) -> bool:
        """Add a new pitcher to the list.

        Returns:
            True if pitcher added successfully, False otherwise
        """
        name = self._pitcher_name_input.text().strip()
        if not name:
            logger.debug("Add pitcher aborted: empty name")
            return False

        logger.info(f"Adding new pitcher: '{name}'")

        try:
            # Add pitcher and refresh list
            pitchers = add_pitcher(name)
            self._pitcher_combo.clear()
            self._pitcher_combo.addItems(pitchers)
            self._pitcher_combo.setCurrentText(name)
            self._pitcher_name_input.clear()

            # Set as current pitcher
            self.set_pitcher(name)

            logger.info(f"Successfully added pitcher '{name}'")
            return True
        except Exception as exc:
            logger.exception(f"Failed to add pitcher '{name}'")
            return False

    def set_pitcher(self, name: str) -> None:
        """Set current pitcher.

        Args:
            name: Pitcher name
        """
        name = name.strip()
        self._pitcher_name = name if name else None

        logger.debug(f"Setting current pitcher: '{name or '(none)'}'")

        # Save to state for persistence
        if name:
            state = load_state()
            state["last_pitcher"] = name
            save_state(state)
            logger.debug(f"Saved pitcher '{name}' to state")

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
