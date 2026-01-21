"""Integration test for MainWindow with PipelineOrchestrator.

Tests that MainWindow can be instantiated and basic operations work with the new
event-driven pipeline architecture.
"""

import sys
from pathlib import Path

import pytest
from PySide6 import QtWidgets

from configs.settings import load_config


# Skip if running in CI without display
pytestmark = pytest.mark.skipif(
    not hasattr(QtWidgets.QApplication, 'instance') or QtWidgets.QApplication.instance() is None,
    reason="Requires Qt GUI environment"
)


@pytest.fixture(scope="module")
def qapp():
    """Create Qt application for testing."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    yield app


def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


def test_main_window_instantiation(qapp):
    """Test MainWindow can be instantiated with PipelineOrchestrator."""
    from ui.main_window import MainWindow

    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"

    # Create MainWindow
    window = MainWindow(backend="sim", config_path=config_path)

    # Verify it was created
    assert window is not None
    assert window._service is not None

    # Cleanup
    window.close()


def test_main_window_service_type(qapp):
    """Test MainWindow uses PipelineOrchestrator."""
    from ui.main_window import MainWindow
    from app.services.orchestrator import PipelineOrchestrator

    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"

    # Create MainWindow
    window = MainWindow(backend="sim", config_path=config_path)

    # Verify service is PipelineOrchestrator
    assert isinstance(window._service, PipelineOrchestrator)

    # Cleanup
    window.close()


def test_main_window_basic_operations(qapp):
    """Test basic MainWindow operations work."""
    from ui.main_window import MainWindow

    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"

    # Create MainWindow
    window = MainWindow(backend="sim", config_path=config_path)

    # Test window properties
    assert window.windowTitle().startswith("Pitch Tracker")

    # Test service is accessible
    assert window._service is not None

    # Test config is loaded
    assert window._config is not None

    # Cleanup
    window.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
