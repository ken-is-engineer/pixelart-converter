"""Unit tests for ConversionService preflight (T2-5)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.binary import ENV_FFMPEG, _ffmpeg_filename
from pixelart_converter.conversion.encoder import EncoderResult
from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode, user_message_for
from pixelart_converter.models import (
    ConversionJob,
    JPEGOutput,
    MP4Options,
    MP4Output,
    SingleFrame,
)
from pixelart_converter.ui.main_window import MainWindow


def _mp4_job() -> ConversionJob:
    return ConversionJob(
        input_path="in.gif",
        output=MP4Output(
            options=MP4Options(loop_count=1),
            output_path="out.mp4",
        ),
    )


def _jpeg_job() -> ConversionJob:
    return ConversionJob(
        input_path="in.gif",
        output=JPEGOutput(frames=SingleFrame(0), output_path="out.jpg"),
    )


def _write_fake_binary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    path.chmod(0o755)
    return path


def _assert_no_system_ffmpeg_advice(message: str) -> None:
    lowered = message.lower()
    for banned in (
        "brew install",
        "apt install",
        "choco install",
        "install ffmpeg",
        "use system",
        "system ffmpeg",
        "system binary",
        "from path",
    ):
        if banned in lowered:
            raise AssertionError(f"message must not advise {banned!r}: {message!r}")


class ConversionServiceMp4Test(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ConversionService()

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=None,
    )
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_mp4_without_encoder_fails_without_encode(
        self, run, popen, resolve_encoder, resolve_ffmpeg
    ) -> None:
        with self.assertRaises(ConversionError) as ctx:
            self.service.convert(_mp4_job())

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertEqual(error.message, user_message_for(ErrorCode.ENCODER_UNAVAILABLE))
        self.assertIn("hardware", error.message.lower())
        self.assertIn("GPL", error.message)
        _assert_no_system_ffmpeg_advice(error.message)
        resolve_ffmpeg.assert_called_once_with()
        resolve_encoder.assert_called_once_with()
        run.assert_not_called()
        popen.assert_not_called()

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=None,
    )
    def test_mp4_preflight_does_not_start_encode(
        self, _resolve_encoder, _resolve_ffmpeg
    ) -> None:
        with (
            patch("subprocess.Popen") as popen,
            patch("subprocess.run") as run,
        ):
            with self.assertRaises(ConversionError) as ctx:
                self.service.preflight(_mp4_job())
            run.assert_not_called()
            popen.assert_not_called()
        self.assertEqual(ctx.exception.code, ErrorCode.ENCODER_UNAVAILABLE)

    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=None,
    )
    def test_mp4_path_decoy_ffmpeg_is_not_used(self, resolve_encoder) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="pixelart-svc-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        decoy = _write_fake_binary(tmp / "decoy-bin" / _ffmpeg_filename())
        bundled = Path("/bundled/ffmpeg")
        decoy_path = str(decoy.parent) + os.pathsep + os.environ.get("PATH", "")

        with patch.dict(os.environ, {"PATH": decoy_path}):
            which_hit = shutil.which(_ffmpeg_filename())
            self.assertIsNotNone(which_hit)
            self.assertEqual(Path(which_hit).resolve(), decoy.resolve())
            with (
                patch(
                    "pixelart_converter.conversion.service.resolve_ffmpeg",
                    return_value=bundled,
                ) as resolve_ffmpeg,
                patch("subprocess.Popen") as popen,
                patch("subprocess.run") as run,
                patch(
                    "shutil.which",
                    side_effect=AssertionError("must not search PATH"),
                ),
            ):
                with self.assertRaises(ConversionError) as ctx:
                    self.service.convert(_mp4_job())

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        _assert_no_system_ffmpeg_advice(error.message)
        resolve_ffmpeg.assert_called_once_with()
        resolve_encoder.assert_called_once_with()
        run.assert_not_called()
        popen.assert_not_called()

    def test_mp4_does_not_fall_back_to_path_when_bundled_ffmpeg_is_missing(
        self,
    ) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="pixelart-svc-missing-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        decoy = _write_fake_binary(tmp / "decoy-bin" / _ffmpeg_filename())
        decoy_path = str(decoy.parent) + os.pathsep + os.environ.get("PATH", "")
        saved_override = os.environ.pop(ENV_FFMPEG, None)

        def _restore_override() -> None:
            if saved_override is None:
                os.environ.pop(ENV_FFMPEG, None)
            else:
                os.environ[ENV_FFMPEG] = saved_override

        self.addCleanup(_restore_override)

        with (
            patch.dict(os.environ, {"PATH": decoy_path}),
            patch(
                "pixelart_converter.conversion.binary._vendor_search_roots",
                return_value=(tmp,),
            ),
            patch(
                "pixelart_converter.conversion.service.resolve_encoder",
            ) as resolve_encoder,
            patch("subprocess.Popen") as popen,
            patch("subprocess.run") as run,
        ):
            which_hit = shutil.which(_ffmpeg_filename())
            self.assertIsNotNone(which_hit)
            self.assertEqual(Path(which_hit).resolve(), decoy.resolve())
            with self.assertRaises(ConversionError) as ctx:
                self.service.convert(_mp4_job())

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertEqual(error.message, user_message_for(ErrorCode.ENCODER_UNAVAILABLE))
        _assert_no_system_ffmpeg_advice(error.message)
        resolve_encoder.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        side_effect=ConversionError.from_code(
            ErrorCode.ENCODER_UNAVAILABLE,
            message="The bundled ffmpeg binary is missing. This app cannot convert without it.",
            detail="no PIXELART_FFMPEG, _MEIPASS, or vendor/ffmpeg binary",
        ),
    )
    @patch("pixelart_converter.conversion.service.resolve_encoder")
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_mp4_missing_ffmpeg_uses_hw_message_not_system_advice(
        self, run, popen, resolve_encoder, _resolve_ffmpeg
    ) -> None:
        with self.assertRaises(ConversionError) as ctx:
            self.service.convert(_mp4_job())

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertEqual(error.message, user_message_for(ErrorCode.ENCODER_UNAVAILABLE))
        _assert_no_system_ffmpeg_advice(error.message)
        resolve_encoder.assert_not_called()
        run.assert_not_called()
        popen.assert_not_called()

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=EncoderResult(name="h264_videotoolbox"),
    )
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_mp4_duration_with_encoder_still_does_not_encode(
        self, run, popen, _resolve_encoder, _resolve_ffmpeg
    ) -> None:
        job = ConversionJob(
            input_path="in.gif",
            output=MP4Output(
                options=MP4Options(duration_seconds=2.0),
                output_path="out.mp4",
            ),
        )
        with self.assertRaises(NotImplementedError):
            self.service.convert(job)
        run.assert_not_called()
        popen.assert_not_called()


class ConversionServiceNonMp4Test(unittest.TestCase):
    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        side_effect=ConversionError.from_code(
            ErrorCode.ENCODER_UNAVAILABLE,
            message="The bundled ffmpeg binary is missing. This app cannot convert without it.",
            detail="no PIXELART_FFMPEG, _MEIPASS, or vendor/ffmpeg binary",
        ),
    )
    @patch("pixelart_converter.conversion.service.resolve_encoder")
    def test_non_mp4_missing_ffmpeg_fails_classified(
        self, resolve_encoder, _resolve_ffmpeg
    ) -> None:
        with self.assertRaises(ConversionError) as ctx:
            ConversionService().preflight(_jpeg_job())

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn("bundled ffmpeg", error.message.lower())
        self.assertIn("cannot convert", error.message.lower())
        _assert_no_system_ffmpeg_advice(error.message)
        resolve_encoder.assert_not_called()

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch("pixelart_converter.conversion.service.resolve_encoder")
    def test_non_mp4_skips_encoder_probe(
        self, resolve_encoder, _resolve_ffmpeg
    ) -> None:
        result = ConversionService().preflight(_jpeg_job())
        self.assertIsNone(result)
        resolve_encoder.assert_not_called()


class ConversionServiceSourceTest(unittest.TestCase):
    def test_service_never_looks_up_ffmpeg_on_path(self) -> None:
        from pixelart_converter.conversion import service as service_mod

        text = Path(service_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("shutil.which", text)
        self.assertNotIn("which(", text)


class ConversionServiceUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication(["pixelart-converter-test"])

    @patch(
        "pixelart_converter.conversion.service.resolve_ffmpeg",
        return_value=Path("/bundled/ffmpeg"),
    )
    @patch(
        "pixelart_converter.conversion.service.resolve_encoder",
        return_value=None,
    )
    def test_main_window_shows_preflight_reason(
        self, _resolve_encoder, _resolve_ffmpeg
    ) -> None:
        window = MainWindow()
        with self.assertRaises(ConversionError) as ctx:
            ConversionService().preflight(_mp4_job())
        error = ctx.exception
        window.show_error(error, show_dialog=False)

        self.assertIs(window.last_error, error)
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn(error.message, window._error_label.text())
        _assert_no_system_ffmpeg_advice(error.message)
        _assert_no_system_ffmpeg_advice(window._error_label.text())


if __name__ == "__main__":
    unittest.main()
