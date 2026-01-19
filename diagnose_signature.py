#!/usr/bin/env python
"""Diagnostic script to check QtPipelineService.start_capture signature at runtime.

Run this AFTER you see the error to diagnose what signature is being used.
"""

import sys
import inspect
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("QtPipelineService.start_capture Signature Diagnostic")
print("=" * 70)
print()

# Import and inspect
from app.qt_pipeline_service import QtPipelineService

# Get signature
sig = inspect.signature(QtPipelineService.start_capture)
params = list(sig.parameters.keys())

print(f"Method signature: {sig}")
print(f"Parameters: {params}")
print(f"Parameter count (including self): {len(params)}")
print()

# Get source file location
source_file = inspect.getsourcefile(QtPipelineService.start_capture)
print(f"Source file: {source_file}")
print()

# Check if config_path exists
has_config_path = 'config_path' in params

print("=" * 70)
if has_config_path:
    print("STATUS: CORRECT ✓")
    print()
    print("The method signature is correct:")
    print("  def start_capture(self, config, left_serial, right_serial, config_path=None)")
    print()
    print("Expected call (4 arguments):")
    print("  service.start_capture(config, left_serial, right_serial, config_path)")
    print()
    print("If you're still getting an error, the running application")
    print("is using OLD cached bytecode. Please:")
    print("  1. Close ALL Python processes completely")
    print("  2. Run: .\\fix_cache.ps1")
    print("  3. Restart the application")
else:
    print("STATUS: INCORRECT ✗")
    print()
    print("The method signature is MISSING config_path parameter:")
    print(f"  def start_capture(self, {', '.join(params[1:])})")
    print()
    print("This is OLD CODE from before the fix (commit 0d06819).")
    print()
    print("SOLUTION:")
    print("  1. Run: git pull")
    print("  2. Run: .\\fix_cache.ps1")
    print("  3. Restart the application")

print("=" * 70)
