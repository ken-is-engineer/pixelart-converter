"""Typed, validated models describing a conversion job."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import ClassVar, TypeAlias


class OutputFormat(str, Enum):
    """Formats supported by the converter."""

    MP4 = "mp4"
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"


class ScaleAlgorithm(str, Enum):
    """FFmpeg scale algorithms exposed by the application."""

    NEIGHBOR = "neighbor"
    BILINEAR = "bilinear"
    BICUBIC = "bicubic"


def _validate_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer greater than or equal to 1")


def _validate_frame_index(value: object, name: str = "frame index") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _optional_path(value: str | Path | None, name: str) -> Path | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{name} must not be empty")
    return Path(value)


@dataclass(frozen=True, slots=True)
class CommonOptions:
    """Options shared by every output format."""

    width: int | None = None
    height: int | None = None
    scale_algorithm: ScaleAlgorithm = ScaleAlgorithm.NEIGHBOR
    strip_metadata: bool = False

    def __post_init__(self) -> None:
        if self.width is not None:
            _validate_positive_int(self.width, "width")
        if self.height is not None:
            _validate_positive_int(self.height, "height")
        if not isinstance(self.scale_algorithm, ScaleAlgorithm):
            raise ValueError("scale_algorithm must be a ScaleAlgorithm")
        if not isinstance(self.strip_metadata, bool):
            raise ValueError("strip_metadata must be a bool")


@dataclass(frozen=True, slots=True)
class MP4Options:
    """MP4 playback length, expressed in exactly one of two ways."""

    loop_count: int | None = None
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if (self.loop_count is None) == (self.duration_seconds is None):
            raise ValueError(
                "exactly one of loop_count or duration_seconds must be provided"
            )
        if self.loop_count is not None:
            _validate_positive_int(self.loop_count, "loop_count")
        if self.duration_seconds is not None:
            duration = self.duration_seconds
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (int, float))
                or not math.isfinite(duration)
                or duration <= 0
            ):
                raise ValueError("duration_seconds must be a positive finite number")


@dataclass(frozen=True, slots=True)
class SingleFrame:
    """Select one zero-based frame index."""

    index: int

    def __post_init__(self) -> None:
        _validate_frame_index(self.index)


@dataclass(frozen=True, slots=True)
class FrameRange:
    """Select an inclusive range of zero-based frame indices."""

    start: int
    end: int

    def __post_init__(self) -> None:
        _validate_frame_index(self.start, "range start")
        _validate_frame_index(self.end, "range end")
        if self.start > self.end:
            raise ValueError("frame range start must not be greater than end")


FrameItem: TypeAlias = int | FrameRange


@dataclass(frozen=True, slots=True)
class MultipleFrames:
    """Select a non-empty comma-list of indices and/or inclusive ranges."""

    items: tuple[FrameItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise ValueError("multiple frame items must be provided as a tuple")
        if not self.items:
            raise ValueError("multiple frame selection must not be empty")
        for item in self.items:
            if isinstance(item, FrameRange):
                continue
            _validate_frame_index(item)


@dataclass(frozen=True, slots=True)
class AllFrames:
    """Select every frame."""


FrameSelection: TypeAlias = SingleFrame | MultipleFrames | AllFrames


def _validate_frame_selection(frames: object) -> None:
    if not isinstance(frames, (SingleFrame, MultipleFrames, AllFrames)):
        raise ValueError(
            "frames must be SingleFrame, MultipleFrames, or AllFrames"
        )


@dataclass(frozen=True, slots=True)
class MP4Output:
    options: MP4Options
    output_path: str | Path | None = None
    format: ClassVar[OutputFormat] = OutputFormat.MP4

    def __post_init__(self) -> None:
        if not isinstance(self.options, MP4Options):
            raise ValueError("MP4 output requires MP4Options")
        object.__setattr__(
            self, "output_path", _optional_path(self.output_path, "output_path")
        )


@dataclass(frozen=True, slots=True)
class JPEGOutput:
    frames: FrameSelection
    output_path: str | Path | None = None
    format: ClassVar[OutputFormat] = OutputFormat.JPEG

    def __post_init__(self) -> None:
        _validate_frame_selection(self.frames)
        object.__setattr__(
            self, "output_path", _optional_path(self.output_path, "output_path")
        )


@dataclass(frozen=True, slots=True)
class PNGOutput:
    frames: FrameSelection
    output_path: str | Path | None = None
    format: ClassVar[OutputFormat] = OutputFormat.PNG

    def __post_init__(self) -> None:
        _validate_frame_selection(self.frames)
        object.__setattr__(
            self, "output_path", _optional_path(self.output_path, "output_path")
        )


@dataclass(frozen=True, slots=True)
class GIFOutput:
    """GIF has no format-specific options."""

    output_path: str | Path | None = None
    format: ClassVar[OutputFormat] = OutputFormat.GIF

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "output_path", _optional_path(self.output_path, "output_path")
        )


Output: TypeAlias = MP4Output | JPEGOutput | PNGOutput | GIFOutput


@dataclass(frozen=True, slots=True)
class ConversionJob:
    """A complete request to convert one GIF."""

    input_path: str | Path
    output: Output
    common: CommonOptions = field(default_factory=CommonOptions)

    def __post_init__(self) -> None:
        input_path = _optional_path(self.input_path, "input_path")
        if input_path is None:  # Kept explicit for type checkers and future changes.
            raise ValueError("input_path is required")
        object.__setattr__(self, "input_path", input_path)
        if not isinstance(self.output, (MP4Output, JPEGOutput, PNGOutput, GIFOutput)):
            raise ValueError("output must be a supported output model")
        if not isinstance(self.common, CommonOptions):
            raise ValueError("common must be CommonOptions")

    @property
    def output_format(self) -> OutputFormat:
        return self.output.format

    def resolved_output_path(self) -> Path:
        """Return the explicit output path or a safe default without touching disk."""

        if self.output.output_path is not None:
            return Path(self.output.output_path)
        input_path = Path(self.input_path)
        if self.output_format is OutputFormat.GIF:
            return input_path.with_name(f"{input_path.stem}_converted.gif")
        suffix = ".jpg" if self.output_format is OutputFormat.JPEG else (
            f".{self.output_format.value}"
        )
        return input_path.with_suffix(suffix)
