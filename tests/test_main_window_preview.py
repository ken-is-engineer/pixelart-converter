"""Headless tests for GIF picker, nearest-neighbor preview, and metadata."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication

from pixelart_converter.ui.main_window import MainWindow
from pixelart_converter.ui.preview import PREVIEW_TRANSFORMATION


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class MainWindowPreviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _ensure_app()

    def setUp(self) -> None:
        self.window = MainWindow()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def tearDown(self) -> None:
        self.window.close()

    def _write_gif(
        self,
        name: str,
        size: tuple[int, int],
        colors: tuple[str, ...],
    ) -> Path:
        path = Path(self.temp_dir.name) / name
        frames = [Image.new("RGB", size, color) for color in colors]
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=50,
            loop=0,
            format="GIF",
        )
        return path

    def test_empty_window_constructs_without_input(self) -> None:
        self.assertIsNone(self.window.input_path)
        self.assertEqual(self.window.output_path_edit.text(), "")
        self.assertFalse(self.window.preview_widget.has_preview())
        self.assertEqual(
            self.window.preview_transformation_mode,
            Qt.TransformationMode.FastTransformation,
        )
        self.assertEqual(
            self.window.preview_transformation_mode,
            PREVIEW_TRANSFORMATION,
        )
        self.assertNotEqual(
            self.window.preview_transformation_mode,
            Qt.TransformationMode.SmoothTransformation,
        )

    def test_loads_gif_metadata_and_preview(self) -> None:
        path = self._write_gif("tiny.gif", (8, 4), ("red", "blue", "green"))
        self.window.set_input_path(path)

        self.assertEqual(self.window.input_path, str(path))
        self.assertEqual(self.window.path_label.text(), str(path))
        self.assertEqual(self.window.width_label.text(), "8")
        self.assertEqual(self.window.height_label.text(), "4")
        self.assertEqual(self.window.frame_count_label.text(), "3")
        self.assertTrue(self.window.preview_widget.has_preview())
        self.assertEqual(
            self.window.preview_widget.source_pixmap_size(),
            QSize(8, 4),
        )
        self.assertTrue(self.window.preview_status_label.isHidden())
        self.assertEqual(
            self.window.preview_transformation_mode,
            Qt.TransformationMode.FastTransformation,
        )
        self.assertEqual(
            self.window.output_path_edit.text(),
            str(path.with_name("tiny-video.mp4")),
        )

    def test_selecting_another_gif_replaces_suggested_output_path(self) -> None:
        first = self._write_gif("first.gif", (2, 2), ("red",))
        second = self._write_gif("second.gif", (2, 2), ("blue",))
        self.window.set_input_path(first)
        self.window.set_input_path(second)
        self.assertEqual(
            self.window.output_path_edit.text(),
            str(second.with_name("second-video.mp4")),
        )

    def test_upscaled_preview_keeps_hard_pixel_edges(self) -> None:
        path = Path(self.temp_dir.name) / "checker.gif"
        image = Image.new("RGB", (2, 2))
        image.putpixel((0, 0), (255, 0, 0))
        image.putpixel((1, 0), (0, 0, 255))
        image.putpixel((0, 1), (0, 0, 255))
        image.putpixel((1, 1), (255, 0, 0))
        image.save(path, format="GIF")

        self.window.set_input_path(path)
        scaled = self.window.preview_widget.scaled_pixmap(QSize(20, 20))
        self.assertFalse(scaled.isNull())
        sampled = scaled.toImage()
        left = sampled.pixelColor(9, 0)
        right = sampled.pixelColor(10, 0)
        self.assertEqual((left.red(), left.green(), left.blue()), (255, 0, 0))
        self.assertEqual((right.red(), right.green(), right.blue()), (0, 0, 255))

    def test_preview_failure_keeps_path_and_does_not_crash(self) -> None:
        bad = Path(self.temp_dir.name) / "not-a-gif.gif"
        bad.write_text("this is not a gif", encoding="utf-8")
        self.window.set_input_path(bad)

        self.assertEqual(self.window.input_path, str(bad))
        self.assertEqual(self.window.path_label.text(), str(bad))
        self.assertFalse(self.window.preview_widget.has_preview())
        self.assertFalse(self.window.preview_status_label.isHidden())
        self.assertIn("still convert", self.window.preview_status_label.text())
        self.assertEqual(self.window.width_label.text(), "—")
        self.assertEqual(self.window.height_label.text(), "—")
        self.assertEqual(self.window.frame_count_label.text(), "—")
        self.assertIsNone(self.window.last_error)

    def test_missing_file_does_not_crash(self) -> None:
        missing = str(Path(self.temp_dir.name) / "missing.gif")
        self.window.set_input_path(missing)
        self.assertEqual(self.window.input_path, missing)
        self.assertFalse(self.window.preview_widget.has_preview())
        self.assertFalse(self.window.preview_status_label.isHidden())

    def test_valid_gif_after_failure_recovers(self) -> None:
        bad = Path(self.temp_dir.name) / "broken.gif"
        bad.write_bytes(b"not a gif")
        self.window.set_input_path(bad)
        self.assertFalse(self.window.preview_widget.has_preview())

        path = self._write_gif("ok.gif", (3, 3), ("red",))
        self.window.set_input_path(path)
        self.assertTrue(self.window.preview_widget.has_preview())
        self.assertEqual(self.window.width_label.text(), "3")
        self.assertEqual(self.window.height_label.text(), "3")
        self.assertEqual(self.window.frame_count_label.text(), "1")
        self.assertTrue(self.window.preview_status_label.isHidden())


if __name__ == "__main__":
    unittest.main()
