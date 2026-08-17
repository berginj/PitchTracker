"""Persist last-used UI selections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

AppStateValue = str | int | float | bool | None


def state_path(root: Optional[Path] = None) -> Path:
    base = root or Path("configs")
    return base / "app_state.json"


def load_state(root: Optional[Path] = None) -> dict[str, AppStateValue]:
    path = state_path(root)
    if not path.exists():
        return {}
    data: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return {
        str(key): value
        for key, value in data.items()
        if value is None or isinstance(value, (str, int, float, bool))
    }


def save_state(state: dict[str, AppStateValue], root: Optional[Path] = None) -> None:
    path = state_path(root)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
