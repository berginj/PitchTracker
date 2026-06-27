"""Support utilities for the PitchTracker launcher."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path


def clear_python_cache(verbose: bool = False, clear_memory: bool = True) -> None:
    """Clear Python bytecode cache files to ensure fresh code loads."""
    logger = logging.getLogger(__name__)
    pyc_count = 0
    cache_count = 0
    pyc_failures = []
    cache_failures = []
    modules_cleared = 0

    for p in Path(".").rglob("*.pyc"):
        try:
            p.unlink()
            pyc_count += 1
        except OSError as exc:
            pyc_failures.append((str(p), str(exc)))
            if verbose:
                logger.warning("Failed to remove .pyc file %s: %s", p, exc)

    for p in Path(".").rglob("__pycache__"):
        try:
            shutil.rmtree(p)
            cache_count += 1
        except OSError as exc:
            cache_failures.append((str(p), str(exc)))
            if verbose:
                logger.warning("Failed to remove __pycache__ directory %s: %s", p, exc)

    if clear_memory:
        modules_cleared = _clear_project_modules()

    if verbose or pyc_failures or cache_failures:
        _report_cache_clear(
            verbose=verbose,
            pyc_count=pyc_count,
            cache_count=cache_count,
            modules_cleared=modules_cleared,
            pyc_failures=pyc_failures,
            cache_failures=cache_failures,
        )


def _clear_project_modules() -> int:
    project_root = Path(".").resolve()
    modules_to_clear = []

    for module_name, module in list(sys.modules.items()):
        if module is None or not hasattr(module, "__file__") or module.__file__ is None:
            continue

        try:
            module_path = Path(module.__file__).resolve()
            if project_root in module_path.parents or module_path.parent == project_root:
                if module_name not in ("__main__", "__mp_main__", "launcher", "startup_validator", "updater"):
                    modules_to_clear.append(module_name)
        except (ValueError, OSError):
            continue

    modules_cleared = 0
    for module_name in modules_to_clear:
        try:
            del sys.modules[module_name]
            modules_cleared += 1
        except KeyError:
            pass
    return modules_cleared


def _report_cache_clear(
    *,
    verbose: bool,
    pyc_count: int,
    cache_count: int,
    modules_cleared: int,
    pyc_failures: list[tuple[str, str]],
    cache_failures: list[tuple[str, str]],
) -> None:
    if verbose:
        if pyc_count > 0 or cache_count > 0:
            print(f"[Cache] Cleared {pyc_count} .pyc files and {cache_count} __pycache__ directories")
        if modules_cleared > 0:
            print(f"[Cache] Cleared {modules_cleared} project modules from memory")
        _report_remaining_cache()

    if pyc_failures or cache_failures:
        total_failures = len(pyc_failures) + len(cache_failures)
        print(f"[Cache] Warning: {total_failures} items could not be cleared (may be in use)")
        if verbose:
            failed_items = ", ".join(f[0] for f in (pyc_failures + cache_failures)[:5])
            print(f"[Cache] Failed items: {failed_items}" + (" ..." if total_failures > 5 else ""))


def _report_remaining_cache() -> None:
    remaining_pyc = sum(1 for _ in Path(".").rglob("*.pyc"))
    remaining_cache = sum(1 for _ in Path(".").rglob("__pycache__"))

    if remaining_pyc > 0 or remaining_cache > 0:
        print(f"[Cache] Verification: {remaining_pyc} .pyc files and {remaining_cache} __pycache__ directories remain")
        print("[Cache] Note: Remaining files may be in use by Python or other processes")
    else:
        print("[Cache] Verification: All cache files successfully cleared")


__all__ = ["clear_python_cache"]
