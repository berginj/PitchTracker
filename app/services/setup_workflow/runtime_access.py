"""Serialize configuration edits with capture/recording admission."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Callable, Iterator

from app.services.setup_workflow.storage import recording_blockers

if TYPE_CHECKING:
    from app.services.rig_profile import RigProfileService
    from app.services.rig_profile_models import RigProfile
    from configs.settings import AppConfig

_lock = RLock()
_captures: dict[int, tuple[Path, Callable[[], None]]] = {}
_recordings: dict[int, Path] = {}
_setup_operations: dict[int, Path] = {}


@dataclass(frozen=True)
class SetupAdmission:
    capture_owned: bool
    recording_owned: bool
    setup_owned: bool

    @property
    def permits_edit(self) -> bool:
        return not self.capture_owned and not self.recording_owned


def admission_status(base_dir: Path) -> SetupAdmission:
    root = base_dir.resolve()
    with _lock:
        return SetupAdmission(any(path == root for path, _stop in _captures.values()),
                              root in _recordings.values(), root in _setup_operations.values())


def register_capture(owner: int, base_dir: Path, stop: Callable[[], None]) -> None:
    with _lock:
        if base_dir.resolve() in _setup_operations.values():
            raise RuntimeError("Setup cameras are still owned; finish or cancel setup before runtime capture")
        _captures[owner] = (base_dir.resolve(), stop)


def release_capture(owner: int) -> None:
    with _lock:
        _captures.pop(owner, None)


def reserve_recording(owner: int, base_dir: Path, profile_id: str | None) -> None:
    with _lock:
        if base_dir.resolve() in _setup_operations.values():
            raise RuntimeError("Setup cameras are still in use; finish or cancel setup capture before recording")
        blockers = recording_blockers(base_dir, profile_id)
        if blockers:
            raise RuntimeError("; ".join(blockers))
        _recordings[owner] = base_dir.resolve()


def admit_recording(
    owner: int, rigs: RigProfileService, captured: RigProfile | None, config: AppConfig,
    backend: str, left: str | None, right: str | None,
) -> None:
    active = rigs.load_active()
    if active is not None and captured is not None:
        if active.profile_id != captured.profile_id:
            raise RuntimeError("The active rig changed; restart capture before recording")
        if active.effective_config_file:
            validation = rigs.validate_for_runtime(
                active, config=config, backend=backend, left_serial=left, right_serial=right,
            )
            if validation.is_critical:
                raise RuntimeError("; ".join(validation.issues))
    reserve_recording(owner, rigs.base_dir, captured.profile_id if captured else None)


def release_recording(owner: int) -> None:
    with _lock:
        _recordings.pop(owner, None)


def begin_setup_capture(owner: int, base_dir: Path, *, stop_preview: bool = True) -> None:
    with prepare_edit(base_dir, stop_preview=stop_preview):
        root = base_dir.resolve()
        if root in _setup_operations.values():
            raise RuntimeError("Another setup capture is still running")
        _setup_operations[owner] = root


def end_setup_capture(owner: int) -> None:
    with _lock:
        _setup_operations.pop(owner, None)


@contextmanager
def prepare_edit(base_dir: Path, *, stop_preview: bool = True) -> Iterator[None]:
    root = base_dir.resolve()
    with _lock:
        if root in _recordings.values():
            raise RuntimeError("End the recording session before editing rig settings")
        stops = [stop for path, stop in _captures.values() if path == root]
        if stops and not stop_preview:
            raise RuntimeError("Stop runtime preview explicitly in Live before editing or acquiring setup cameras")
    # Do not hold our admission lock while acquiring a pipeline's lifecycle lock.
    for stop in stops:
        stop()
    with _lock:
        if root in _recordings.values():
            raise RuntimeError("End the recording session before editing rig settings")
        if any(path == root for path, _stop in _captures.values()):
            raise RuntimeError("Camera shutdown is incomplete; retry before editing")
        yield
