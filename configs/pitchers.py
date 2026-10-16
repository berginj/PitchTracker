"""Persist pitcher list for session naming."""

from __future__ import annotations

import json
import os
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import List, Optional
from contracts.pitcher import validate_pitcher_name


def pitchers_path(root: Optional[Path] = None) -> Path:
    base = root or Path("configs")
    path = base / "pitchers.json"
    return path


def load_pitchers(root: Optional[Path] = None) -> List[str]:
    path = pitchers_path(root)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        entries = data.get("pitchers")
    else:
        entries = data
    if not isinstance(entries, list) or any(not isinstance(item, str) for item in entries):
        raise ValueError("The saved roster must contain a list of pitcher names.")
    return [validate_pitcher_name(item) for item in entries]


def save_pitchers(pitchers: List[str], root: Optional[Path] = None) -> None:
    path = pitchers_path(root)
    names = [validate_pitcher_name(name) for name in pitchers]
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("A pitcher with that name already exists.")
    payload = {"pitchers": sorted(names)}
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".pitchers-", suffix=".tmp", delete=False) as temporary:
        staged = Path(temporary.name)
        json.dump(payload, temporary, indent=2)
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def add_pitcher(name: str, root: Optional[Path] = None) -> List[str]:
    name = validate_pitcher_name(name)
    pitchers = load_pitchers(root)
    if any(value.casefold() == name.casefold() for value in pitchers):
        raise ValueError("A pitcher with that name already exists.")
    if name not in pitchers:
        pitchers.append(name)
        save_pitchers(pitchers, root)
    return sorted(set(pitchers))


def rename_pitcher(old: str, new: str) -> List[str]:
    new = validate_pitcher_name(new)
    pitchers = load_pitchers()
    if old not in pitchers:
        raise ValueError("That pitcher is no longer in the roster. Reopen Players.")
    pitchers[pitchers.index(old)] = new
    save_pitchers(pitchers)
    return pitchers


def remove_pitcher(name: str) -> List[str]:
    pitchers = load_pitchers()
    if name in pitchers:
        pitchers.remove(name)
    save_pitchers(pitchers)
    return pitchers
