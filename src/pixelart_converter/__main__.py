"""Run the GUI: ``python -m pixelart_converter``."""

from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pixelart_converter.ui.main_window import MainWindow


def _is_smoke(args: argparse.Namespace) -> bool:
    if args.smoke:
        return True
    return os.environ.get("PIXELART_SMOKE", "") == "1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pixelart-converter")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Create the window and quit immediately (CI / headless).",
    )
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()

    if _is_smoke(args):
        QTimer.singleShot(0, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
