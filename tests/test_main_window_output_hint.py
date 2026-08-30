"""Headless tests for multi-frame output sequence hint (T4-4)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pixelart_converter.models import OutputFormat
from pixelart_converter.ui.main_window import MainWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MainWindowOutputSequenceHintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _ensure_app()

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.close()

    @property
    def hint(self):
        return self.window._output_sequence_hint

    def test_hint_hidden_for_mp4_and_gif(self) -> None:
        for fmt in (OutputFormat.MP4, OutputFormat.GIF):
            with self.subTest(fmt=fmt):
                self.window.set_output_format(fmt)
                self.assertTrue(self.hint.isHidden())

    def test_hint_hidden_for_jpeg_png_single_frame(self) -> None:
        for fmt in (OutputFormat.JPEG, OutputFormat.PNG):
            with self.subTest(fmt=fmt):
                self.window.set_output_format(fmt)
                self.window.frame_single_radio.setChecked(True)
                self.assertTrue(self.hint.isHidden())

    def test_hint_visible_for_jpeg_png_list_or_all_frames(self) -> None:
        cases = (
            (OutputFormat.JPEG, "frame_list_radio", "jpg"),
            (OutputFormat.JPEG, "frame_all_radio", "jpg"),
            (OutputFormat.PNG, "frame_list_radio", "png"),
            (OutputFormat.PNG, "frame_all_radio", "png"),
        )
        for fmt, frame_radio_name, ext in cases:
            with self.subTest(fmt=fmt, frame=frame_radio_name):
                self.window.set_output_format(fmt)
                getattr(self.window, frame_radio_name).setChecked(True)
                self.assertFalse(self.hint.isHidden())
                self.assertIn(f"name_000.{ext}", self.hint.text())
                self.assertIn("numbered sequence", self.hint.text())

    def test_hint_hides_when_switching_from_multi_to_single_frame(self) -> None:
        self.window.set_output_format(OutputFormat.PNG)
        self.window.frame_all_radio.setChecked(True)
        self.assertFalse(self.hint.isHidden())

        self.window.frame_single_radio.setChecked(True)
        self.assertTrue(self.hint.isHidden())

    def test_hint_hides_when_switching_from_jpeg_multi_to_mp4(self) -> None:
        self.window.set_output_format(OutputFormat.JPEG)
        self.window.frame_list_radio.setChecked(True)
        self.assertFalse(self.hint.isHidden())

        self.window.set_output_format(OutputFormat.MP4)
        self.assertTrue(self.hint.isHidden())


if __name__ == "__main__":
    unittest.main()
