"""One-shot camera probe without importing the service or Qt packages."""

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=int, choices=range(16), metavar="index")
    args = parser.parse_args(argv)
    import cv2

    capture = cv2.VideoCapture(args.index, cv2.CAP_DSHOW)
    try:
        opened = capture.isOpened()
    finally:
        capture.release()
    raise SystemExit(0 if opened else 1)


if __name__ == "__main__":
    main()
