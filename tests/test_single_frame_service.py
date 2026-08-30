"""Unit tests for single-frame JPEG/PNG service validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_valid_index_runs_single_output(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        output_path = Path(self.temp_dir.name) / "frame.jpg"
        job = ConversionJob(
            input_path=self.input_path,
            output=JPEGOutput(frames=SingleFrame(1), output_path=output_path),
        )

        ConversionService().convert(job)

        service_ffmpeg.assert_called_once_with()
        command_ffmpeg.assert_called_once_with()
        argv = run.call_args.args[0]
        self.assertIn("select='eq(n,1)'", argv)
        self.assertEqual(argv[argv.index("-vsync") + 1], "0")
        self.assertEqual(argv[-1], str(output_path))
        run.assert_called_once_with(argv, check=True)

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

    @patch("pixelart_converter.conversion.command.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_non_gif_input_fails_before_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        png_path = Path(self.temp_dir.name) / "not.gif"
        Image.new("RGB", (2, 2), "green").save(png_path, format="PNG")
        job = ConversionJob(
            input_path=png_path,
            output=PNGOutput(frames=SingleFrame(0), output_path="frame.png"),
        )

        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        run.assert_not_called()
        service_ffmpeg.assert_not_called()
        command_ffmpeg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
