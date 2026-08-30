"""Build FFmpeg argv from typed conversion jobs."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.encoder import ALLOWED_MP4_ENCODERS, EncoderResolver
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    FrameRange,
    JPEGOutput,
    MP4Options,
    MP4Output,
    MultipleFrames,
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
        output ``-t``. GIF re-encodes with a split-filter palettegen/paletteuse
        graph (one process, two passes) so resized output keeps a global
        palette instead of a naive 256-color quantize.
        """

        argv = [str(resolve_ffmpeg()), "-nostdin", "-y"]
        argv.extend(self._input_args(job))

        if job.output_format is OutputFormat.GIF:
            argv.extend(self._gif_filter_args(job))
        else:
            filters = self._video_filters(job)
            if filters:
                argv.extend(["-vf", ",".join(filters)])

        common = job.common
        if common.strip_metadata:
            argv.extend(["-map_metadata", "-1"])

        argv.extend(self._format_output_args(job))
        argv.append(str(self._output_path(job)))
        return argv

    def _input_args(self, job: ConversionJob) -> list[str]:
        argv: list[str] = []
        if job.output_format is OutputFormat.MP4:
            argv.extend(self._mp4_stream_loop_args(job))
        argv.extend(["-i", str(job.input_path)])
        return argv

    def _video_filters(self, job: ConversionJob) -> list[str]:
        filters: list[str] = []
        if isinstance(job.output, (JPEGOutput, PNGOutput)):
            selection = job.output.frames
            if isinstance(selection, SingleFrame):
                filters.append(f"select='eq(n,{selection.index})'")
            elif isinstance(selection, MultipleFrames):
                expressions = []
                for item in selection.items:
                    if isinstance(item, FrameRange):
                        expressions.append(f"between(n,{item.start},{item.end})")
                    else:
                        expressions.append(f"eq(n,{item})")
                filters.append(f"select='{'+'.join(expressions)}'")

        scale = self._scale_filter(job)
        if scale is not None:
            filters.append(scale)
        return filters

    def _scale_filter(self, job: ConversionJob) -> str | None:
        common = job.common
        if common.width is None and common.height is None:
            return None
        width = common.width if common.width is not None else -1
        height = common.height if common.height is not None else -1
        return f"scale={width}:{height}:flags={common.scale_algorithm.value}"

    def _gif_filter_args(self, job: ConversionJob) -> list[str]:
        """Build a 1-process 2-pass palette graph; scale runs before split.

        ``paletteuse=dither=none`` keeps pixel-art edges crisp. Per-frame
        delay is left to PTS passthrough (``-vsync 0`` in format args) rather
        than an ``fps`` filter or ``-r``, which would rewrite GIF timing.
        """

        chain: list[str] = []
        scale = self._scale_filter(job)
        if scale is not None:
            chain.append(scale)
        chain.append("split[s0][s1]")
        graph = (
            f"[0:v]{','.join(chain)};[s0]palettegen=reserve_transparent=1[p];"
            f"[s1][p]paletteuse=dither=none"
        )
        return ["-filter_complex", graph]

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
        if job.output_format is OutputFormat.GIF:
            return ["-vsync", "0"]
        if isinstance(job.output, (JPEGOutput, PNGOutput)):
            if isinstance(job.output.frames, SingleFrame):
                return ["-vsync", "0", "-frames:v", "1"]
            return ["-vsync", "0", "-start_number", "0"]
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

    def _output_path(self, job: ConversionJob) -> Path:
        output_path = job.resolved_output_path()
        if not isinstance(job.output, (JPEGOutput, PNGOutput)) or isinstance(
            job.output.frames, SingleFrame
        ):
            return output_path
        return output_path.with_name(
            f"{output_path.stem}_%03d{output_path.suffix}"
        )


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
