"""Unit tests for H.264 encoder probing and selection."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.encoder import EncoderResolver
from pixelart_converter.errors import ConversionError, ErrorCode


def _encoder_output(*names: str) -> str:
    lines = [
        "Encoders:",
        " V..... = Video",
        " ------",
    ]
    lines.extend(f" V..... {name:<24} test encoder" for name in names)
    return "\n".join(lines)


def _probe_result(*names: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=_encoder_output(*names),
        stderr="",
    )


class EncoderResolverTest(unittest.TestCase):
    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_macos_selects_videotoolbox(
        self, system, run, resolve_ffmpeg
    ) -> None:
        system.return_value = "Darwin"
        run.return_value = _probe_result("libopenh264", "h264_videotoolbox")

        result = EncoderResolver().resolve()

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "h264_videotoolbox")
        resolve_ffmpeg.assert_called_once_with()
        run.assert_called_once_with(
            ["/bundled/ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10.0,
        )

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("C:/bundled/ffmpeg.exe"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_windows_selects_media_foundation(
        self, system, run, _resolve_ffmpeg
    ) -> None:
        system.return_value = "Windows"
        run.return_value = _probe_result("h264_mf")

        result = EncoderResolver().resolve()

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "h264_mf")

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_libx264_is_logged_but_not_selected(
        self, system, run, _resolve_ffmpeg
    ) -> None:
        system.return_value = "Darwin"
        run.return_value = _probe_result("libx264")

        with self.assertLogs(
            "pixelart_converter.conversion.encoder", level="WARNING"
        ) as logs:
            result = EncoderResolver().resolve()

        self.assertIsNone(result)
        self.assertTrue(any("libx264" in message for message in logs.output))

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_native_wins_even_when_libx264_is_also_listed(
        self, system, run, _resolve_ffmpeg
    ) -> None:
        system.return_value = "Darwin"
        run.return_value = _probe_result("libx264", "h264_videotoolbox")

        result = EncoderResolver().resolve()

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "h264_videotoolbox")

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_wrong_os_hardware_encoder_is_not_selected(
        self, system, run, _resolve_ffmpeg
    ) -> None:
        system.return_value = "Darwin"
        run.return_value = _probe_result("h264_mf")

        self.assertIsNone(EncoderResolver().resolve())

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    def test_empty_encoder_list_returns_none(self, run, _resolve_ffmpeg) -> None:
        run.return_value = _probe_result()
        self.assertIsNone(EncoderResolver().resolve())

    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.resolve_ffmpeg")
    def test_missing_ffmpeg_error_propagates(
        self, resolve_ffmpeg, run
    ) -> None:
        expected = ConversionError.from_code(
            ErrorCode.ENCODER_UNAVAILABLE,
            detail="bundled ffmpeg missing",
        )
        resolve_ffmpeg.side_effect = expected

        with self.assertRaises(ConversionError) as raised:
            EncoderResolver().resolve()

        self.assertIs(raised.exception, expected)
        run.assert_not_called()

    @patch(
        "pixelart_converter.conversion.encoder.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.encoder.subprocess.run")
    @patch("pixelart_converter.conversion.encoder.platform.system")
    def test_libopenh264_is_logged_but_not_selected(
        self, system, run, _resolve_ffmpeg
    ) -> None:
        system.return_value = "Darwin"
        run.return_value = _probe_result("libopenh264")

        with self.assertLogs(
            "pixelart_converter.conversion.encoder", level="WARNING"
        ) as logs:
            result = EncoderResolver().resolve()

        self.assertIsNone(result)
        self.assertTrue(
            any("libopenh264" in message for message in logs.output)
        )


if __name__ == "__main__":
    unittest.main()
