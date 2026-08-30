"""Locate bundled third-party license texts (T6-1)."""

from __future__ import annotations

import sys
from pathlib import Path

_NOTICE_FILENAME = "NOTICE.txt"


def _meipass_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass)


def _repo_root() -> Path:
    # src/pixelart_converter/licenses.py -> parents[2] is the repository root.
    return Path(__file__).resolve().parents[2]


def resolve_third_party_licenses_dir() -> Path:
    """Return the directory containing NOTICE.txt and license files."""
    meipass = _meipass_dir()
    if meipass is not None:
        bundled = meipass / "third_party_licenses"
        if (bundled / _NOTICE_FILENAME).is_file():
            return bundled

    dev = _repo_root() / "third_party_licenses"
    if (dev / _NOTICE_FILENAME).is_file():
        return dev

    raise FileNotFoundError("third_party_licenses directory not found")


def notice_path() -> Path:
    """Return the path to NOTICE.txt."""
    return resolve_third_party_licenses_dir() / _NOTICE_FILENAME
