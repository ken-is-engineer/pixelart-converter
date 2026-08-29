"""ConversionService: preflight jobs and run supported FFmpeg conversions."""

from __future__ import annotations

import subprocess

from PIL import Image

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.conversion.encoder import EncoderResult, resolve_encoder
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    FrameRange,
    JPEGOutput,
    MultipleFrames,
    OutputFormat,
    PNGOutput,
    SingleFrame,
)


class ConversionService:
    """Validate that a job can run, then convert.

    GIF conversion supports the common Phase 3 options. MP4 loop-count
    and duration jobs encode with the hardware encoder selected at
    preflight. JPEG and PNG frame selections are validated before FFmpeg.
    """

    def preflight(self, job: ConversionJob) -> EncoderResult | None:
        """Ensure bundled ffmpeg (and for MP4, a HW encoder) is available.

        Never searches PATH. Does not start an encode subprocess.

        Returns the selected encoder for MP4, or ``None`` for other formats.
        """
        if job.output_format is OutputFormat.MP4:
            return self._preflight_mp4()
        resolve_ffmpeg()
        return None

    def convert(self, job: ConversionJob) -> None:
        """Preflight, then encode.

        GIF output uses the common command builder. MP4 jobs invoke the
        builder (hardware ``-c:v`` only) and a mockable subprocess.
        JPEG/PNG jobs validate the GIF and every requested index before
        resolving or starting FFmpeg.
        """
        if job.output_format is OutputFormat.GIF:
            argv = FFmpegCommandBuilder().build(job)
            subprocess.run(argv, check=True)
            return

        if isinstance(job.output, (JPEGOutput, PNGOutput)):
            self._validate_still_frames(job)
            self.preflight(job)
            argv = FFmpegCommandBuilder().build(job)
            subprocess.run(argv, check=True)
            return

        self.preflight(job)
        if job.output_format is OutputFormat.MP4:
            argv = FFmpegCommandBuilder().build(job)
            subprocess.run(argv, check=True)
            return

        raise NotImplementedError(
            "This output format is not implemented yet; conversion was not started."
        )

    def _validate_still_frames(self, job: ConversionJob) -> None:
        output = job.output
        assert isinstance(output, (JPEGOutput, PNGOutput))

        try:
            with Image.open(job.input_path) as image:
                if image.format != "GIF":
                    raise ConversionError.from_code(
                        ErrorCode.INVALID_INPUT,
                        detail=f"input format is {image.format!r}, expected GIF",
                    )
                frame_count = image.n_frames
        except (OSError, ValueError) as exc:
            raise ConversionError.from_code(
                ErrorCode.INVALID_INPUT,
                detail=f"could not read GIF frame count: {exc}",
            ) from exc

        invalid_index = _first_out_of_range_index(output.frames, frame_count)
        if invalid_index is not None:
            raise ConversionError.from_code(
                ErrorCode.INVALID_INPUT,
                message=(
                    f"Frame index {invalid_index} is out of range for a GIF "
                    f"with {frame_count} frame(s)."
                ),
                detail=(
                    f"requested frame {invalid_index}; frame count is {frame_count}"
                ),
            )

    def _preflight_mp4(self) -> EncoderResult:
        try:
            resolve_ffmpeg()
        except ConversionError as exc:
            if exc.code is ErrorCode.ENCODER_UNAVAILABLE:
                raise _mp4_encoder_unavailable(detail=exc.detail) from exc
            raise
        encoder = resolve_encoder()
        if encoder is None:
            raise _mp4_encoder_unavailable(
                detail="bundled ffmpeg has no hardware H.264 encoder",
            )
        return encoder


def _mp4_encoder_unavailable(*, detail: str | None) -> ConversionError:
    """User-facing MP4 failure: HW H.264 missing, no system/GPL ffmpeg fallback."""
    return ConversionError.from_code(
        ErrorCode.ENCODER_UNAVAILABLE,
        detail=detail,
    )


def _first_out_of_range_index(
    frames: object, frame_count: int
) -> int | None:
    if isinstance(frames, SingleFrame):
        return frames.index if frames.index >= frame_count else None
    if isinstance(frames, MultipleFrames):
        for item in frames.items:
            if isinstance(item, FrameRange):
                if item.end >= frame_count:
                    return max(item.start, frame_count)
            elif item >= frame_count:
                return item
    return None
