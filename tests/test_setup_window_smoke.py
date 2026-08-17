"""Smoke test: SetupWindow is driven by the SetupStateMachine engine.

Follows the repo convention for GUI tests (see
tests/integration/test_main_window_integration.py): only runs when a Qt
application instance already exists, and is skipped otherwise so headless CI
does not crash on Qt teardown. The Qt-free control-flow logic is covered
deterministically by tests/test_wizard_spec.py and tests/test_setup_state_machine.py.
"""

from __future__ import annotations

import sys

import pytest
from PySide6 import QtWidgets

from ui.setup.wizard_spec import WIZARD_STEP_ORDER, WizardStep


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app


def test_setup_window_wires_state_machine(qapp):
    from ui.setup.setup_window import SetupWindow

    window = SetupWindow(backend="opencv")
    try:
        # The window exposes one widget per canonical wizard step, in order.
        assert window._machine.current == WizardStep.CAMERAS
        assert len(window._steps) == len(WIZARD_STEP_ORDER)
        assert window._content_stack.count() == len(WIZARD_STEP_ORDER)
        assert len(window._step_labels) == len(WIZARD_STEP_ORDER)

        # First step: cannot go back; Next shown, Finish hidden.
        assert not window._back_button.isEnabled()
        assert not window._next_button.isHidden()
        assert window._finish_button.isHidden()

        # Drive the machine straight through (no dialogs) and re-render.
        for step in WIZARD_STEP_ORDER[:-1]:
            window._machine.mark_complete(step, True)
            window._machine.advance()
        window._machine.mark_complete(WIZARD_STEP_ORDER[-1], True)
        window._show_current()

        assert window._machine.current.value == WizardStep.QUALITY_REPORT.value
        assert window._machine.can_finish()
        # Last step: Finish shown, Next hidden, Back enabled.
        assert not window._finish_button.isHidden()
        assert window._next_button.isHidden()
        assert window._back_button.isEnabled()
    finally:
        window.close()
