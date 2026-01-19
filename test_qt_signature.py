"""Quick test to verify QtPipelineService.start_capture signature."""

from app.qt_pipeline_service import QtPipelineService
import inspect

service = QtPipelineService(backend="uvc")
sig = inspect.signature(service.start_capture)

print("QtPipelineService.start_capture signature:")
print(f"  Full: {sig}")
print(f"  Parameters: {list(sig.parameters.keys())}")
print(f"  Count: {len(sig.parameters)}")

# Test call signature
from unittest.mock import Mock
service._service = Mock()

# This should work without error
try:
    service.start_capture(
        config=Mock(),
        left_serial="test_left",
        right_serial="test_right",
        config_path="test_path"
    )
    print("\nSUCCESS: Method accepts 4 arguments (5 with self)")
except TypeError as e:
    print(f"\nERROR: {e}")
