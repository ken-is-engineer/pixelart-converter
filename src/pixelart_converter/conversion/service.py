"""ConversionService: preflight jobs and run supported FFmpeg conversions."""

from __future__ import annotations

import subprocess

from PIL import Image

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.conversion.encoder import (
    ALLOWED_MP4_ENCODERS,
    EncoderResult,
    resolve_encoder,
)
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    JPEGOutput,
    OutputFormat,
    PNGOutput,
    SingleFrame,
)


class ConversionService:
    """Validate that a job can run, then convert.

    GIF conversion supports the common Phase 3 options. MP4 loop-count
    and duration jobs encode with the hardware encoder selected at
    preflight. JPEG and PNG support one validated, zero-based frame.
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
        Single-frame JPEG/PNG jobs validate the GIF and requested index
        before resolving or starting FFmpeg.
        """
        if job.output_format is OutputFormat.GIF:
            argv = FFmpegCommandBuilder().build(job)
            _run_ffmpeg(argv)
            return

        if isinstance(job.output, (JPEGOutput, PNGOutput)):
            if not isinstance(job.output.frames, SingleFrame):
                raise NotImplementedError(
                    "Multi-frame still-image output is not implemented yet."
                )
            self._validate_single_frame(job)
            self.preflight(job)
            argv = FFmpegCommandBuilder().build(job)
            _run_ffmpeg(argv)
            return

        self.preflight(job)
        if job.output_format is OutputFormat.MP4:
            argv = FFmpegCommandBuilder().build(job)
            _run_ffmpeg(argv)
            return

        raise NotImplementedError(
            "This output format is not implemented yet; conversion was not started."
        )

    def _validate_single_frame(self, job: ConversionJob) -> None:
        output = job.output
        if not isinstance(output, (JPEGOutput, PNGOutput)):
            raise TypeError("single-frame validation requires JPEG or PNG output")
        frames = output.frames
        if not isinstance(frames, SingleFrame):
            raise TypeError("single-frame validation requires SingleFrame")

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

        if frames.index >= frame_count:
            raise ConversionError.from_code(
                ErrorCode.INVALID_INPUT,
                message=(
                    f"Frame index {frames.index} is out of range for a GIF "
                    f"with {frame_count} frame(s)."
                ),
                detail=f"requested frame {frames.index}; frame count is {frame_count}",
            )

    def _preflight_mp4(self) -> EncoderResult:
        # Missing bundled binary is a different failure from "HW encoder
        # listed but unavailable". Do not rewrite the user message.
        resolve_ffmpeg()
        encoder = resolve_encoder()
        if encoder is None or encoder.name not in ALLOWED_MP4_ENCODERS:
            raise _mp4_encoder_unavailable(
                detail=(
                    "bundled ffmpeg has no hardware H.264 encoder"
                    if encoder is None
                    else f"refusing encoder {encoder.name!r}"
                ),
            )
        return encoder


def _run_ffmpeg(argv: list[str]) -> None:
    try:
        subprocess.run(argv, check=True)
    except subprocess.CalledProcessError as exc:
        raise ConversionError.from_code(
            ErrorCode.UNKNOWN,
            detail=f"ffmpeg exited {exc.returncode}",
        ) from exc


def _mp4_encoder_unavailable(*, detail: str | None) -> ConversionError:
    """User-facing MP4 failure: HW H.264 missing, no system/GPL ffmpeg fallback."""
    return ConversionError.from_code(
        ErrorCode.ENCODER_UNAVAILABLE,
        detail=detail,
    )
