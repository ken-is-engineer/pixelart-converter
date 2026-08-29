"""Build FFmpeg argv from typed conversion jobs."""

from __future__ import annotations

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.conversion.encoder import EncoderResolver
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob, MP4Options, MP4Output, OutputFormat


class FFmpegCommandBuilder:
    """Build FFmpeg arguments without invoking a shell."""

    def build(self, job: ConversionJob) -> list[str]:
        """Return argv with common options, then format-specific ones.

        MP4 loop-count jobs resolve a hardware encoder via EncoderResolver.
        Duration-limited MP4 (``-t``) is T3-3 and is not assembled here.
        """

        argv = [str(resolve_ffmpeg())]
        argv.extend(self._input_args(job))

        common = job.common
        if common.width is not None or common.height is not None:
            width = common.width if common.width is not None else -1
            height = common.height if common.height is not None else -1
            argv.extend(
                [
                    "-vf",
                    f"scale={width}:{height}:flags={common.scale_algorithm.value}",
                ]
            )

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

    def _mp4_stream_loop_args(self, job: ConversionJob) -> list[str]:
        """Map playback loops N to FFmpeg ``-stream_loop N-1`` before ``-i``.

        FFmpeg's ``-stream_loop`` is the number of *extra* repeats, not the
        total play count. Playing the GIF N times therefore needs ``N-1``.
        N=1 → ``-stream_loop 0`` (equivalent to omitting the flag; always
        emitted so the off-by-one mapping stays visible in argv and tests).
        Duration mode (``-stream_loop -1`` plus ``-t``) is T3-3, not here.
        """

        options = _mp4_options(job)
        loop_count = options.loop_count
        if loop_count is None:
            raise NotImplementedError(
                "MP4 duration encoding is not implemented yet; conversion was not started."
            )
        extra_repeats = loop_count - 1
        return ["-stream_loop", str(extra_repeats)]

    def _format_output_args(self, job: ConversionJob) -> list[str]:
        if job.output_format is not OutputFormat.MP4:
            return []
        options = _mp4_options(job)
        if options.duration_seconds is not None:
            raise NotImplementedError(
                "MP4 duration encoding is not implemented yet; conversion was not started."
            )
        encoder = EncoderResolver().resolve()
        if encoder is None:
            # Service fail-closes first; builder never falls back to libx264.
            raise ConversionError.from_code(
                ErrorCode.ENCODER_UNAVAILABLE,
                detail="bundled ffmpeg has no hardware H.264 encoder",
            )
        return [
            "-c:v",
            encoder.name,
            "-an",
            "-movflags",
            "+faststart",
        ]


def _mp4_options(job: ConversionJob) -> MP4Options:
    if not isinstance(job.output, MP4Output):
        raise TypeError("MP4 argv requires an MP4Output job")
    return job.output.options
