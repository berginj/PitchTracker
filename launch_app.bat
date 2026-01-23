@echo off
REM PitchTracker Application Launcher

echo Starting PitchTracker...
echo.

cd /d "%~dp0"
set PYTHONPATH=%cd%

REM Launch the role selector
python launcher.py

pause
