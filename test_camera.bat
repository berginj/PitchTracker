@echo off
REM Minimal Camera Test - Tests basic camera functionality
REM Run this first if alignment checker is failing

echo.
echo ====================================
echo Minimal Camera Test
echo ====================================
echo.
echo This test checks if basic camera functions work.
echo If this test passes but alignment checker fails,
echo check alignment_check_log.txt for detailed errors.
echo.

python test_camera_basic.py

echo.
pause
