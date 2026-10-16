"""Operator-selected names are labels, not inferred stable player identities."""

from dataclasses import dataclass


def validate_pitcher_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Enter a pitcher name.")
    name = name.strip()
    if len(name) > 80 or not name.isprintable():
        raise ValueError("Use a printable pitcher name of 80 characters or fewer.")
    return name


@dataclass(frozen=True)
class PitcherSelection:
    active_name: str | None = None
    pending_name: str | None = None
    pitch_id: str | None = None
