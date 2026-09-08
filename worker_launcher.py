"""Frozen console-worker entrypoint; the GUI launches it with CREATE_NO_WINDOW."""

from app.worker_entrypoint import main

if __name__ == "__main__":
    main()
