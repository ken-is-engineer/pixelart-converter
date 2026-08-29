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


if __name__ == "__main__":
    unittest.main()
