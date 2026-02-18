"""Calibration workflow management controller.

Extracted from MainWindow to reduce god class complexity.
Manages stereo calibration workflows and dialogs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

from PySide6 import QtWidgets

from calib.plate_plane import estimate_and_write
from configs.settings import load_config, AppConfig
from ui.dialogs import (
    CalibrationGuide,
    CalibrationWizardDialog,
    PlatePlaneDialog,
    QuickCalibrateDialog,
)
from log_config.logger import get_logger

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLabel

logger = get_logger(__name__)


class CalibrationManager:
    """Manages stereo calibration workflows and dialogs.

    Responsibilities:
    - Opening calibration guide and wizard dialogs
    - Managing quick calibration workflow
    - Managing plate plane calibration
    - Updating calibration summary display
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        config_path: Path,
        status_label: "QLabel",
        calib_summary: "QLabel",
        get_config: Callable[[], AppConfig],
        set_config: Callable[[AppConfig], None],
    ):
        """Initialize calibration manager.

        Args:
            parent: Parent widget for dialogs
            config_path: Path to configuration file
            status_label: Label for status messages
            calib_summary: Label for calibration summary display
            get_config: Callback to get current config
            set_config: Callback to set new config
        """
        self._parent = parent
        self._config_path = config_path
        self._status_label = status_label
        self._calib_summary = calib_summary
        self._get_config = get_config
        self._set_config = set_config

        # Track open wizard dialog (only one at a time)
        self._calibration_wizard: Optional[CalibrationWizardDialog] = None

        logger.debug(f"CalibrationManager initialized with config path: {config_path}")

    def open_calibration_guide(self) -> None:
        """Open the calibration guide dialog.

        Shows step-by-step calibration instructions.
        """
        logger.info("Opening calibration guide")
        dialog = CalibrationGuide(self._parent)
        dialog.exec()
        logger.debug("Calibration guide closed")

    def run_calibration_wizard(self) -> None:
        """Open or focus the calibration wizard dialog.

        The wizard provides guided calibration with camera detection
        and step-by-step instructions.
        """
        # If wizard already open, bring it to front
        if self._calibration_wizard is not None:
            logger.debug("Calibration wizard already open, raising window")
            self._calibration_wizard.raise_()
            self._calibration_wizard.activateWindow()
            return

        logger.info("Opening calibration wizard")
        wizard = CalibrationWizardDialog(self._parent)
        wizard.setModal(False)
        wizard.finished.connect(self._on_wizard_closed)
        self._calibration_wizard = wizard
        wizard.show()

    def _on_wizard_closed(self) -> None:
        """Handle calibration wizard being closed."""
        logger.debug("Calibration wizard closed")
        self._calibration_wizard = None

    def open_quick_calibrate(self) -> None:
        """Open the quick calibration dialog.

        Quick calibration allows rapid stereo calibration using
        ChArUco board images.
        """
        logger.info("Opening quick calibrate dialog")
        dialog = QuickCalibrateDialog(self._parent, self._config_path)
        dialog.exec()

        if dialog.updated:
            logger.info("Quick calibration completed, reloading config")
            # Reload config to pick up changes
            new_config = load_config(self._config_path)
            self._set_config(new_config)
            self.update_calib_summary()

            # Build status message
            if dialog.updates:
                baseline = dialog.updates.get("baseline_ft")
                focal = dialog.updates.get("focal_length_px")
                if isinstance(baseline, (int, float)) and isinstance(focal, (int, float)):
                    msg = f"Calibration updated (baseline_ft={baseline:.3f}, f_px={focal:.1f}). Restart capture."
                    logger.info(f"Calibration values: baseline={baseline:.3f}, focal={focal:.1f}")
                else:
                    msg = "Calibration updated. Restart capture to apply."
            else:
                msg = "Calibration updated. Restart capture to apply."

            self._status_label.setText(msg)
        else:
            logger.debug("Quick calibrate dialog cancelled")

    def open_plate_calibrate(self) -> None:
        """Open the plate plane calibration dialog.

        Plate plane calibration determines the Z coordinate of the
        plate plane for accurate strike zone calculation.
        """
        logger.info("Opening plate plane calibration dialog")
        dialog = PlatePlaneDialog(self._parent, self._config_path)

        if dialog.exec() != QtWidgets.QDialog.Accepted:
            logger.debug("Plate plane calibration cancelled")
            return

        left_path, right_path = dialog.values()
        logger.info(f"Running plate plane estimation with left={left_path}, right={right_path}")

        try:
            plate_z = estimate_and_write(
                Path(left_path),
                Path(right_path),
                self._config_path,
            )
        except Exception as exc:
            logger.error(f"Plate plane calibration failed: {exc}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self._parent,
                "Plate Plane Calibrate",
                f"Calibration failed.\n\nError: {exc}",
            )
            return

        # Reload config to pick up changes
        new_config = load_config(self._config_path)
        self._set_config(new_config)

        msg = f"Plate plane updated (Z={plate_z:.3f} ft). Restart capture."
        logger.info(msg)
        self._status_label.setText(msg)

    def update_calib_summary(self) -> None:
        """Update the calibration summary display.

        Shows current baseline and focal length values.
        """
        config = self._get_config()
        baseline = config.stereo.baseline_ft
        focal = config.stereo.focal_length_px

        summary_text = f"Calib: baseline_ft={baseline:.3f} f_px={focal:.1f}"
        self._calib_summary.setText(summary_text)
        logger.debug(f"Updated calibration summary: {summary_text}")

    @property
    def wizard_is_open(self) -> bool:
        """Check if calibration wizard is currently open."""
        return self._calibration_wizard is not None
