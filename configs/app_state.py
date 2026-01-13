"""Persist last-used UI selections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


def state_path(root: Optional[Path] = None) -> Path:
    base = root or Path("configs")
    return base / "app_state.json"


def load_state(root: Optional[Path] = None) -> Dict[str, str]:
    path = state_path(root)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def save_state(state: Dict[str, str], root: Optional[Path] = None) -> None:
    path = state_path(root)
    path.write_text(json.dumps(state, indent=2))
