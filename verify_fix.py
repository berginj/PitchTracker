#!/usr/bin/env python
"""Verify QtPipelineService.start_capture has correct signature."""

import sys
import importlib

# Force fresh import (no cache)
if 'app.qt_pipeline_service' in sys.modules:
    del sys.modules['app.qt_pipeline_service']

from app.qt_pipeline_service import QtPipelineService
import inspect

print("=" * 60)
print("QtPipelineService.start_capture Signature Check")
print("=" * 60)

sig = inspect.signature(QtPipelineService.start_capture)
params = list(sig.parameters.keys())

print(f"\nMethod signature: {sig}")
print(f"Parameters: {params}")
print(f"Parameter count (excluding self): {len(params)}")

# Check if config_path parameter exists
has_config_path = 'config_path' in params

print(f"\nHas 'config_path' parameter: {has_config_path}")

if has_config_path:
    print("\nSTATUS: CORRECT - Method accepts config_path parameter")
    print("The fix is present in the code.")
    sys.exit(0)
else:
    print("\nSTATUS: INCORRECT - Method missing config_path parameter")
    print("Running old code! Restart the application.")
    sys.exit(1)
