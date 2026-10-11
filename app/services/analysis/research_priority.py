"""Local capture ownership used to suspend admission of offline research jobs."""

from threading import Lock

_lock = Lock()
_owners: set[int] = set()


def set_capture_active(owner: object, active: bool) -> None:
    with _lock:
        if active:
            _owners.add(id(owner))
        else:
            _owners.discard(id(owner))


def capture_active() -> bool:
    with _lock:
        return bool(_owners)
