"""Unit tests for multi-frame JPEG/PNG FFmpeg argv."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.models import (
    AllFrames,
    ConversionJob,
    FrameRange,
    JPEGOutput,
    MultipleFrames,
    PNGOutput,
)


class FFmpegCommandBuilderMultiFrameTest(unittest.TestCase):
    def setUp(self) -> None:
        resolver = patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=Path("/bundled/ffmpeg"),
        )
        self.resolve_ffmpeg = resolver.start()
        self.addCleanup(resolver.stop)
        self.builder = FFmpegCommandBuilder()

    def test_all_frames_use_zero_based_sequence_without_select(self) -> None:
        job = ConversionJob(
            input_path="input.gif",
            output=PNGOutput(frames=AllFrames(), output_path="exports/out.png"),
        )

        argv = self.builder.build(job)

        self.assertEqual(
            argv,
            [
                "/bundled/ffmpeg",
                "-i",
                "input.gif",
                "-vsync",
                "0",
                "-start_number",
                "0",
                "exports/out_%03d.png",
            ],
        )
        self.assertNotIn("-vf", argv)

    def test_range_uses_inclusive_select_and_jpeg_sequence(self) -> None:
        job = ConversionJob(
            input_path="input.gif",
            output=JPEGOutput(
                frames=MultipleFrames((FrameRange(2, 5),)),
                output_path="out.jpg",
            ),
        )

        argv = self.builder.build(job)

        self.assertEqual(
            argv[argv.index("-vf") + 1],
            "select='between(n,2,5)'",
        )
        self.assertEqual(argv[-1], "out_%03d.jpg")
        self.assertEqual(argv[argv.index("-start_number") + 1], "0")

    def test_list_combines_indices_and_ranges_in_one_select(self) -> None:
        job = ConversionJob(
            input_path="input.gif",
            output=PNGOutput(
                frames=MultipleFrames((0, 2, FrameRange(4, 6))),
                output_path="out.png",
            ),
        )

        argv = self.builder.build(job)

        self.assertEqual(
            argv[argv.index("-vf") + 1],
            "select='eq(n,0)+eq(n,2)+between(n,4,6)'",
        )
        self.assertEqual(argv[-1], "out_%03d.png")
        self.assertNotIn("-frames:v", argv)


if __name__ == "__main__":
    unittest.main()
