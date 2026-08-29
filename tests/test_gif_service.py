"""Unit tests for the T3-1 GIF conversion subprocess."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import CommonOptions, ConversionJob, GIFOutput


class ConversionServiceGifTest(unittest.TestCase):
    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_convert_runs_built_argv(self, run, resolve_ffmpeg) -> None:
        job = ConversionJob(
            input_path="in.gif",
            output=GIFOutput("out.gif"),
            common=CommonOptions(width=16, height=12, strip_metadata=True),
        )

        ConversionService().convert(job)

        resolve_ffmpeg.assert_called_once_with()
        run.assert_called_once_with(
            [
                "/bundled/ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                "in.gif",
                "-vf",
                "scale=16:12:flags=neighbor",
                "-map_metadata",
                "-1",
                "out.gif",
            ],
            check=True,
        )

    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["ffmpeg"]),
    )
    def test_ffmpeg_failure_is_classified(self, _run, _resolve_ffmpeg) -> None:
        job = ConversionJob(input_path="in.gif", output=GIFOutput("out.gif"))
        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)
        self.assertEqual(ctx.exception.code, ErrorCode.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
