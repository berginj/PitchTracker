@echo off
REM Camera Alignment Checker - Easy launcher for Windows
REM Double-click this file to run the alignment checker

echo.
echo ====================================
echo Camera Alignment Checker
echo ====================================
echo.
echo All output will be logged to: alignment_check_log.txt
echo If the script fails, check this log file for errors.
echo.

REM Check if we have camera arguments
if "%1"=="" (
    echo Using default cameras: Left=0, Right=1
    echo.
    echo To use different cameras, edit this batch file or run:
    echo   python scripts\check_camera_alignment.py --capture --left-camera X --right-camera Y
    echo.
    python scripts\check_camera_alignment.py --capture --left-camera 0 --right-camera 1
) else (
    python scripts\check_camera_alignment.py %*
)

echo.
echo ====================================
echo.
echo If you see errors, check alignment_check_log.txt
echo.
pause
