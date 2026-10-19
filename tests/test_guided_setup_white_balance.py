"""Saved color setup accepts a pinned Kelvin value and requires fresh checks."""

from dataclasses import replace

import pytest

from app.services.setup_workflow import SetupWorkflowService
from contracts.setup_capture import SetupCapturePurpose
from exceptions import ConfigValidationError
from tests.test_guided_setup_workflow import _capture, _new_workflow


def test_observed_white_balance_saves_reopens_and_invalidates_image_checks(tmp_path):
    workflow = _new_workflow(tmp_path)
    workflow.update_settings("camera", {"color_mode": True})
    workflow.assign("left", "right")
    result = _capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR)
    controls = {side: {"readback_verified": True, "resolved_wb": value}
                for side, value in (("left", 5230), ("right", 5330))}
    workflow.apply_capture_result(replace(result, controls=controls))
    generation = workflow.generation
    workflow.record_check("images", True, {}, generation)
    workflow.use_observed_white_balance()
    reopened = SetupWorkflowService(workflow.rigs.config_path, workflow.rigs.base_dir, backend="sim")
    assert reopened.config.camera.wb == 5230
    assert reopened.generation > generation
    assert "images" not in reopened.state["checks"]
    assert all("Pin a verified white balance" not in item for item in reopened.readiness().blockers)


@pytest.mark.parametrize("value", ([5200], "5200", True, 5200.5, 0, -1))
def test_invalid_white_balance_preserves_working_config(tmp_path, value):
    workflow = _new_workflow(tmp_path)
    before = workflow.config_path
    state = workflow.state
    with pytest.raises(ConfigValidationError):
        workflow.update_settings("camera", {"wb": value})
    assert workflow.config_path == before
    assert workflow.state == state
