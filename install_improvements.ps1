# PitchTracker Improvements Installation Script
# Run this to install new dependencies and verify everything works

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "PitchTracker Improvements Installer" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please run setup.ps1 first to create the virtual environment" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Activating virtual environment..." -ForegroundColor Green
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[2/5] Installing new dependencies..." -ForegroundColor Green
pip install -r requirements.txt --quiet

Write-Host "[3/5] Verifying installations..." -ForegroundColor Green

# Test imports
Write-Host "  - Testing logging infrastructure..." -ForegroundColor Gray
python -c "from logging.logger import get_logger; logger = get_logger('test'); logger.info('✓ Logging works'); print('    ✓ Logging module OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    [ERROR] Logging test failed" -ForegroundColor Red
    exit 1
}

Write-Host "  - Testing exception classes..." -ForegroundColor Gray
python -c "from exceptions import CameraConnectionError; print('    ✓ Exceptions module OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    [ERROR] Exceptions test failed" -ForegroundColor Red
    exit 1
}

Write-Host "  - Testing config validation..." -ForegroundColor Gray
python -c "from configs.validator import validate_config_file; validate_config_file('configs/default.yaml'); print('    ✓ Config validation OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "    [ERROR] Config validation test failed" -ForegroundColor Red
    exit 1
}

Write-Host "[4/5] Running new tests..." -ForegroundColor Green
pytest tests/test_stereo_triangulation.py tests/test_detector_accuracy.py tests/test_strike_zone_accuracy.py -v --tb=short
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Some tests failed - check output above" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ All new tests passed!" -ForegroundColor Green
}

Write-Host "[5/5] Checking logs directory..." -ForegroundColor Green
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
    Write-Host "  ✓ Created logs directory" -ForegroundColor Green
} else {
    Write-Host "  ✓ Logs directory exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "New features installed:" -ForegroundColor White
Write-Host "  ✓ Logging infrastructure (loguru)" -ForegroundColor Green
Write-Host "  ✓ Custom exception classes" -ForegroundColor Green
Write-Host "  ✓ Configuration validation" -ForegroundColor Green
Write-Host "  ✓ Enhanced error handling" -ForegroundColor Green
Write-Host "  ✓ 30+ new tests" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Read QUICK_START_IMPROVEMENTS.md for usage guide" -ForegroundColor Yellow
Write-Host "  2. Read IMPROVEMENTS_SUMMARY.md for full documentation" -ForegroundColor Yellow
Write-Host "  3. Run the app: .\run.ps1 -Backend uvc" -ForegroundColor Yellow
Write-Host "  4. Check logs: type logs\pitchtracker_*.log" -ForegroundColor Yellow
Write-Host ""
Write-Host "Happy tracking! 🎯⚾" -ForegroundColor Cyan
