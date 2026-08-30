"""Headless tests for format-specific option enable/disable (T4-2)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from pixelart_converter.models import (
    AllFrames,
    FrameRange,
    GIFOutput,
    JPEGOutput,
    MP4Output,
    MultipleFrames,
    OutputFormat,
    PNGOutput,
    ScaleAlgorithm,
    SingleFrame,
)
from pixelart_converter.ui.main_window import MainWindow
from pixelart_converter.ui.options import parse_frame_list


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ParseFrameListTest(unittest.TestCase):
    def test_indices_and_inclusive_ranges(self) -> None:
        selection = parse_frame_list("0, 2, 4-6")
        self.assertEqual(selection.items, (0, 2, FrameRange(4, 6)))

    def test_empty_or_invalid_tokens_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_frame_list("")
        with self.assertRaises(ValueError):
            parse_frame_list("1,abc")
        with self.assertRaises(ValueError):
            parse_frame_list("3-1")


class MainWindowOptionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _ensure_app()

    def setUp(self) -> None:
        self.window = MainWindow()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def tearDown(self) -> None:
        self.window.close()

    def _write_gif(self, name: str = "input.gif") -> Path:
        path = Path(self.temp_dir.name) / name
        frame = Image.new("RGB", (4, 4), "red")
        frame.save(path, format="GIF")
        return path

    def _assert_common_operable(self) -> None:
        self.assertTrue(self.window.output_width_spin.isEnabled())
        self.assertTrue(self.window.output_height_spin.isEnabled())
        self.assertTrue(self.window.scale_combo.isEnabled())
        self.assertTrue(self.window.strip_metadata_check.isEnabled())
        self.assertTrue(self.window.output_path_edit.isEnabled())
        self.assertFalse(self.window.output_width_spin.isHidden())
        self.assertFalse(self.window.convert_button.isEnabled())

    def test_default_mp4_hides_frame_controls_and_enables_loop_field(self) -> None:
        self.assertEqual(self.window.current_output_format(), OutputFormat.MP4)
        self.assertFalse(self.window.mp4_group.isHidden())
        self.assertTrue(self.window.mp4_group.isEnabled())
        self.assertTrue(self.window.mp4_loop_radio.isChecked())
        self.assertTrue(self.window.mp4_loop_spin.isEnabled())
        self.assertFalse(self.window.mp4_duration_spin.isEnabled())
        self.assertTrue(self.window.mp4_duration_radio.isEnabled())
        self.assertTrue(self.window.frame_group.isHidden())
        self.assertFalse(self.window.frame_group.isEnabled())
        self._assert_common_operable()

    def test_mp4_duration_mode_disables_loop_count_field(self) -> None:
        self.window.set_output_format(OutputFormat.MP4)
        self.window.mp4_duration_radio.setChecked(True)

        self.assertTrue(self.window.mp4_duration_radio.isEnabled())
        self.assertTrue(self.window.mp4_duration_spin.isEnabled())
        self.assertTrue(self.window.mp4_loop_radio.isEnabled())
        self.assertFalse(self.window.mp4_loop_spin.isEnabled())

        self.window.mp4_loop_radio.setChecked(True)
        self.assertTrue(self.window.mp4_loop_spin.isEnabled())
        self.assertFalse(self.window.mp4_duration_spin.isEnabled())

    def test_jpeg_and_png_show_frame_controls_and_hide_mp4(self) -> None:
        for fmt in (OutputFormat.JPEG, OutputFormat.PNG):
            with self.subTest(fmt=fmt):
                self.window.set_output_format(fmt)
                self.assertTrue(self.window.mp4_group.isHidden())
                self.assertFalse(self.window.mp4_group.isEnabled())
                self.assertFalse(self.window.mp4_loop_spin.isEnabled())
                self.assertFalse(self.window.mp4_duration_spin.isEnabled())
                self.assertFalse(self.window.frame_group.isHidden())
                self.assertTrue(self.window.frame_group.isEnabled())
                self._assert_common_operable()

    def test_jpeg_unused_frame_fields_are_disabled(self) -> None:
        self.window.set_output_format(OutputFormat.JPEG)
        self.assertTrue(self.window.frame_single_radio.isChecked())
        self.assertTrue(self.window.frame_index_spin.isEnabled())
        self.assertFalse(self.window.frame_list_edit.isEnabled())

        self.window.frame_list_radio.setChecked(True)
        self.assertTrue(self.window.frame_list_edit.isEnabled())
        self.assertFalse(self.window.frame_index_spin.isEnabled())
        self.assertTrue(self.window.frame_single_radio.isEnabled())
        self.assertTrue(self.window.frame_all_radio.isEnabled())

        self.window.frame_all_radio.setChecked(True)
        self.assertFalse(self.window.frame_index_spin.isEnabled())
        self.assertFalse(self.window.frame_list_edit.isEnabled())

    def test_gif_hides_mp4_and_image_frame_controls(self) -> None:
        self.window.set_output_format(OutputFormat.GIF)
        self.assertTrue(self.window.mp4_group.isHidden())
        self.assertTrue(self.window.frame_group.isHidden())
        self.assertFalse(self.window.mp4_group.isEnabled())
        self.assertFalse(self.window.frame_group.isEnabled())
        self.assertFalse(self.window.mp4_loop_spin.isEnabled())
        self.assertFalse(self.window.frame_index_spin.isEnabled())
        self.assertFalse(self.window.frame_list_edit.isEnabled())
        self._assert_common_operable()
        self.assertTrue(self.window.format_gif_radio.isEnabled())
        self.assertTrue(self.window.format_mp4_radio.isEnabled())

    def test_switching_back_to_mp4_restores_exclusive_fields(self) -> None:
        self.window.set_output_format(OutputFormat.GIF)
        self.window.set_output_format(OutputFormat.MP4)
        self.assertFalse(self.window.mp4_group.isHidden())
        self.assertTrue(self.window.mp4_group.isEnabled())
        self.assertTrue(self.window.frame_group.isHidden())
        self.assertTrue(self.window.mp4_loop_spin.isEnabled())
        self.assertFalse(self.window.mp4_duration_spin.isEnabled())

    def test_build_job_collects_mp4_loop_without_running_ffmpeg(self) -> None:
        path = self._write_gif()
        self.window.set_input_path(path)
        self.window.set_output_format(OutputFormat.MP4)
        self.window.mp4_loop_radio.setChecked(True)
        self.window.mp4_loop_spin.setValue(3)
        self.window.output_width_spin.setValue(32)
        self.window.output_height_spin.setValue(16)
        bicubic = self.window.scale_combo.findData(ScaleAlgorithm.BICUBIC.value)
        self.window.scale_combo.setCurrentIndex(bicubic)
        self.window.strip_metadata_check.setChecked(True)
        self.window.output_path_edit.setText(str(Path(self.temp_dir.name) / "out.mp4"))

        job = self.window.build_job()
        self.assertIsInstance(job.output, MP4Output)
        self.assertEqual(job.output.options.loop_count, 3)
        self.assertIsNone(job.output.options.duration_seconds)
        self.assertEqual(job.common.width, 32)
        self.assertEqual(job.common.height, 16)
        self.assertIs(job.common.scale_algorithm, ScaleAlgorithm.BICUBIC)
        self.assertTrue(job.common.strip_metadata)
        self.assertEqual(job.output.output_path, Path(self.temp_dir.name) / "out.mp4")

    def test_build_job_collects_mp4_duration(self) -> None:
        path = self._write_gif()
        self.window.set_input_path(path)
        self.window.mp4_duration_radio.setChecked(True)
        self.window.mp4_duration_spin.setValue(2.5)
        job = self.window.build_job()
        self.assertEqual(job.output.options.duration_seconds, 2.5)
        self.assertIsNone(job.output.options.loop_count)

    def test_build_job_collects_jpeg_png_and_gif_selections(self) -> None:
        path = self._write_gif()
        self.window.set_input_path(path)

        self.window.set_output_format(OutputFormat.JPEG)
        self.window.frame_single_radio.setChecked(True)
        self.window.frame_index_spin.setValue(4)
        jpeg_job = self.window.build_job()
        self.assertIsInstance(jpeg_job.output, JPEGOutput)
        self.assertEqual(jpeg_job.output.frames, SingleFrame(4))

        self.window.set_output_format(OutputFormat.PNG)
        self.window.frame_list_radio.setChecked(True)
        self.window.frame_list_edit.setText("0,2,4-6")
        png_list = self.window.build_job()
        self.assertIsInstance(png_list.output, PNGOutput)
        self.assertEqual(
            png_list.output.frames,
            MultipleFrames((0, 2, FrameRange(4, 6))),
        )

        self.window.frame_all_radio.setChecked(True)
        png_all = self.window.build_job()
        self.assertIsInstance(png_all.output.frames, AllFrames)

        self.window.set_output_format(OutputFormat.GIF)
        gif_job = self.window.build_job()
        self.assertIsInstance(gif_job.output, GIFOutput)

    def test_build_job_requires_input_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "input path"):
            self.window.build_job()


if __name__ == "__main__":
    unittest.main()
