"""Unit tests for MP4 loop-count and duration conversion subprocesses."""

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


def _duration_job(*, duration_seconds: float = 2.5) -> ConversionJob:
    return ConversionJob(
        input_path="in.gif",
        output=MP4Output(
            options=MP4Options(duration_seconds=duration_seconds),
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
                "-nostdin",
                "-y",
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
        "pixelart_converter.conversion.command.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.command.EncoderResolver")
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=EncoderResult(name="h264_videotoolbox"),
    )
    @patch("pixelart_converter.conversion.service.subprocess.run")
    def test_convert_runs_duration_argv(
        self, run, _resolve_encoder, encoder_cls, command_ffmpeg, _service_ffmpeg
    ) -> None:
        encoder_cls.return_value.resolve.return_value = EncoderResult(
            name="h264_videotoolbox"
        )

        ConversionService().convert(_duration_job(duration_seconds=2.5))

        command_ffmpeg.assert_called_once_with()
        argv = run.call_args.args[0]
        self.assertEqual(run.call_args.kwargs, {"check": True})
        self.assertEqual(
            argv,
            [
                "/bundled/ffmpeg",
                "-nostdin",
                "-y",
                "-stream_loop",
                "-1",
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
                "-t",
                "2.5",
                "out.mp4",
            ],
        )
        self.assertNotIn("libx264", argv)
        self.assertNotEqual(argv[0], "ffmpeg")


if __name__ == "__main__":
    unittest.main()
