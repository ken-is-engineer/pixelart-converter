"""Run the GUI: ``python -m pixelart_converter``."""

from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pixelart_converter.errors import sample_demo_error
from pixelart_converter.logging_config import configure_logging
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
    parser.add_argument(
        "--demo-error",
        action="store_true",
        help="Show a sample classified error without running FFmpeg, then quit.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()

    if args.demo_error:

        def _demo_error_and_quit() -> None:
            window.show_error(sample_demo_error(), show_dialog=False)
            app.quit()

        QTimer.singleShot(0, _demo_error_and_quit)
    elif _is_smoke(args):
        QTimer.singleShot(0, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
