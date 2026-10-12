"""One explicit operation runs all image-quality checks."""

from PySide6 import QtWidgets

from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_capture import SetupCapturePurpose
from ui.setup.guided_base import WorkflowStep, display_image
from ui.themes import style_status_label


class ImagesStage(WorkflowStep):
    def __init__(self, workflow: SetupWorkflowService):
        super().__init__(workflow, "Image checks")
        self.layout_box.addWidget(QtWidgets.QLabel(
            "Keep both cameras fixed. Check focus and lighting at the working distance."
        ))
        row = QtWidgets.QHBoxLayout()
        self.previews = [QtWidgets.QLabel(), QtWidgets.QLabel()]
        for label in self.previews:
            label.setMinimumSize(180, 120)
            row.addWidget(label)
        self.layout_box.addLayout(row)
        self.results = QtWidgets.QLabel()
        self.results.setWordWrap(True)
        self.layout_box.addWidget(self.results)
        run = QtWidgets.QPushButton("Run image checks")
        run.clicked.connect(lambda: self.capture(SetupCapturePurpose.CHECKS, self.completed))
        self.layout_box.addWidget(run)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_pending)
        self.layout_box.addWidget(cancel)
        self.footer()

    def completed(self, diagnostics) -> None:
        self.refresh()
        for side, label in zip(("left", "right"), self.previews):
            display_image(label, self.workflow.images[side])
        self.set_details(diagnostics)

    def refresh(self) -> None:
        check = self.workflow.state["checks"].get("images", {})
        checks = check.get("diagnostics", {}).get("checks", {})
        self.results.setText("\n".join(
            f"{name.replace('_', ' ').capitalize()}: {'Passed' if item['passed'] else 'Needs attention'}"
            for name, item in checks.items()
        ))
        passed, reason = self.validate()
        style_status_label(self.status, "success" if passed else "warning",
                           "Image checks passed" if passed else reason)

    def validate(self) -> tuple[bool, str]:
        check = self.workflow.state["checks"].get("images", {})
        passed = bool(check.get("passed") and "images" in self.workflow.visit_checks)
        return passed, "" if passed else "Run image checks and correct the failed conditions"
