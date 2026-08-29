"""ConversionService: preflight jobs and run supported FFmpeg conversions."""

from __future__ import annotations

import subprocess

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.conversion.encoder import EncoderResult, resolve_encoder
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob, MP4Output, OutputFormat


class ConversionService:
    """Validate that a job can run, then convert.

    GIF conversion supports the common Phase 3 options. MP4 loop-count
    jobs encode with the hardware encoder selected at preflight. Duration
    MP4 and still-image pipelines remain unavailable until later tasks.
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

        GIF output uses the common command builder. MP4 loop-count jobs
        invoke the builder (hardware ``-c:v`` only) and a mockable
        subprocess. Other formats still run preflight so MP4 fails closed
        when no hardware encoder is available. Duration MP4 is T3-3.
        """
        if job.output_format is OutputFormat.GIF:
            argv = FFmpegCommandBuilder().build(job)
            subprocess.run(argv, check=True)
            return

        self.preflight(job)
        if (
            job.output_format is OutputFormat.MP4
            and isinstance(job.output, MP4Output)
            and job.output.options.loop_count is not None
        ):
            argv = FFmpegCommandBuilder().build(job)
            subprocess.run(argv, check=True)
            return

        raise NotImplementedError(
            "This output format is not implemented yet; conversion was not started."
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
