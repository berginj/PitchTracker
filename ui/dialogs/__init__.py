"""UI dialogs module for PitchTracker."""

from ui.dialogs.calibration_guide import CalibrationGuide
from ui.dialogs.calibration_wizard_dialog import CalibrationWizardDialog
from ui.dialogs.checklist_dialog import ChecklistDialog
from ui.dialogs.detector_settings_dialog import DetectorSettingsDialog
from ui.dialogs.pattern_analysis_dialog import PatternAnalysisDialog
from ui.dialogs.plate_plane_dialog import PlatePlaneDialog
from ui.dialogs.quick_calibrate_dialog import QuickCalibrateDialog
from ui.dialogs.recording_settings_dialog import RecordingSettingsDialog
from ui.dialogs.session_summary_dialog import SessionSummaryDialog
from ui.dialogs.startup_dialog import StartupDialog
from ui.dialogs.strike_zone_settings_dialog import StrikeZoneSettingsDialog

__all__ = [
    "CalibrationGuide",
    "CalibrationWizardDialog",
    "ChecklistDialog",
    "DetectorSettingsDialog",
    "PatternAnalysisDialog",
    "PlatePlaneDialog",
    "QuickCalibrateDialog",
    "RecordingSettingsDialog",
    "SessionSummaryDialog",
    "StartupDialog",
    "StrikeZoneSettingsDialog",
]
