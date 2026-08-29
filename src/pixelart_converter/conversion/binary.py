"""Resolve bundled ffmpeg (and ffprobe) paths.

Lookup order (design.md §3.3):

1. ``PIXELART_FFMPEG`` / ``PIXELART_FFPROBE`` (tests and local overrides)
2. PyInstaller ``sys._MEIPASS`` when ``sys.frozen``
3. Repo ``vendor/ffmpeg/<os>/`` next to the package/repo root

Never searches PATH. A system ffmpeg must not be used even if it is installed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pixelart_converter.errors import ConversionError, ErrorCode

ENV_FFMPEG = "PIXELART_FFMPEG"
ENV_FFPROBE = "PIXELART_FFPROBE"

_MISSING_FFMPEG_MESSAGE = (
    "The bundled ffmpeg binary is missing. This app cannot convert without it."
)


def _ffmpeg_filename() -> str:
    return "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def _ffprobe_filename() -> str:
    return "ffprobe.exe" if sys.platform == "win32" else "ffprobe"


def _vendor_os_dir() -> str | None:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return None


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _missing_ffmpeg_error(*, detail: str | None = None) -> ConversionError:
    return ConversionError.from_code(
        ErrorCode.ENCODER_UNAVAILABLE,
        message=_MISSING_FFMPEG_MESSAGE,
        detail=detail,
    )


def _env_override(var_name: str) -> Path | None:
    """Return the override path if the variable is set.

    A set override that is not an existing file is an error, not a fallback.
    """
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if _is_file(path):
        return path.resolve()
    raise _missing_ffmpeg_error(
        detail=f"{var_name}={raw!r} is not an existing file",
    )


def _meipass_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass)


def _meipass_candidates(meipass: Path, filename: str) -> tuple[Path, ...]:
    os_dir = _vendor_os_dir()
    candidates = [
        meipass / filename,
        meipass / "ffmpeg" / filename,
    ]
    if os_dir is not None:
        candidates.append(meipass / "vendor" / "ffmpeg" / os_dir / filename)
    return tuple(candidates)


def _first_existing(candidates: tuple[Path, ...]) -> Path | None:
    for candidate in candidates:
        if _is_file(candidate):
            return candidate.resolve()
    return None


def _vendor_search_roots() -> tuple[Path, ...]:
    """Repo root(s) to search for ``vendor/ffmpeg/<os>/``.

    ``binary.py`` lives at ``src/pixelart_converter/conversion/binary.py``,
    so ``parents[3]`` is the repository root in a source checkout.
    """
    here = Path(__file__).resolve()
    try:
        return (here.parents[3],)
    except IndexError:
        return ()


def _vendor_binary(filename: str) -> Path | None:
    os_dir = _vendor_os_dir()
    if os_dir is None:
        return None
    for root in _vendor_search_roots():
        candidate = root / "vendor" / "ffmpeg" / os_dir / filename
        if _is_file(candidate):
            return candidate.resolve()
    return None


def resolve_ffmpeg() -> Path:
    """Return the bundled ffmpeg executable.

    Raises ConversionError if it cannot be found. Does not search PATH.
    """
    override = _env_override(ENV_FFMPEG)
    if override is not None:
        return override

    meipass = _meipass_dir()
    if meipass is not None:
        found = _first_existing(_meipass_candidates(meipass, _ffmpeg_filename()))
        if found is not None:
            return found

    vendor = _vendor_binary(_ffmpeg_filename())
    if vendor is not None:
        return vendor

    raise _missing_ffmpeg_error(
        detail="no PIXELART_FFMPEG, _MEIPASS, or vendor/ffmpeg binary",
    )


def resolve_ffprobe() -> Path | None:
    """Return ffprobe in the same directory as ffmpeg, if present.

    ``PIXELART_FFPROBE`` overrides like ``PIXELART_FFMPEG`` (must be a file).
    ffprobe is optional; missing sibling is None, not an error. PATH is never
    searched.
    """
    override = _env_override(ENV_FFPROBE)
    if override is not None:
        return override

    ffmpeg = resolve_ffmpeg()
    sibling = ffmpeg.parent / _ffprobe_filename()
    if _is_file(sibling):
        return sibling.resolve()
    return None
