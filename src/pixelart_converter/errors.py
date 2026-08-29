"""Classified conversion errors for user-facing messages and logging."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    """Stable error categories surfaced in the UI and logs."""

    INVALID_INPUT = "invalid_input"
    ENCODER_UNAVAILABLE = "encoder_unavailable"
    OUTPUT_PATH = "output_path"
    DISK = "disk"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


_DEFAULT_USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_INPUT: (
        "The input GIF could not be opened. Check that the file exists and is a valid GIF."
    ),
    ErrorCode.ENCODER_UNAVAILABLE: (
        "No compatible H.264 encoder is available on this system. "
        "MP4 output requires a hardware encoder; this app does not fall back to GPL FFmpeg builds."
    ),
    ErrorCode.OUTPUT_PATH: (
        "The output path is invalid or cannot be written. Choose a different file or folder."
    ),
    ErrorCode.DISK: (
        "Not enough disk space to write the output file. Free space and try again."
    ),
    ErrorCode.CANCELLED: "Conversion was cancelled.",
    ErrorCode.UNKNOWN: "Conversion failed for an unexpected reason. See the log for details.",
}


def user_message_for(code: ErrorCode) -> str:
    """Return the default user-facing message for an error code."""
    return _DEFAULT_USER_MESSAGES[code]


@dataclass(frozen=True, slots=True)
class ConversionError:
    """Structured error: category, user message, and optional log-only detail."""

    code: ErrorCode
    message: str
    detail: str | None = None

    @classmethod
    def from_code(
        cls,
        code: ErrorCode,
        *,
        message: str | None = None,
        detail: str | None = None,
    ) -> ConversionError:
        return cls(code=code, message=message or user_message_for(code), detail=detail)

    def log_message(self) -> str:
        """Format for logging; includes detail when present."""
        if self.detail:
            return f"[{self.code.value}] {self.message} (detail: {self.detail})"
        return f"[{self.code.value}] {self.message}"


def sample_demo_error() -> ConversionError:
    """Return a dummy classified error for smoke/demo paths."""
    return ConversionError.from_code(
        ErrorCode.ENCODER_UNAVAILABLE,
        detail="probe: bundled ffmpeg reports no h264_videotoolbox or h264_mf",
    )
