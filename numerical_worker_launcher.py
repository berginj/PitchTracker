"""Standalone numerical-only worker entry point, suitable for native ARM64 builds."""

from app.trajectory_persistent_worker import main


if __name__ == "__main__":
    main()
