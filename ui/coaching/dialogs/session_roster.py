"""Shared saved roster for session preparation without fabricated sample players."""

import logging

from configs.pitchers import load_pitchers


def load_preparation_roster(dialog) -> list[str]:
    try:
        return sorted(load_pitchers())
    except (ValueError, OSError) as exc:
        logging.getLogger(__name__).exception("Roster could not be loaded for preparation")
        dialog._roster_error = str(exc)
        return []


def save_new_pitcher(dialog) -> bool:
    if dialog._pitcher_combo.currentText() != "+ Add New Pitcher":
        return True
    try:
        from configs.pitchers import add_pitcher
        add_pitcher(dialog._pitcher_name)
        return True
    except (ValueError, OSError) as exc:
        from ui.themes import show_message_dialog
        show_message_dialog(dialog, "Roster not saved", str(exc), tone="warning")
        return False
