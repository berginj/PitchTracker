"""Isolated OpenCV camera-index probe executed in a child process."""

from __future__ import annotations

from multiprocessing.connection import Connection

import cv2


def probe_camera_index(index: int, result_connection: Connection) -> None:
    """Probe one DirectShow index and return availability through a pipe."""
    capture = None
    available = False
    try:
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        available = bool(capture.isOpened())
    except Exception:
        available = False
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                available = False
        try:
            result_connection.send(available)
        except (BrokenPipeError, EOFError, OSError):
            pass
        finally:
            result_connection.close()
