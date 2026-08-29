"""Package logging setup using the stdlib logging module."""

from __future__ import annotations

import logging
import sys

PACKAGE_LOGGER_NAME = "pixelart_converter"


def configure_logging(*, level: int = logging.INFO) -> None:
    """Configure root handlers once and set the package logger level."""
    package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    if not package_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        package_logger.addHandler(handler)
    package_logger.setLevel(level)
    package_logger.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the package namespace."""
    if name:
        return logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")
    return logging.getLogger(PACKAGE_LOGGER_NAME)
