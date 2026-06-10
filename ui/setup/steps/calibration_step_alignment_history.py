"""Alignment history persistence for the calibration step."""

from __future__ import annotations

from pathlib import Path


from log_config.logger import get_logger

logger = get_logger(__name__)


class CalibrationStepAlignmentHistoryMixin:
    def _update_alignment_history(self, results) -> None:
        """Add current results to history and update display.

        Args:
            results: AlignmentResults object to add to history
        """
        from datetime import datetime

        # Add to history list
        self._alignment_history.append(
            {
                "timestamp": datetime.now(),
                "quality": results.quality,
                "focal": results.scale_difference_percent,
                "toin": results.convergence_std_px,
                "vertical": results.vertical_mean_px,
                "rotation": results.rotation_deg,
            }
        )

        # Update history display
        history_text = ""
        for i, entry in enumerate(self._alignment_history, 1):
            history_text += f"Iteration {i} ({entry['timestamp'].strftime('%H:%M:%S')}):\n"
            history_text += f"  Focal: {entry['focal']:5.1f}% | "
            history_text += f"Toe-in: {entry['toin']:5.1f}px | "
            history_text += f"Vertical: {entry['vertical']:5.1f}px | "
            history_text += f"Quality: {entry['quality']}\n\n"

        self._history_list.setText(history_text)
        self._history_group.show()

        # NEW: Auto-save history to file
        self._save_alignment_history()

    def _save_alignment_history(self) -> None:
        """Save alignment history to JSON file for persistence across sessions."""
        try:
            import json
            from datetime import datetime

            history_file = Path("alignment_checks/history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing history file (if exists)
            if history_file.exists():
                try:
                    existing_data = json.loads(history_file.read_text())
                except:
                    existing_data = {"sessions": []}
            else:
                existing_data = {"sessions": []}

            # Create current session entry
            session_entry = {
                "session_date": datetime.now().isoformat(),
                "camera_serials": {"left": self._left_serial, "right": self._right_serial},
                "iterations": [],
            }

            # Convert history entries to serializable format
            for entry in self._alignment_history:
                session_entry["iterations"].append(
                    {
                        "timestamp": entry["timestamp"].isoformat(),
                        "quality": entry["quality"],
                        "focal_diff_percent": entry["focal"],
                        "toin_std_px": entry["toin"],
                        "vertical_mean_px": entry["vertical"],
                        "rotation_deg": entry["rotation"],
                    }
                )

            # Append to sessions
            existing_data["sessions"].append(session_entry)

            # Keep only last 10 sessions to prevent file from growing too large
            if len(existing_data["sessions"]) > 10:
                existing_data["sessions"] = existing_data["sessions"][-10:]

            # Write back to file
            history_file.write_text(json.dumps(existing_data, indent=2))

        except Exception as e:
            # Don't fail alignment check if saving history fails
            logger.warning("Could not save alignment history: {}", e)

    def _load_alignment_history(self) -> None:
        """Load previous alignment history from file (for current session display)."""
        try:
            import json

            history_file = Path("alignment_checks/history.json")
            if not history_file.exists():
                return

            data = json.loads(history_file.read_text())

            # Show summary of past sessions in history widget if no current history
            if len(self._alignment_history) == 0 and len(data.get("sessions", [])) > 0:
                past_sessions_text = "<b>Previous Sessions:</b>\n\n"

                for session in data["sessions"][-5:]:  # Show last 5 sessions
                    date = session["session_date"][:10]  # Just date part
                    iterations = session["iterations"]

                    if len(iterations) > 0:
                        first = iterations[0]
                        last = iterations[-1]

                        past_sessions_text += f"📅 {date} ({len(iterations)} checks):\n"
                        past_sessions_text += f"  Started: {first['quality']} "
                        past_sessions_text += f"(Focal: {first['focal_diff_percent']:.1f}%, "
                        past_sessions_text += f"Toe-in: {first['toin_std_px']:.1f}px)\n"

                        if len(iterations) > 1:
                            past_sessions_text += f"  Ended:   {last['quality']} "
                            past_sessions_text += f"(Focal: {last['focal_diff_percent']:.1f}%, "
                            past_sessions_text += f"Toe-in: {last['toin_std_px']:.1f}px)\n"

                        past_sessions_text += "\n"

                self._history_list.setText(past_sessions_text)
                self._history_group.show()

        except Exception as e:
            logger.warning("Could not load saved alignment history: {}", e)
