"""Five guided stages over the saved setup service."""

from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_workflow import GuidedSetupStage
from ui.setup.state_machine import GUIDED_SETUP_SPEC

__all__ = ["GUIDED_SETUP_SPEC", "build_guided_setup_widgets"]


def build_guided_setup_widgets(workflow: SetupWorkflowService, catalog=None):
    from ui.setup.guided_cameras import CamerasStage
    from ui.setup.guided_images import ImagesStage
    from ui.setup.guided_calibration import CalibrationStage
    from ui.setup.guided_field import FieldStage
    from ui.setup.guided_ready import ReadyStage
    return {
        GuidedSetupStage.CAMERAS: CamerasStage(workflow, catalog),
        GuidedSetupStage.IMAGES: ImagesStage(workflow),
        GuidedSetupStage.CALIBRATION: CalibrationStage(workflow),
        GuidedSetupStage.FIELD: FieldStage(workflow),
        GuidedSetupStage.READY: ReadyStage(workflow),
    }
