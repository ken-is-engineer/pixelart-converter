"""Unit tests for common FFmpeg argv construction (T3-1, T3-6).

Visual resize and ffprobe metadata checks are deferred when no bundled binary
is present; these tests intentionally verify argv without requiring FFmpeg.
GIF jobs use a split-filter palette graph rather than a naive ``-vf`` encode.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.models import (
    CommonOptions,
    ConversionJob,
    GIFOutput,
    ScaleAlgorithm,
)


def _job(*, common: CommonOptions | None = None) -> ConversionJob:
    return ConversionJob(
        input_path="input.gif",
        output=GIFOutput("named-output.gif"),
        common=common or CommonOptions(),
    )


def _filter_complex(argv: list[str]) -> str:
    return argv[argv.index("-filter_complex") + 1]


class FFmpegCommandBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        resolver = patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=Path("/bundled/ffmpeg"),
        )
        self.resolve_ffmpeg = resolver.start()
        self.addCleanup(resolver.stop)
        self.builder = FFmpegCommandBuilder()

    def test_no_size_omits_scale_filter(self) -> None:
        argv = self.builder.build(_job())

        self.assertNotIn("-vf", argv)
        self.assertFalse(any("scale=" in arg for arg in argv))

    def test_size_uses_neighbor_by_default(self) -> None:
        argv = self.builder.build(
            _job(common=CommonOptions(width=32, height=24))
        )

        self.assertIn("scale=32:24:flags=neighbor", _filter_complex(argv))

    def test_bilinear_and_bicubic_flags_are_used(self) -> None:
        for algorithm in (ScaleAlgorithm.BILINEAR, ScaleAlgorithm.BICUBIC):
            with self.subTest(algorithm=algorithm):
                argv = self.builder.build(
                    _job(
                        common=CommonOptions(
                            width=32,
                            height=24,
                            scale_algorithm=algorithm,
                        )
                    )
                )
                self.assertIn(
                    f"scale=32:24:flags={algorithm.value}",
                    _filter_complex(argv),
                )

    def test_one_omitted_dimension_preserves_aspect_ratio(self) -> None:
        argv = self.builder.build(_job(common=CommonOptions(width=32)))

        self.assertIn("scale=32:-1:flags=neighbor", _filter_complex(argv))

    def test_strip_metadata_adds_map_metadata_minus_one(self) -> None:
        argv = self.builder.build(
            _job(common=CommonOptions(strip_metadata=True))
        )

        index = argv.index("-map_metadata")
        self.assertEqual(argv[index + 1], "-1")

    def test_preserve_metadata_omits_map_metadata(self) -> None:
        argv = self.builder.build(_job())

        self.assertNotIn("-map_metadata", argv)

    def test_output_filename_is_last(self) -> None:
        argv = self.builder.build(_job())

        self.assertEqual(argv[-1], "named-output.gif")

    def test_uses_bundled_resolver_and_never_path_ffmpeg(self) -> None:
        with patch(
            "shutil.which",
            side_effect=AssertionError("must not search PATH"),
        ):
            argv = self.builder.build(_job())

        self.resolve_ffmpeg.assert_called_once_with()
        self.assertEqual(argv[0], "/bundled/ffmpeg")
        self.assertEqual(argv[1:3], ["-nostdin", "-y"])
        self.assertNotEqual(argv[0], "ffmpeg")

    def test_noninteractive_flags_come_before_input(self) -> None:
        argv = self.builder.build(_job())
        self.assertLess(argv.index("-nostdin"), argv.index("-i"))
        self.assertLess(argv.index("-y"), argv.index("-i"))


class FFmpegCommandBuilderGifPaletteTest(unittest.TestCase):
    def setUp(self) -> None:
        resolver = patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=Path("/bundled/ffmpeg"),
        )
        self.resolve_ffmpeg = resolver.start()
        self.addCleanup(resolver.stop)
        self.builder = FFmpegCommandBuilder()

    def test_argv_contains_palettegen_and_paletteuse(self) -> None:
        argv = self.builder.build(_job())

        graph = _filter_complex(argv)
        self.assertIn("palettegen", graph)
        self.assertIn("paletteuse", graph)
        self.assertIn("split", graph)
        self.assertNotIn("-vf", argv)

    def test_scale_runs_before_split_in_the_palette_graph(self) -> None:
        argv = self.builder.build(
            _job(common=CommonOptions(width=32, height=24))
        )

        graph = _filter_complex(argv)
        scale_at = graph.index("scale=32:24:flags=neighbor")
        split_at = graph.index("split")
        palettegen_at = graph.index("palettegen")
        paletteuse_at = graph.index("paletteuse")
        self.assertLess(scale_at, split_at)
        self.assertLess(split_at, palettegen_at)
        self.assertLess(palettegen_at, paletteuse_at)

    def test_strip_metadata_still_emits_map_metadata(self) -> None:
        argv = self.builder.build(
            _job(common=CommonOptions(width=16, height=12, strip_metadata=True))
        )

        self.assertEqual(argv[argv.index("-map_metadata") + 1], "-1")
        self.assertIn("palettegen", _filter_complex(argv))
        self.assertIn("paletteuse", _filter_complex(argv))

    def test_vsync_passthrough_preserves_gif_frame_delay(self) -> None:
        argv = self.builder.build(_job())

        self.assertEqual(argv[argv.index("-vsync") + 1], "0")
        self.assertNotIn("-r", argv)
        self.assertNotIn("fps=", _filter_complex(argv))


if __name__ == "__main__":
    unittest.main()
