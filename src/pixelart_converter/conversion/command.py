"""Build FFmpeg argv from typed conversion jobs."""

from __future__ import annotations

from pixelart_converter.conversion.binary import resolve_ffmpeg
from pixelart_converter.models import ConversionJob


class FFmpegCommandBuilder:
    """Build common FFmpeg arguments without invoking a shell."""

    def build(self, job: ConversionJob) -> list[str]:
        """Return argv with common options in FFmpeg-compatible order."""

        argv = [
            str(resolve_ffmpeg()),
            "-i",
            str(job.input_path),
        ]

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

        argv.append(str(job.resolved_output_path()))
        return argv
