"""Unit tests for the T3-2 MP4 loop-count conversion subprocess."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.encoder import EncoderResult
from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.models import (
    CommonOptions,
    ConversionJob,
    MP4Options,
    MP4Output,
)


def _loop_job(*, loop_count: int = 3) -> ConversionJob:
    return ConversionJob(
        input_path="in.gif",
        output=MP4Output(
            options=MP4Options(loop_count=loop_count),
            output_path="out.mp4",
        ),
        common=CommonOptions(width=16, height=12, strip_metadata=True),
    )


class ConversionServiceMp4LoopTest(unittest.TestCase):
    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.command.EncoderResolver")
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=EncoderResult(name="h264_videotoolbox"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_convert_runs_loop_count_argv(
        self, run, _resolve_encoder, encoder_cls, command_ffmpeg, _service_ffmpeg
    ) -> None:
        encoder_cls.return_value.resolve.return_value = EncoderResult(
            name="h264_videotoolbox"
        )

        ConversionService().convert(_loop_job(loop_count=3))

        command_ffmpeg.assert_called_once_with()
        argv = run.call_args.args[0]
        self.assertEqual(run.call_args.kwargs, {"check": True})
        self.assertEqual(
            argv,
            [
                "/bundled/ffmpeg",
                "-stream_loop",
                "2",
                "-i",
                "in.gif",
                "-vf",
                "scale=16:12:flags=neighbor",
                "-map_metadata",
                "-1",
                "-c:v",
                "h264_videotoolbox",
                "-an",
                "-movflags",
                "+faststart",
                "out.mp4",
            ],
        )
        self.assertNotIn("libx264", argv)
        self.assertNotIn("-t", argv)
        self.assertNotEqual(argv[0], "ffmpeg")

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=EncoderResult(name="h264_mf"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_duration_mode_does_not_start_encode(
        self, run, _resolve_encoder, _resolve_ffmpeg
    ) -> None:
        job = ConversionJob(
            input_path="in.gif",
            output=MP4Output(
                options=MP4Options(duration_seconds=1.5),
                output_path="out.mp4",
            ),
        )

        with self.assertRaises(NotImplementedError):
            ConversionService().convert(job)

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
