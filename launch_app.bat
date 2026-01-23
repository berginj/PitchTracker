@echo off
REM PitchTracker Application Launcher
REM Launches with simulated backend for testing

echo Starting PitchTracker...
echo.

cd /d "%~dp0"
set PYTHONPATH=%cd%

REM Launch with simulated backend (no cameras required)
python ui\main_window.py --backend sim

REM If you have cameras connected, comment the line above and uncomment below:
REM python ui\main_window.py --backend opencv

pause
