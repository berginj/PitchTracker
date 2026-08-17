param(
    [string]$Backend = "uvc"
)

. .\.venv\Scripts\Activate.ps1
python launcher.py --backend $Backend
