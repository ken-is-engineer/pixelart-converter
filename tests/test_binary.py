"""Unit tests for bundled ffmpeg path resolution.

Fake binaries live under tempfile dirs. A decoy ffmpeg on PATH must never win.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pixelart_converter.conversion import binary as binary_mod
from pixelart_converter.conversion.binary import (
    ENV_FFMPEG,
    ENV_FFPROBE,
    _ffmpeg_filename,
    _ffprobe_filename,
    _vendor_os_dir,
    resolve_ffmpeg,
    resolve_ffprobe,
)
from pixelart_converter.errors import ConversionError, ErrorCode


def _write_fake_binary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    path.chmod(0o755)
    return path


class ResolveFfmpegTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pixelart-ffmpeg-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

        self._saved_env: dict[str, str | None] = {}
        for key in (ENV_FFMPEG, ENV_FFPROBE):
            self._saved_env[key] = os.environ.pop(key, None)
        self.addCleanup(self._restore_env)

        roots = patch(
            "pixelart_converter.conversion.binary._vendor_search_roots",
            return_value=(self.tmp,),
        )
        roots.start()
        self.addCleanup(roots.stop)

    def _restore_env(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _vendor_ffmpeg(self) -> Path:
        os_dir = _vendor_os_dir()
        self.assertIsNotNone(os_dir)
        return _write_fake_binary(
            self.tmp / "vendor" / "ffmpeg" / os_dir / _ffmpeg_filename()
        )

    def _vendor_ffprobe(self) -> Path:
        os_dir = _vendor_os_dir()
        self.assertIsNotNone(os_dir)
        return _write_fake_binary(
            self.tmp / "vendor" / "ffmpeg" / os_dir / _ffprobe_filename()
        )

    def test_env_override_wins_over_vendor_and_meipass(self) -> None:
        vendor = self._vendor_ffmpeg()
        meipass_dir = self.tmp / "meipass"
        meipass_bin = _write_fake_binary(meipass_dir / _ffmpeg_filename())
        override = _write_fake_binary(self.tmp / "override" / _ffmpeg_filename())
        os.environ[ENV_FFMPEG] = str(override)

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(meipass_dir), create=True),
        ):
            resolved = resolve_ffmpeg()

        self.assertEqual(resolved, override.resolve())
        self.assertNotEqual(resolved, vendor.resolve())
        self.assertNotEqual(resolved, meipass_bin.resolve())

    def test_vendor_path_used_when_env_unset(self) -> None:
        vendor = self._vendor_ffmpeg()
        self.assertEqual(resolve_ffmpeg(), vendor.resolve())

    def test_path_decoy_is_ignored_when_vendor_exists(self) -> None:
        vendor = self._vendor_ffmpeg()
        decoy = _write_fake_binary(self.tmp / "decoy-bin" / _ffmpeg_filename())
        decoy_path = str(decoy.parent) + os.pathsep + os.environ.get("PATH", "")

        with patch.dict(os.environ, {"PATH": decoy_path}):
            which_hit = shutil.which(_ffmpeg_filename())
            self.assertIsNotNone(which_hit)
            self.assertEqual(Path(which_hit).resolve(), decoy.resolve())
            with patch(
                "shutil.which",
                side_effect=AssertionError("must not search PATH"),
            ):
                resolved = resolve_ffmpeg()

        self.assertEqual(resolved, vendor.resolve())
        self.assertNotEqual(resolved, decoy.resolve())

    def test_path_decoy_is_ignored_when_bundled_binary_is_missing(self) -> None:
        decoy = _write_fake_binary(self.tmp / "decoy-bin" / _ffmpeg_filename())
        decoy_path = str(decoy.parent) + os.pathsep + os.environ.get("PATH", "")

        with patch.dict(os.environ, {"PATH": decoy_path}):
            which_hit = shutil.which(_ffmpeg_filename())
            self.assertIsNotNone(which_hit)
            self.assertEqual(Path(which_hit).resolve(), decoy.resolve())
            with self.assertRaises(ConversionError) as ctx:
                resolve_ffmpeg()

        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn("bundled ffmpeg", error.message.lower())
        self.assertNotIn("install", error.message.lower())

    def test_missing_binary_raises_classified_error(self) -> None:
        with self.assertRaises(ConversionError) as ctx:
            resolve_ffmpeg()
        error = ctx.exception
        self.assertEqual(error.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertEqual(
            error.message,
            "The bundled ffmpeg binary is missing. This app cannot convert without it.",
        )
        self.assertNotIn("system", error.message.lower())
        self.assertNotIn("install", error.message.lower())

    def test_invalid_env_override_does_not_fall_back_to_vendor_or_path(self) -> None:
        vendor = self._vendor_ffmpeg()
        decoy = _write_fake_binary(self.tmp / "decoy-bin" / _ffmpeg_filename())
        missing = self.tmp / "does-not-exist" / _ffmpeg_filename()
        os.environ[ENV_FFMPEG] = str(missing)
        decoy_path = str(decoy.parent) + os.pathsep + os.environ.get("PATH", "")

        with patch.dict(os.environ, {"PATH": decoy_path}):
            with self.assertRaises(ConversionError) as ctx:
                resolve_ffmpeg()

        self.assertEqual(ctx.exception.code, ErrorCode.ENCODER_UNAVAILABLE)
        self.assertIn(ENV_FFMPEG, ctx.exception.detail or "")
        self.assertTrue(vendor.is_file())

    def test_env_override_pointing_at_a_directory_fails(self) -> None:
        directory = self.tmp / "not-a-binary"
        directory.mkdir()
        os.environ[ENV_FFMPEG] = str(directory)
        with self.assertRaises(ConversionError) as ctx:
            resolve_ffmpeg()
        self.assertEqual(ctx.exception.code, ErrorCode.ENCODER_UNAVAILABLE)

    def test_frozen_meipass_wins_over_vendor(self) -> None:
        vendor = self._vendor_ffmpeg()
        meipass_dir = self.tmp / "meipass"
        bundled = _write_fake_binary(meipass_dir / _ffmpeg_filename())

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(meipass_dir), create=True),
        ):
            resolved = resolve_ffmpeg()

        self.assertEqual(resolved, bundled.resolve())
        self.assertNotEqual(resolved, vendor.resolve())

    def test_frozen_meipass_vendor_layout(self) -> None:
        os_dir = _vendor_os_dir()
        self.assertIsNotNone(os_dir)
        meipass_dir = self.tmp / "meipass"
        bundled = _write_fake_binary(
            meipass_dir / "vendor" / "ffmpeg" / os_dir / _ffmpeg_filename()
        )

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(meipass_dir), create=True),
        ):
            self.assertEqual(resolve_ffmpeg(), bundled.resolve())

    def test_frozen_without_binary_falls_through_to_vendor(self) -> None:
        vendor = self._vendor_ffmpeg()
        meipass_dir = self.tmp / "empty-meipass"
        meipass_dir.mkdir()

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", str(meipass_dir), create=True),
        ):
            self.assertEqual(resolve_ffmpeg(), vendor.resolve())

    def test_ffprobe_is_sibling_of_ffmpeg(self) -> None:
        ffmpeg = self._vendor_ffmpeg()
        ffprobe = self._vendor_ffprobe()
        self.assertEqual(resolve_ffmpeg(), ffmpeg.resolve())
        self.assertEqual(resolve_ffprobe(), ffprobe.resolve())

    def test_ffprobe_optional_when_missing(self) -> None:
        self._vendor_ffmpeg()
        self.assertIsNone(resolve_ffprobe())

    def test_ffprobe_env_override(self) -> None:
        self._vendor_ffmpeg()
        override = _write_fake_binary(self.tmp / "override" / _ffprobe_filename())
        os.environ[ENV_FFPROBE] = str(override)
        self.assertEqual(resolve_ffprobe(), override.resolve())

    def test_source_never_looks_up_ffmpeg_on_path(self) -> None:
        source = Path(binary_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("shutil.which", source)
        self.assertNotIn("which(", source)


if __name__ == "__main__":
    unittest.main()
