"""Unit tests for multi-frame JPEG/PNG service validation."""

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
    FrameRange,
    MultipleFrames,
    PNGOutput,
)


class ConversionServiceMultiFrameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.input_path = Path(self.temp_dir.name) / "three-frames.gif"
        frames = [
            Image.new("RGB", (2, 2), color)
            for color in ("red", "green", "blue")
        ]
        frames[0].save(
            self.input_path,
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
        )

    @patch("pixelart_converter.conversion.command.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_any_out_of_range_list_index_fails_before_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        output_path = Path(self.temp_dir.name) / "list.png"
        job = ConversionJob(
            input_path=self.input_path,
            output=PNGOutput(
                frames=MultipleFrames((0, 3)),
                output_path=output_path,
            ),
        )

        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("Frame index 3", ctx.exception.message)
        self.assertFalse(output_path.exists())
        service_ffmpeg.assert_not_called()
        command_ffmpeg.assert_not_called()
        run.assert_not_called()

    @patch("pixelart_converter.conversion.command.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.resolve_ffmpeg")
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_out_of_range_range_fails_before_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        output_path = Path(self.temp_dir.name) / "range.png"
        job = ConversionJob(
            input_path=self.input_path,
            output=PNGOutput(
                frames=MultipleFrames((FrameRange(1, 4),)),
                output_path=output_path,
            ),
        )

        with self.assertRaises(ConversionError) as ctx:
            ConversionService().convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("Frame index 3", ctx.exception.message)
        self.assertFalse(output_path.exists())
        service_ffmpeg.assert_not_called()
        command_ffmpeg.assert_not_called()
        run.assert_not_called()

    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_inclusive_last_index_starts_ffmpeg(
        self, run, service_ffmpeg, command_ffmpeg
    ) -> None:
        output_path = Path(self.temp_dir.name) / "ok.png"
        job = ConversionJob(
            input_path=self.input_path,
            output=PNGOutput(
                frames=MultipleFrames((FrameRange(0, 2),)),
                output_path=output_path,
            ),
        )

        ConversionService().convert(job)

        service_ffmpeg.assert_called_once_with()
        command_ffmpeg.assert_called_once_with()
        run.assert_called_once()
        argv = run.call_args.args[0]
        self.assertIn("select='between(n,0,2)'", argv)
        self.assertTrue(argv[-1].endswith("ok_%03d.png"))


if __name__ == "__main__":
    unittest.main()
