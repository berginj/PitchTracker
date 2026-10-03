"""Copy-only legacy installation migration; never overwrite or follow links."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile


def copy_file_once(source: Path, destination: Path, state: Path) -> None:
    """Install a complete file atomically if absent, leaving originals untouched."""
    state = state.resolve()
    if not destination.resolve().is_relative_to(state):
        raise ValueError(f"Migration destination escapes operator state: {destination}")
    if destination.is_symlink() or destination.is_junction():
        raise ValueError(f"Migration destination is a link: {destination}")
    if destination.exists():
        return
    if source.is_symlink() or source.is_junction() or not source.is_file():
        if not source.exists():
            raise FileNotFoundError(f"Bundled default or migration source missing: {source}")
        raise ValueError(f"Migration source must be a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".migration-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        try:
            # Linking a complete temporary file creates the destination only if
            # absent, also preserving files created by another app/worker startup.
            os.link(temporary, destination)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def migrate_legacy_state(roots: tuple[Path, ...], state: Path, directories: tuple[str, ...]) -> None:
    """Copy known state directories from known install roots without path rewrites.

    Junctions/symlinks are skipped and external configured paths remain operator
    choices. Errors surface to startup; originals and existing state stay intact.
    """
    for root in dict.fromkeys(path.resolve() for path in roots):
        if root == state.resolve():
            continue
        for name in directories:
            source_dir = root / name
            if not source_dir.is_dir() or source_dir.is_symlink() or source_dir.is_junction():
                continue
            for folder, subdirectories, filenames in os.walk(source_dir, followlinks=False):
                parent = Path(folder)
                subdirectories[:] = [
                    item for item in subdirectories
                    if not (parent / item).is_symlink() and not (parent / item).is_junction()
                ]
                for filename in filenames:
                    source = parent / filename
                    if source.is_symlink() or source.is_junction() or not source.is_file():
                        continue
                    if not source.resolve().is_relative_to(root):
                        continue
                    copy_file_once(source, state / source.relative_to(root), state)
