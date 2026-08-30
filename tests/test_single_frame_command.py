"""Unit tests for single-frame JPEG/PNG FFmpeg argv."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.models import (
    CommonOptions,
    ConversionJob,
    JPEGOutput,
    PNGOutput,
    SingleFrame,
)


class FFmpegCommandBuilderSingleFrameTest(unittest.TestCase):
    def setUp(self) -> None:
        resolver = patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=Path("/bundled/ffmpeg"),
        )
        self.resolve_ffmpeg = resolver.start()
        self.addCleanup(resolver.stop)
        self.builder = FFmpegCommandBuilder()

    def test_index_zero_selects_one_frame_into_one_output_file(self) -> None:
        job = ConversionJob(
            input_path="input.gif",
            output=PNGOutput(frames=SingleFrame(0), output_path="frame.png"),
        )

        argv = self.builder.build(job)

        self.assertEqual(
            argv,
            [
                "/bundled/ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                "input.gif",
                "-vf",
                "select='eq(n,0)'",
                "-vsync",
                "0",
                "-frames:v",
                "1",
                "frame.png",
            ],
        )
        self.assertEqual(argv.count("frame.png"), 1)
        self.assertFalse(any("%" in argument for argument in argv))

    def test_select_and_scale_share_one_filter_chain(self) -> None:
        job = ConversionJob(
            input_path="input.gif",
            output=JPEGOutput(frames=SingleFrame(2), output_path="frame.jpg"),
            common=CommonOptions(width=32, height=24),
        )

        argv = self.builder.build(job)

        self.assertEqual(
            argv[argv.index("-vf") + 1],
            "select='eq(n,2)',scale=32:24:flags=neighbor",
        )
        self.assertEqual(argv[argv.index("-frames:v") + 1], "1")
        self.assertEqual(argv[argv.index("-vsync") + 1], "0")
        self.assertLess(argv.index("-vsync"), argv.index("-frames:v"))

    def test_default_extensions_match_png_and_jpeg(self) -> None:
        cases = (
            (PNGOutput(frames=SingleFrame(0)), "input.png"),
            (JPEGOutput(frames=SingleFrame(0)), "input.jpg"),
        )

        for output, expected in cases:
            with self.subTest(output=type(output).__name__):
                job = ConversionJob(input_path="input.gif", output=output)
                self.assertEqual(self.builder.build(job)[-1], expected)


if __name__ == "__main__":
    unittest.main()
