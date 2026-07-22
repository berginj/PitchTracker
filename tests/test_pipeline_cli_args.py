"""Tests for backend-aware defaults in the legacy pipeline CLI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def pipeline_cli():
    """Load ``app/pipeline.py`` without colliding with the app.pipeline package."""

    module_path = Path(__file__).parents[1] / "app" / "pipeline.py"
    spec = importlib.util.spec_from_file_location("pitchtracker_pipeline_cli", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("backend", ["uvc", "sim"])
def test_named_backends_keep_logical_camera_defaults(monkeypatch, pipeline_cli, backend):
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--backend", backend])

    args = pipeline_cli.parse_args()

    assert args.left == "left"
    assert args.right == "right"


def test_opencv_defaults_to_numeric_camera_indexes(monkeypatch, pipeline_cli):
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--backend", "opencv"])

    args = pipeline_cli.parse_args()

    assert args.left == "0"
    assert args.right == "1"


def test_explicit_camera_ids_override_backend_defaults(monkeypatch, pipeline_cli):
    monkeypatch.setattr(
        sys,
        "argv",
        ["pipeline.py", "--backend", "opencv", "--left", "4", "--right", "7"],
    )

    args = pipeline_cli.parse_args()

    assert args.left == "4"
    assert args.right == "7"
