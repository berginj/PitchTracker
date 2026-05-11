"""ChArUco board metadata helpers for calibration setup."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_METADATA_PATHS = (
    Path("charuco_board.json"),
    Path("calibration/charuco_board.json"),
)


@dataclass(frozen=True)
class CharucoBoardMetadata:
    cols: int
    rows: int
    square_mm: float
    dictionary: str = "6x6_250"
    source_path: Optional[Path] = None


def load_charuco_metadata(
    paths: Iterable[Path] = DEFAULT_METADATA_PATHS,
) -> Optional[CharucoBoardMetadata]:
    """Load board metadata written by generate_charuco.py."""
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        return CharucoBoardMetadata(
            cols=_positive_int(data, "cols"),
            rows=_positive_int(data, "rows"),
            square_mm=_positive_float(data, "square_mm"),
            dictionary=str(data.get("dictionary", "6x6_250")),
            source_path=path,
        )
    return None


def _positive_int(data: dict, key: str) -> int:
    value = int(data[key])
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _positive_float(data: dict, key: str) -> float:
    value = float(data[key])
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value
