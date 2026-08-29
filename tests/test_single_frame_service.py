"""Unit tests for single-frame JPEG/PNG service validation."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    ConversionJob,
    JPEGOutput,
    PNGOutput,
    SingleFrame,
)


class ConversionServiceSingleFrameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.input_path = Path(self.temp_dir.name) / "two-frames.gif"
        first = Image.new("RGB", (2, 2), "red")
        second = Image.new("RGB", (2, 2), "blue")
        first.save(
            self.input_path,
            save_all=True,
            append_images=[second],
            duration=100,
            loop=0,
        )

    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.Popen")
    def test_valid_index_runs_single_output(
        self, popen, service_ffmpeg, command_ffmpeg
    ) -> None:
        output_path = Path(self.temp_dir.name) / "frame.jpg"
        job = ConversionJob(
            input_path=self.input_path,
            output=JPEGOutput(frames=SingleFrame(1), output_path=output_path),
        )
        process = Mock()
        process.stdout = io.StringIO("")
        process.stderr = io.StringIO("")
        process.wait.return_value = 0
        process.poll.return_value = 0

        def create_output(argv, **_kwargs):
            Path(argv[-1]).write_bytes(b"jpeg")
            return process

        popen.side_effect = create_output

        ConversionService().convert(job)

        service_ffmpeg.assert_called_once_with()
        command_ffmpeg.assert_called_once_with()
        argv = popen.call_args.args[0]
        self.assertIn("select='eq(n,1)'", argv)
        self.assertEqual(argv[-4:-1], ["-progress", "pipe:1", "-nostats"])
        self.assertEqual(Path(argv[-1]).name, output_path.name)
        self.assertEqual(output_path.read_bytes(), b"jpeg")

    @patch("pixelart_converter.conversion.command.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_out_of_range_fails_before_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        job = ConversionJob(
            input_path=self.input_path,
            output=PNGOutput(frames=SingleFrame(2), output_path="frame.png"),
        )

        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("out of range", ctx.exception.message)
        service_ffmpeg.assert_not_called()
        command_ffmpeg.assert_not_called()
        run.assert_not_called()

    @patch("pixelart_converter.conversion.command.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_missing_input_is_invalid_before_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        job = ConversionJob(
            input_path=Path(self.temp_dir.name) / "missing.gif",
            output=JPEGOutput(frames=SingleFrame(0), output_path="frame.jpg"),
        )

        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        service_ffmpeg.assert_not_called()
        command_ffmpeg.assert_not_called()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
