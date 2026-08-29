"""Headless tests for worker-thread convert, progress, cancel, and errors (T4-3)."""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication, QMessageBox

from pixelart_converter.errors import ConversionError, ErrorCode
from pixelart_converter.models import ConversionJob, ScaleAlgorithm
from pixelart_converter.ui.main_window import MainWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeConversionService:
    """Test double: convert() sleeps/holds on the caller thread, never FFmpeg."""

    def __init__(
        self,
        *,
        hold: bool = True,
        sleep: float = 0.0,
        progress: float | None = None,
        error: ConversionError | None = None,
    ) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancel_called = threading.Event()
        self.convert_thread_id: int | None = None
        self.jobs: list[ConversionJob] = []
        self._hold = hold
        self._sleep = sleep
        self._progress = progress
        self._error = error
        self._cancelled = threading.Event()

    def convert(
        self,
        job: ConversionJob,
        progress_callback: object | None = None,
    ) -> None:
        self.convert_thread_id = threading.get_ident()
        self.jobs.append(job)
        if self._progress is not None and callable(progress_callback):
            progress_callback(self._progress)
        self.started.set()
        if self._sleep:
            time.sleep(self._sleep)
        if self._hold:
            self.release.wait(timeout=5)
        if self._cancelled.is_set():
            raise ConversionError.from_code(ErrorCode.CANCELLED)
        if self._error is not None:
            raise self._error

    def cancel(self) -> None:
        self.cancel_called.set()
        self._cancelled.set()
        self.release.set()


class MainWindowConvertTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _ensure_app()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = FakeConversionService()
        self.window = MainWindow(service=self.service)
        path = Path(self.temp_dir.name) / "input.gif"
        Image.new("RGB", (4, 4), "red").save(path, format="GIF")
        self.window.set_input_path(path)

    def tearDown(self) -> None:
        if self.window.is_converting:
            self.window.cancel_button.click()
        self._pump_until(lambda: self.window.conversion_worker is None)
        self.window.close()

    def _pump_until(self, predicate: object, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if callable(predicate) and predicate():
                return
            time.sleep(0.01)
        self.fail("condition not met before timeout")

    def test_convert_runs_off_gui_thread_and_finishes(self) -> None:
        self.service._sleep = 0.25
        gui_thread = threading.get_ident()
        self.assertTrue(self.window.convert_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())

        started = time.monotonic()
        self.window.convert_button.click()
        self.assertLess(time.monotonic() - started, 0.15)
        self.assertTrue(self.window.is_converting)
        self.assertIsNotNone(self.window.conversion_worker)
        self.assertFalse(self.window.convert_button.isEnabled())
        self.assertTrue(self.window.cancel_button.isEnabled())
        self.assertFalse(self.window.output_width_spin.isEnabled())
        self.assertFalse(self.window._browse_button.isEnabled())
        self.assertFalse(self.window.format_mp4_radio.isEnabled())
        self.assertFalse(self.window.output_path_edit.isEnabled())

        self.assertTrue(self.service.started.wait(timeout=2))
        self.assertNotEqual(self.service.convert_thread_id, gui_thread)
        self.assertEqual(self.service.jobs[0].common.scale_algorithm, ScaleAlgorithm.NEIGHBOR)

        pumped = time.monotonic()
        while time.monotonic() - pumped < 0.1:
            self.app.processEvents()
        self.assertTrue(self.window.is_converting)

        self.service.release.set()
        self._pump_until(lambda: not self.window.is_converting)
        self._pump_until(lambda: self.window.conversion_worker is None)
        self.assertEqual(self.window.progress_label.text(), "Done")
        self.assertEqual(self.window.progress_bar.value(), 1)
        self.assertTrue(self.window.convert_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())
        self.assertTrue(self.window.output_width_spin.isEnabled())

    def test_progress_updates_widgets_on_gui_thread(self) -> None:
        self.service._progress = 1.25
        self.window.convert_button.click()
        self.assertTrue(self.service.started.wait(timeout=2))
        self._pump_until(lambda: "1.25" in self.window.progress_label.text())
        self.assertTrue(self.window.is_converting)
        self.assertEqual(self.window.progress_bar.minimum(), 0)
        self.assertEqual(self.window.progress_bar.maximum(), 0)
        self.service.release.set()
        self._pump_until(lambda: not self.window.is_converting)

    def test_cancel_calls_service_and_shows_cancelled_error(self) -> None:
        self.window.convert_button.click()
        self.assertTrue(self.service.started.wait(timeout=2))
        self.window.cancel_button.click()
        self.assertTrue(self.service.cancel_called.wait(timeout=2))
        self._pump_until(lambda: not self.window.is_converting)
        self.assertIsNotNone(self.window.last_error)
        self.assertEqual(self.window.last_error.code, ErrorCode.CANCELLED)
        self.assertIn("cancelled", self.window._error_label.text().lower())
        self.assertTrue(self.window.convert_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())

    @patch.object(QMessageBox, "critical")
    def test_conversion_error_calls_show_error(self, critical: object) -> None:
        error = ConversionError.from_code(
            ErrorCode.ENCODER_UNAVAILABLE,
            detail="no hardware encoder",
        )
        self.service._error = error
        self.service._hold = False
        self.window.convert_button.click()
        self._pump_until(lambda: self.window.last_error is not None)
        self.assertIs(self.window.last_error, error)
        self.assertIn(error.message, self.window._error_label.text())
        critical.assert_called_once()  # type: ignore[attr-defined]
        self.assertFalse(self.window.is_converting)
        self.assertTrue(self.window.convert_button.isEnabled())

    def test_common_options_are_passed_to_convert(self) -> None:
        self.window.output_width_spin.setValue(32)
        self.window.output_height_spin.setValue(16)
        self.window.strip_metadata_check.setChecked(True)
        bicubic = self.window.scale_combo.findData(ScaleAlgorithm.BICUBIC.value)
        self.window.scale_combo.setCurrentIndex(bicubic)
        self.service._hold = False
        self.window.convert_button.click()
        self._pump_until(lambda: bool(self.service.jobs))
        self._pump_until(lambda: not self.window.is_converting)
        job = self.service.jobs[0]
        self.assertEqual(job.common.width, 32)
        self.assertEqual(job.common.height, 16)
        self.assertIs(job.common.scale_algorithm, ScaleAlgorithm.BICUBIC)
        self.assertTrue(job.common.strip_metadata)


if __name__ == "__main__":
    unittest.main()
