"""Unit tests for conversion job models."""

from pathlib import Path
import unittest

from pixelart_converter.models import (
    AllFrames,
    CommonOptions,
    ConversionJob,
    FrameRange,
    GIFOutput,
    JPEGOutput,
    MP4Options,
    MP4Output,
    MultipleFrames,
    OutputFormat,
    PNGOutput,
    ScaleAlgorithm,
    SingleFrame,
)


class MP4OptionsTest(unittest.TestCase):
    def test_loop_count_and_duration_are_mutually_exclusive(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            MP4Options(loop_count=2, duration_seconds=3.5)

    def test_one_playback_limit_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            MP4Options()

    def test_valid_loop_and_duration_can_each_be_constructed(self) -> None:
        self.assertEqual(MP4Options(loop_count=1).loop_count, 1)
        self.assertEqual(MP4Options(duration_seconds=0.5).duration_seconds, 0.5)

    def test_invalid_playback_limits_are_rejected(self) -> None:
        for value in (0, -1, 1.5, True):
            with self.subTest(loop_count=value):
                with self.assertRaises(ValueError):
                    MP4Options(loop_count=value)  # type: ignore[arg-type]
        for value in (0, -0.1, float("inf"), float("nan"), True):
            with self.subTest(duration_seconds=value):
                with self.assertRaises(ValueError):
                    MP4Options(duration_seconds=value)


class FrameSelectionTest(unittest.TestCase):
    def test_valid_frame_selection_variants(self) -> None:
        self.assertEqual(SingleFrame(0).index, 0)
        self.assertEqual(
            MultipleFrames((0, 2, FrameRange(4, 6))).items,
            (0, 2, FrameRange(4, 6)),
        )
        self.assertIsInstance(AllFrames(), AllFrames)

    def test_invalid_frames_are_rejected(self) -> None:
        invalid_constructors = (
            lambda: SingleFrame(-1),
            lambda: FrameRange(-1, 2),
            lambda: FrameRange(3, 2),
            lambda: MultipleFrames(()),
            lambda: MultipleFrames((0, -1)),
        )
        for constructor in invalid_constructors:
            with self.subTest(constructor=constructor):
                with self.assertRaises(ValueError):
                    constructor()

    def test_image_output_requires_typed_frame_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "frames must be"):
            PNGOutput(frames=(0, 1))  # type: ignore[arg-type]


class ConversionJobTest(unittest.TestCase):
    def test_common_defaults(self) -> None:
        options = CommonOptions()

        self.assertIsNone(options.width)
        self.assertIsNone(options.height)
        self.assertIs(options.scale_algorithm, ScaleAlgorithm.NEIGHBOR)
        self.assertFalse(options.strip_metadata)

    def test_invalid_dimensions_are_rejected(self) -> None:
        for dimensions in ({"width": 0}, {"height": -1}):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(ValueError):
                    CommonOptions(**dimensions)

    def test_each_output_format_can_be_constructed(self) -> None:
        outputs = (
            MP4Output(MP4Options(loop_count=2)),
            JPEGOutput(SingleFrame(0)),
            PNGOutput(AllFrames()),
            GIFOutput(),
        )

        jobs = tuple(ConversionJob("input.gif", output) for output in outputs)

        self.assertEqual(
            tuple(job.output_format for job in jobs),
            (
                OutputFormat.MP4,
                OutputFormat.JPEG,
                OutputFormat.PNG,
                OutputFormat.GIF,
            ),
        )

    def test_paths_and_common_options_are_represented(self) -> None:
        job = ConversionJob(
            input_path="sprites/input.gif",
            output=PNGOutput(
                MultipleFrames((0, FrameRange(2, 4))),
                output_path="exports/frame.png",
            ),
            common=CommonOptions(
                width=320,
                height=240,
                scale_algorithm=ScaleAlgorithm.BICUBIC,
                strip_metadata=True,
            ),
        )

        self.assertEqual(job.input_path, Path("sprites/input.gif"))
        self.assertEqual(job.output.output_path, Path("exports/frame.png"))
        self.assertEqual(job.common.width, 320)
        self.assertEqual(job.common.height, 240)
        self.assertTrue(job.common.strip_metadata)

    def test_default_output_paths(self) -> None:
        png_job = ConversionJob("sprites/input.gif", PNGOutput(AllFrames()))
        gif_job = ConversionJob("sprites/input.gif", GIFOutput())

        self.assertEqual(png_job.resolved_output_path(), Path("sprites/input.png"))
        self.assertEqual(
            gif_job.resolved_output_path(), Path("sprites/input_converted.gif")
        )

    def test_gif_needs_no_format_specific_options(self) -> None:
        job = ConversionJob("input.gif", GIFOutput("output.gif"))

        self.assertEqual(job.output_format, OutputFormat.GIF)
        self.assertEqual(job.output.output_path, Path("output.gif"))


if __name__ == "__main__":
    unittest.main()
