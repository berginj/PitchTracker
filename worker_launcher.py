"""Frozen console-worker entrypoint; the GUI launches it with CREATE_NO_WINDOW."""

from app.runtime_paths import prepare_frozen_runtime

prepare_frozen_runtime()

from app.worker_entrypoint import main  # noqa: E402

if __name__ == "__main__":
    main()
