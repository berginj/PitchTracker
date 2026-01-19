# Fix Python Cache Issues
# This script completely clears Python caches and verifies the fix

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "PitchTracker Cache Fix Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Kill all Python processes
Write-Host "[1/5] Killing all Python processes..." -ForegroundColor Yellow
try {
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Done" -ForegroundColor Green
} catch {
    Write-Host "  No Python processes running" -ForegroundColor Gray
}
Start-Sleep -Seconds 2

# Step 2: Remove all __pycache__ directories
Write-Host "[2/5] Removing all __pycache__ directories..." -ForegroundColor Yellow
$cacheCount = 0
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force -Recurse -ErrorAction SilentlyContinue
    $cacheCount++
}
Write-Host "  Removed $cacheCount cache directories" -ForegroundColor Green

# Step 3: Remove all .pyc files
Write-Host "[3/5] Removing all .pyc files..." -ForegroundColor Yellow
$pycCount = 0
Get-ChildItem -Path . -Filter "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    $pycCount++
}
Write-Host "  Removed $pycCount .pyc files" -ForegroundColor Green

# Step 4: Verify the fix is in the source code
Write-Host "[4/5] Verifying fix is in source code..." -ForegroundColor Yellow
$qtPipelineFile = "app\qt_pipeline_service.py"
$content = Get-Content $qtPipelineFile -Raw
if ($content -match "def start_capture\(self, config, left_serial: str, right_serial: str, config_path=None\)") {
    Write-Host "  OK: start_capture has config_path parameter" -ForegroundColor Green
} else {
    Write-Host "  ERROR: start_capture missing config_path parameter!" -ForegroundColor Red
    Write-Host "  Run 'git pull' to get latest code" -ForegroundColor Yellow
    exit 1
}

# Step 5: Test the signature with fresh import
Write-Host "[5/5] Testing signature with fresh import..." -ForegroundColor Yellow
$testScript = @"
import sys
import importlib

# Force fresh import
if 'app.qt_pipeline_service' in sys.modules:
    del sys.modules['app.qt_pipeline_service']

from app.qt_pipeline_service import QtPipelineService
import inspect

sig = inspect.signature(QtPipelineService.start_capture)
params = list(sig.parameters.keys())

if 'config_path' in params:
    print('SUCCESS')
    sys.exit(0)
else:
    print('FAILED')
    sys.exit(1)
"@

$testResult = python -c $testScript 2>&1
if ($testResult -match "SUCCESS") {
    Write-Host "  OK: Signature is correct" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Signature still incorrect" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Cache cleared successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now start the application:" -ForegroundColor Cyan
Write-Host "  .\run.ps1 -Backend uvc" -ForegroundColor White
Write-Host ""
