param(
    [string]$Python = "python"
)

Write-Host "Activating venv..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Installing build tools..."
python -m pip install --upgrade pip
pip install pyinstaller

Write-Host "Building executable..."
pyinstaller --noconfirm --windowed --name PitchTracker ui\qt_app.py

Write-Host "Build complete. See dist\\PitchTracker\\PitchTracker.exe"
