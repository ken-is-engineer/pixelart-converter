"""Probe the bundled FFmpeg and select a supported H.264 encoder."""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass

from pixelart_converter.conversion.binary import resolve_ffmpeg

logger = logging.getLogger(__name__)

DEFAULT_PROBE_TIMEOUT = 10.0
_ENCODER_LINE = re.compile(r"^\s*[A-Z.]{6}\s+(\S+)", re.MULTILINE)
_NATIVE_ENCODERS = {
    "Darwin": "h264_videotoolbox",
    "Windows": "h264_mf",
}


@dataclass(frozen=True)
class EncoderResult:
    """The encoder selected from the bundled FFmpeg's advertised encoders."""

    name: str


class EncoderResolver:
    """Resolve an H.264 encoder in platform-specific priority order."""

    def __init__(self, *, timeout: float = DEFAULT_PROBE_TIMEOUT) -> None:
        self._timeout = timeout

    def resolve(self) -> EncoderResult | None:
        """Return the preferred available encoder, or ``None``.

        ``resolve_ffmpeg`` is deliberately called before the probe so its
        classified missing-binary error propagates without a PATH fallback.
        """
        ffmpeg = resolve_ffmpeg()
        try:
            completed = subprocess.run(
                [str(ffmpeg), "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("FFmpeg encoder probe failed: %s", exc)
            return None

        if completed.returncode != 0:
            logger.warning(
                "FFmpeg encoder probe exited with status %d",
                completed.returncode,
            )
            return None

        encoders = set(
            _ENCODER_LINE.findall(f"{completed.stdout}\n{completed.stderr}")
        )
        if "libx264" in encoders:
            logger.warning(
                "Bundled FFmpeg advertises libx264; ignoring the GPL encoder"
            )
        if "libopenh264" in encoders:
            logger.warning(
                "Bundled FFmpeg advertises libopenh264; not adopted in current builds"
            )

        native = _NATIVE_ENCODERS.get(platform.system())
        if native is not None and native in encoders:
            return EncoderResult(name=native)
        return None


def resolve_encoder(*, timeout: float = DEFAULT_PROBE_TIMEOUT) -> EncoderResult | None:
    """Convenience wrapper around :class:`EncoderResolver`."""
    return EncoderResolver(timeout=timeout).resolve()
