param(
    [string]$Backend = "uvc"
)

. .\.venv\Scripts\Activate.ps1
python -m ui.qt_app --backend $Backend
