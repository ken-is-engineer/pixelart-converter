"""Unit tests for MP4 loop-count and duration FFmpeg argv (T3-2, T3-3).

No real FFmpeg binary is required: encoder resolution and the bundled
path are mocked. Duration jobs use ``-stream_loop -1`` and output ``-t``;
loop-count jobs must not emit ``-t``.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.command import FFmpegCommandBuilder
from pixelart_converter.conversion.encoder import EncoderResult
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import (
    CommonOptions,
    ConversionJob,
    MP4Options,
    MP4Output,
)


def _mp4_job(
    *,
    loop_count: int | None = 3,
    duration_seconds: float | None = None,
    common: CommonOptions | None = None,
    output_path: str = "out.mp4",
) -> ConversionJob:
    if duration_seconds is not None:
        options = MP4Options(duration_seconds=duration_seconds)
    else:
        options = MP4Options(loop_count=loop_count)
    return ConversionJob(
        input_path="in.gif",
        output=MP4Output(options=options, output_path=output_path),
        common=common or CommonOptions(),
    )


class FFmpegCommandBuilderMp4LoopTest(unittest.TestCase):
    def setUp(self) -> None:
        ffmpeg = patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=Path("/bundled/ffmpeg"),
        )
        self.resolve_ffmpeg = ffmpeg.start()
        self.addCleanup(ffmpeg.stop)

        resolver = patch(
            "pixelart_converter.conversion.command.EncoderResolver",
        )
        self.encoder_cls = resolver.start()
        self.addCleanup(resolver.stop)
        self.encoder_cls.return_value.resolve.return_value = EncoderResult(
            name="h264_videotoolbox"
        )
        self.builder = FFmpegCommandBuilder()

    def test_n1_emits_stream_loop_zero_before_input(self) -> None:
        # FFmpeg stream_loop is extra repeats; N=1 → 0 (omit is equivalent).
        argv = self.builder.build(_mp4_job(loop_count=1))

        i_index = argv.index("-i")
        self.assertEqual(argv[i_index - 2], "-stream_loop")
        self.assertEqual(argv[i_index - 1], "0")
        self.assertEqual(argv[i_index + 1], "in.gif")

    def test_n3_emits_stream_loop_two_before_input(self) -> None:
        argv = self.builder.build(_mp4_job(loop_count=3))

        i_index = argv.index("-i")
        self.assertEqual(argv[i_index - 2], "-stream_loop")
        self.assertEqual(argv[i_index - 1], "2")
        self.assertEqual(argv[i_index + 1], "in.gif")

    def test_encoder_name_is_used_and_libx264_is_absent(self) -> None:
        for name in ("h264_videotoolbox", "h264_mf"):
            with self.subTest(encoder=name):
                self.encoder_cls.return_value.resolve.return_value = EncoderResult(
                    name=name
                )
                argv = self.builder.build(_mp4_job(loop_count=3))
                codec_index = argv.index("-c:v")
                self.assertEqual(argv[codec_index + 1], name)
                self.assertNotIn("libx264", argv)
                self.assertFalse(any("libx264" in arg for arg in argv))

    def test_no_audio_and_mp4_output_path(self) -> None:
        argv = self.builder.build(_mp4_job(loop_count=3, output_path="clip.mp4"))

        self.assertIn("-an", argv)
        self.assertEqual(argv[-1], "clip.mp4")

    def test_common_scale_and_metadata_are_kept(self) -> None:
        argv = self.builder.build(
            _mp4_job(
                loop_count=3,
                common=CommonOptions(width=32, height=24, strip_metadata=True),
            )
        )

        self.assertIn("scale=32:24:flags=neighbor", argv)
        self.assertEqual(argv[argv.index("-map_metadata") + 1], "-1")

    def test_duration_mode_is_not_mixed_into_loop_argv(self) -> None:
        argv = self.builder.build(_mp4_job(loop_count=3))

        self.assertNotIn("-t", argv)
        self.assertNotIn("-stream_loop", argv[argv.index("-i") :])

    def test_duration_2_5_emits_infinite_loop_and_output_t(self) -> None:
        argv = self.builder.build(_mp4_job(duration_seconds=2.5))

        i_index = argv.index("-i")
        self.assertEqual(argv[i_index - 2], "-stream_loop")
        self.assertEqual(argv[i_index - 1], "-1")
        self.assertEqual(argv[i_index + 1], "in.gif")
        self.assertNotIn("-t", argv[:i_index])
        t_index = argv.index("-t")
        self.assertGreater(t_index, i_index)
        self.assertEqual(argv[t_index + 1], "2.5")
        self.assertNotIn("libx264", argv)

    def test_duration_uses_hw_encoder_and_no_audio(self) -> None:
        for name in ("h264_videotoolbox", "h264_mf"):
            with self.subTest(encoder=name):
                self.encoder_cls.return_value.resolve.return_value = EncoderResult(
                    name=name
                )
                argv = self.builder.build(_mp4_job(duration_seconds=2.5))
                self.assertEqual(argv[argv.index("-c:v") + 1], name)
                self.assertIn("-an", argv)
                self.assertEqual(argv[argv.index("-movflags") + 1], "+faststart")
                self.assertNotIn("libx264", argv)
                self.assertFalse(any("libx264" in arg for arg in argv))

    def test_duration_keeps_common_scale_and_metadata(self) -> None:
        argv = self.builder.build(
            _mp4_job(
                duration_seconds=2.5,
                common=CommonOptions(width=32, height=24, strip_metadata=True),
            )
        )

        self.assertIn("scale=32:24:flags=neighbor", argv)
        self.assertEqual(argv[argv.index("-map_metadata") + 1], "-1")
        self.assertEqual(argv[argv.index("-t") + 1], "2.5")

    def test_uses_bundled_resolver_and_never_path_ffmpeg(self) -> None:
        with patch(
            "shutil.which",
            side_effect=AssertionError("must not search PATH"),
        ):
            argv = self.builder.build(_mp4_job(loop_count=3))

        self.resolve_ffmpeg.assert_called_once_with()
        self.assertEqual(argv[0], "/bundled/ffmpeg")
        self.assertEqual(argv[1:3], ["-nostdin", "-y"])
        self.assertNotEqual(argv[0], "ffmpeg")

    def test_duration_uses_bundled_resolver_and_never_path_ffmpeg(self) -> None:
        with patch(
            "shutil.which",
            side_effect=AssertionError("must not search PATH"),
        ):
            argv = self.builder.build(_mp4_job(duration_seconds=2.5))

        self.resolve_ffmpeg.assert_called_once_with()
        self.assertEqual(argv[0], "/bundled/ffmpeg")
        self.assertEqual(argv[1:3], ["-nostdin", "-y"])
        self.assertNotEqual(argv[0], "ffmpeg")
        self.assertNotIn("libx264", argv)

    def test_libx264_from_resolver_is_refused(self) -> None:
        self.encoder_cls.return_value.resolve.return_value = EncoderResult(
            name="libx264"
        )
        with self.assertRaises(ConversionError) as ctx:
            self.builder.build(_mp4_job(loop_count=3))
        self.assertEqual(ctx.exception.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn("libx264", ctx.exception.detail or "")

    def test_tiny_duration_does_not_use_scientific_notation(self) -> None:
        argv = self.builder.build(_mp4_job(duration_seconds=1e-5))
        value = argv[argv.index("-t") + 1]
        self.assertNotIn("e", value.lower())
        self.assertEqual(float(value), 1e-5)


if __name__ == "__main__":
    unittest.main()
