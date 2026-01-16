"""Base class for wizard steps."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets


class BaseStep(QtWidgets.QWidget):
    """Base class for wizard steps with validation and navigation.

    Subclasses should implement all abstract methods to define step behavior.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._complete = False

    def get_title(self) -> str:
        """Return step title for display. Subclasses must override."""
        raise NotImplementedError("Subclass must implement get_title()")

    def get_description(self) -> str:
        """Return step description/instructions. Subclasses must override."""
        raise NotImplementedError("Subclass must implement get_description()")

    def validate(self) -> tuple[bool, str]:
        """Validate step completion. Subclasses must override.

        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message should be empty string.
        """
        raise NotImplementedError("Subclass must implement validate()")

    def on_enter(self) -> None:
        """Called when step becomes active. Subclasses should override."""
        pass

    def on_exit(self) -> None:
        """Called when leaving step. Subclasses should override."""
        pass

    def is_optional(self) -> bool:
        """Return True if step can be skipped."""
        return False

    def is_complete(self) -> bool:
        """Return True if step has been completed."""
        return self._complete

    def set_complete(self, complete: bool) -> None:
        """Mark step as complete or incomplete."""
        self._complete = complete
