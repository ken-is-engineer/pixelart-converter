"""Unit tests for the T3-6 GIF conversion subprocess."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import CommonOptions, ConversionJob, GIFOutput


class ConversionServiceGifTest(unittest.TestCase):
    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.Popen")
    def test_convert_runs_built_argv(self, popen, resolve_ffmpeg) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "out.gif"
            job = ConversionJob(
                input_path="in.gif",
                output=GIFOutput(output_path),
                common=CommonOptions(width=16, height=12, strip_metadata=True),
            )
            process = Mock()
            process.stdout = io.StringIO("")
            process.stderr = io.StringIO("")
            process.wait.return_value = 0
            process.poll.return_value = 0

            def create_output(argv, **_kwargs):
                Path(argv[-1]).write_bytes(b"gif")
                return process

            popen.side_effect = create_output

            ConversionService().convert(job)

            resolve_ffmpeg.assert_called_once_with()
            argv = popen.call_args.args[0]
            self.assertEqual(
                argv[:-1],
                [
                    "/bundled/ffmpeg",
                    "-nostdin",
                    "-y",
                    "-i",
                    "in.gif",
                    "-filter_complex",
                    "[0:v]scale=16:12:flags=neighbor,split[s0][s1];"
                    "[s0]palettegen=reserve_transparent=1[p];"
                    "[s1][p]paletteuse=dither=none",
                    "-map_metadata",
                    "-1",
                    "-vsync",
                    "0",
                    "-progress",
                    "pipe:1",
                    "-nostats",
                ],
            )
            self.assertEqual(Path(argv[-1]).name, "out.gif")
            self.assertEqual(output_path.read_bytes(), b"gif")

    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.Popen")
    def test_ffmpeg_failure_is_classified(self, popen, _resolve_ffmpeg) -> None:
        process = Mock()
        process.stdout = io.StringIO("")
        process.stderr = io.StringIO("")
        process.wait.return_value = 1
        process.poll.return_value = 1
        popen.return_value = process
        job = ConversionJob(input_path="in.gif", output=GIFOutput("out.gif"))
        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)
        self.assertEqual(ctx.exception.code, ErrorCode.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
