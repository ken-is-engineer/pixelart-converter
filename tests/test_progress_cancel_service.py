"""Progress, cancellation, and temporary output tests for ConversionService."""

from __future__ import annotations

import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion.service import ConversionService
from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob, GIFOutput


class ConversionServiceProgressCancelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.output_dir = self.root / "outputs"
        self.output_dir.mkdir()

    def _fake_ffmpeg(self, *, pause: bool) -> Path:
        script = self.root / ("slow-ffmpeg" if pause else "ffmpeg")
        sleep_line = "time.sleep(30)" if pause else ""
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib\n"
            "import sys\n"
            "import time\n"
            "output = pathlib.Path(sys.argv[-1])\n"
            "output.write_bytes(b'encoded')\n"
            "print('out_time_us=1250000', flush=True)\n"
            f"{sleep_line}\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def test_progress_callback_and_successful_publish(self) -> None:
        output_path = self.output_dir / "converted.gif"
        job = ConversionJob("input.gif", GIFOutput(output_path))
        progress: list[float] = []

        with patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=self._fake_ffmpeg(pause=False),
        ):
            ConversionService().convert(job, progress.append)

        self.assertEqual(progress, [1.25])
        self.assertEqual(output_path.read_bytes(), b"encoded")
        self.assertEqual(list(self.output_dir.iterdir()), [output_path])

    def test_cancel_raises_cancelled_and_removes_temporary_output(self) -> None:
        output_path = self.output_dir / "cancelled.gif"
        job = ConversionJob("input.gif", GIFOutput(output_path))
        service = ConversionService()
        progress_seen = threading.Event()
        errors: list[BaseException] = []

        def convert() -> None:
            try:
                service.convert(job, lambda _seconds: progress_seen.set())
            except BaseException as exc:
                errors.append(exc)

        with patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=self._fake_ffmpeg(pause=True),
        ):
            thread = threading.Thread(target=convert)
            thread.start()
            self.assertTrue(progress_seen.wait(timeout=5))
            service.cancel()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConversionError)
        self.assertEqual(errors[0].code, ErrorCode.CANCELLED)
        self.assertFalse(output_path.exists())
        self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_cancel_during_preflight_does_not_start_ffmpeg(self) -> None:
        from pixelart_converter.models import JPEGOutput, SingleFrame

        output_path = self.output_dir / "never.jpg"
        job = ConversionJob(
            "input.gif",
            JPEGOutput(frames=SingleFrame(0), output_path=output_path),
        )
        service = ConversionService()

        def cancel_then_return(_job) -> None:
            service.cancel()

        with (
            patch.object(
                service, "_validate_still_frames", side_effect=cancel_then_return
            ),
            patch(
                "pixelart_converter.conversion.service.resolve_ffmpeg",
                return_value=Path("/bundled/ffmpeg"),
            ),
            patch(
                "pixelart_converter.conversion.command.resolve_ffmpeg",
                return_value=Path("/bundled/ffmpeg"),
            ),
            patch("pixelart_converter.conversion.service.subprocess.Popen") as popen,
        ):
            with self.assertRaises(ConversionError) as ctx:
                service.convert(job)

        self.assertEqual(ctx.exception.code, ErrorCode.CANCELLED)
        popen.assert_not_called()
        self.assertFalse(output_path.exists())

    def test_publish_uses_intended_name_when_temp_dir_has_extra_files(
        self,
    ) -> None:
        output_path = self.output_dir / "converted.gif"
        job = ConversionJob("input.gif", GIFOutput(output_path))
        extra_dir = Path(tempfile.mkdtemp(dir=self.output_dir))
        (extra_dir / "leftover.bin").write_bytes(b"nope")

        with patch(
            "pixelart_converter.conversion.command.resolve_ffmpeg",
            return_value=self._fake_ffmpeg(pause=False),
        ), patch(
            "pixelart_converter.conversion.service.tempfile.mkdtemp",
            return_value=str(extra_dir),
        ):
            ConversionService().convert(job)

        self.assertEqual(output_path.read_bytes(), b"encoded")
        self.assertFalse((self.output_dir / "leftover.bin").exists())
        self.assertEqual(list(self.output_dir.iterdir()), [output_path])


if __name__ == "__main__":
    unittest.main()
