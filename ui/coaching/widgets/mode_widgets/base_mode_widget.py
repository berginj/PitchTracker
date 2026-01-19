"""Base widget for all visualization modes."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from contracts import Frame
    from app.pipeline_service import PitchSummary


# Combined metaclass for Qt + ABC
class QABCMeta(type(QObject), ABCMeta):
    """Metaclass that combines Qt's metaclass with ABCMeta."""
    pass


class BaseModeWidget(QtWidgets.QWidget, metaclass=QABCMeta):
    """Abstract base class for visualization mode widgets.

    All coaching visualization modes must inherit from this class and
    implement the required abstract methods.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize base mode widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._current_camera = "left"  # Default camera selection

    @abstractmethod
    def update_pitch_data(self, recent_pitches: List["PitchSummary"]) -> None:
        """Update visualization with new pitch data.

        Called by CoachWindow when new pitch data is available.

        Args:
            recent_pitches: List of recent pitch summaries
        """
        pass

    @abstractmethod
    def update_camera_frames(
        self,
        left_frame: Optional["Frame"],
        right_frame: Optional["Frame"]
    ) -> None:
        """Update camera preview frames.

        Called by CoachWindow on preview update timer (33ms).

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all visualizations.

        Called when starting a new session.
        """
        pass

    @abstractmethod
    def get_mode_name(self) -> str:
        """Return display name for this mode.

        Returns:
            Mode name (e.g., "Broadcast View")
        """
        pass

    def get_current_camera_selection(self) -> str:
        """Get current camera selection.

        Returns:
            Current camera ("left" or "right")
        """
        return self._current_camera

    def set_camera_selection(self, camera: str) -> None:
        """Set camera selection.

        Called when switching modes to preserve camera selection.

        Args:
            camera: Camera to select ("left" or "right")
        """
        if camera in ("left", "right"):
            self._current_camera = camera
            # Subclasses should override and update their camera widget
