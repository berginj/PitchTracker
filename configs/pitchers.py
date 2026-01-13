"""Persist pitcher list for session naming."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional


def pitchers_path(root: Optional[Path] = None) -> Path:
    base = root or Path("configs")
    path = base / "pitchers.json"
    return path


def load_pitchers(root: Optional[Path] = None) -> List[str]:
    path = pitchers_path(root)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        entries = data.get("pitchers", [])
    else:
        entries = data
    return [str(item) for item in entries if str(item).strip()]


def save_pitchers(pitchers: List[str], root: Optional[Path] = None) -> None:
    path = pitchers_path(root)
    payload = {"pitchers": sorted(set(pitchers))}
    path.write_text(json.dumps(payload, indent=2))


def add_pitcher(name: str, root: Optional[Path] = None) -> List[str]:
    name = name.strip()
    if not name:
        return load_pitchers(root)
    pitchers = load_pitchers(root)
    if name not in pitchers:
        pitchers.append(name)
        save_pitchers(pitchers, root)
    return sorted(set(pitchers))
