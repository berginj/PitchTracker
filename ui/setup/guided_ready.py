"""Clear operational readiness and final publication."""

from PySide6 import QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from ui.setup.guided_base import WorkflowStep
from ui.themes import style_status_label


class ReadyStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService):
        super().__init__(workflow, "Ready")
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        self.layout_box.addWidget(self.summary)
        note = QtWidgets.QLabel(
            "A passing setup enables research recording with estimated measurements. "
            "Independently validated accuracy requires a separate physical confirmation and approval."
        )
        note.setWordWrap(True)
        self.layout_box.addWidget(note)
        self.footer()

    def refresh(self) -> None:
        readiness = self.workflow.readiness()
        style_status_label(self.status, "success" if readiness.permits_recording else "warning", readiness.status)
        self.summary.setText("\n".join(readiness.blockers) if readiness.blockers else
                             "All setup checks passed. Finish setup to publish this checked configuration.")
        self.set_details(self.workflow.state)

    def validate(self) -> tuple[bool, str]:
        readiness = self.workflow.readiness()
        return readiness.permits_recording, "; ".join(readiness.blockers)

    def finish_setup(self) -> None:
        self.workflow.finish()
