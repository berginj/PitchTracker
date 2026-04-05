from pathlib import Path


MAX_LINES = 500
ROOT = Path(__file__).resolve().parents[1]


def test_priority_hotspots_stay_within_line_limit() -> None:
    hotspots = [
        ROOT / "app" / "pipeline_service.py",
        ROOT / "ui" / "main_window.py",
        ROOT / "ui" / "setup" / "steps" / "calibration_step.py",
    ]

    for path in hotspots:
        line_count = sum(1 for _ in path.open(encoding="utf-8"))
        assert line_count <= MAX_LINES, f"{path} exceeds {MAX_LINES} lines ({line_count})"
