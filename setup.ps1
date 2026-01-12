param(
    [string]$Python = "python"
)

Write-Host "Creating venv..."
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create venv."
}

Write-Host "Activating venv..."
. .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "Installing dependencies..."
pip install -r requirements.txt

Write-Host "Setup complete."
