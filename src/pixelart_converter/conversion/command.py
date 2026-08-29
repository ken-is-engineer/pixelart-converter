"""Build FFmpeg argv from typed conversion jobs."""

from __future__ import annotations

from decimal import Decimal

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.encoder import ALLOWED_MP4_ENCODERS, EncoderResolver
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    JPEGOutput,
    MP4Options,
    MP4Output,
    OutputFormat,
    PNGOutput,
    SingleFrame,
)


class FFmpegCommandBuilder:
    """Build FFmpeg arguments without invoking a shell."""

    def build(self, job: ConversionJob) -> list[str]:
        """Return argv with common options, then format-specific ones.

        MP4 jobs resolve a hardware encoder via EncoderResolver. Loop-count
        uses ``-stream_loop N-1``; duration uses infinite input loop plus
        output ``-t``.
        """

        argv = [str(resolve_ffmpeg()), "-nostdin", "-y"]
        argv.extend(self._input_args(job))

        filters = self._video_filters(job)
        if filters:
            argv.extend(["-vf", ",".join(filters)])

        common = job.common
        if common.strip_metadata:
            argv.extend(["-map_metadata", "-1"])

        argv.extend(self._format_output_args(job))
        argv.append(str(job.resolved_output_path()))
        return argv

    def _input_args(self, job: ConversionJob) -> list[str]:
        argv: list[str] = []
        if job.output_format is OutputFormat.MP4:
            argv.extend(self._mp4_stream_loop_args(job))
        argv.extend(["-i", str(job.input_path)])
        return argv

    def _video_filters(self, job: ConversionJob) -> list[str]:
        filters: list[str] = []
        if isinstance(job.output, (JPEGOutput, PNGOutput)) and isinstance(
            job.output.frames, SingleFrame
        ):
            filters.append(f"select='eq(n,{job.output.frames.index})'")

        common = job.common
        if common.width is not None or common.height is not None:
            width = common.width if common.width is not None else -1
            height = common.height if common.height is not None else -1
            filters.append(
                f"scale={width}:{height}:flags={common.scale_algorithm.value}"
            )
        return filters

    def _mp4_stream_loop_args(self, job: ConversionJob) -> list[str]:
        """Emit ``-stream_loop`` before ``-i`` for MP4 playback length.

        Loop-count N maps to extra repeats ``N-1`` (FFmpeg counts extra
        plays, not total plays). N=1 → ``-stream_loop 0`` (equivalent to
        omitting the flag; always emitted so the off-by-one mapping stays
        visible in argv and tests). Duration T uses infinite input loop
        (``-stream_loop -1``) so a short GIF repeats until ``-t T``.
        """

        options = _mp4_options(job)
        if options.duration_seconds is not None:
            return ["-stream_loop", "-1"]
        loop_count = options.loop_count
        if loop_count is None:
            raise ConversionError.from_code(
                ErrorCode.UNKNOWN,
                detail="MP4 job is missing loop_count after duration check",
            )
        extra_repeats = loop_count - 1
        return ["-stream_loop", str(extra_repeats)]

    def _format_output_args(self, job: ConversionJob) -> list[str]:
        if isinstance(job.output, (JPEGOutput, PNGOutput)) and isinstance(
            job.output.frames, SingleFrame
        ):
            return ["-frames:v", "1"]
        if job.output_format is not OutputFormat.MP4:
            return []
        options = _mp4_options(job)
        encoder = EncoderResolver().resolve()
        if encoder is None or encoder.name not in ALLOWED_MP4_ENCODERS:
            raise ConversionError.from_code(
                ErrorCode.ENCODER_UNAVAILABLE,
                detail=(
                    "bundled ffmpeg has no hardware H.264 encoder"
                    if encoder is None
                    else f"refusing encoder {encoder.name!r}"
                ),
            )
        argv = [
            "-c:v",
            encoder.name,
            "-an",
            "-movflags",
            "+faststart",
        ]
        if options.duration_seconds is not None:
            argv.extend(["-t", _format_duration(options.duration_seconds)])
        return argv


def _mp4_options(job: ConversionJob) -> MP4Options:
    if not isinstance(job.output, MP4Output):
        raise TypeError("MP4 argv requires an MP4Output job")
    return job.output.options


def _format_duration(seconds: float) -> str:
    """Render seconds for FFmpeg ``-t`` without scientific notation.

    ``format(x, "g")`` switches to ``1e-05`` below 1e-4, which FFmpeg's
    option parser does not accept as a time.
    """

    text = format(Decimal.from_float(seconds), "f")
    if "e" in text.lower():
        raise ValueError(f"duration must not use scientific notation: {text!r}")
    return text
