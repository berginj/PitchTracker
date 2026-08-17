from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtWidgets

from ui.setup.field_alignment_view import FieldAlignmentSnapshot, load_or_estimate_field_alignment, present_field_alignment
from ui.setup.steps.base_step import BaseStep
from ui.themes import apply_standard_layout, build_notice, get_style_manager, style_status_label


class FieldAlignmentStep(BaseStep):
    def __init__(self, snapshot_provider: Optional[Callable[[], FieldAlignmentSnapshot]] = None, parent=None):
        super().__init__(parent)
        self._uses_default_provider = snapshot_provider is None
        self._provider = snapshot_provider or load_or_estimate_field_alignment
        self._snapshot: FieldAlignmentSnapshot | None = None
        self._style = get_style_manager()
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)
        self._headline = QtWidgets.QLabel("Field alignment")
        style_status_label(self._headline, "info", "Field alignment")
        layout.addWidget(self._headline)
        self._details = QtWidgets.QVBoxLayout()
        layout.addLayout(self._details)
        refresh = QtWidgets.QPushButton("Load / Recalculate Field Transform")
        refresh.clicked.connect(self.recalculate)
        layout.addWidget(refresh)
        layout.addStretch()

    def get_title(self) -> str:
        return "Field Alignment"

    def get_description(self) -> str:
        return "Map calibrated camera coordinates into the surveyed baseball field frame."

    def on_enter(self) -> None:
        self.refresh()

    def validate(self) -> tuple[bool, str]:
        if self._snapshot is None:
            self.refresh()
        return (
            bool(self._snapshot and self._snapshot.passed),
            "" if self._snapshot and self._snapshot.passed else (self._snapshot.recommendation if self._snapshot else "Field alignment unavailable."),
        )

    def refresh(self) -> None:
        self._snapshot = self._provider()
        self._render_snapshot()

    def recalculate(self) -> None:
        if self._uses_default_provider:
            self._snapshot = load_or_estimate_field_alignment(force_recalculate=True)
        else:
            self._snapshot = self._provider()
        self._render_snapshot()

    def _render_snapshot(self) -> None:
        assert self._snapshot is not None
        view = present_field_alignment(self._snapshot)
        style_status_label(self._headline, view.tone, view.headline)
        while self._details.count():
            item = self._details.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in view.rows:
            label = QtWidgets.QLabel(f"{row.label}: {row.value}")
            self._details.addWidget(label)
        for warning in view.warnings:
            notice, _ = build_notice(warning, tone="warning")
            self._details.addWidget(notice)
        self.set_complete(self._snapshot.passed)


__all__ = ["FieldAlignmentStep"]
