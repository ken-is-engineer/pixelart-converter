"""T6-1: bundled third-party license texts and resolver."""

from __future__ import annotations

import unittest
from pathlib import Path

from pixelart_converter.licenses import notice_path, resolve_third_party_licenses_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSES_DIR = REPO_ROOT / "third_party_licenses"

REQUIRED_FILES = (
    "NOTICE.txt",
    "LGPL-3.0.txt",
    "GPL-3.0.txt",
    "Pillow-LICENSE.txt",
    "PyInstaller-COPYING.txt",
    "FFmpeg-README.txt",
)


class ThirdPartyLicensesTest(unittest.TestCase):
    def test_license_directory_contains_required_files(self) -> None:
        self.assertTrue(LICENSES_DIR.is_dir(), f"missing {LICENSES_DIR}")
        for name in REQUIRED_FILES:
            path = LICENSES_DIR / name
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_notice_lists_components(self) -> None:
        notice = (LICENSES_DIR / "NOTICE.txt").read_text(encoding="utf-8")
        for fragment in (
            "PySide6",
            "Qt",
            "LGPL",
            "FFmpeg",
            "Pillow",
            "PyInstaller",
        ):
            self.assertIn(fragment, notice)

    def test_lgpl_and_gpl_are_gnu_licenses(self) -> None:
        lgpl = (LICENSES_DIR / "LGPL-3.0.txt").read_text(encoding="utf-8")
        gpl = (LICENSES_DIR / "GPL-3.0.txt").read_text(encoding="utf-8")
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", lgpl)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", gpl)

    def test_resolve_points_at_repo_directory_in_dev(self) -> None:
        resolved = resolve_third_party_licenses_dir()
        self.assertEqual(resolved, LICENSES_DIR)
        self.assertEqual(notice_path(), LICENSES_DIR / "NOTICE.txt")


class PackagingSpecLicensesTest(unittest.TestCase):
    def test_macos_spec_ships_third_party_licenses(self) -> None:
        text = (REPO_ROOT / "packaging" / "macos.spec").read_text(encoding="utf-8")
        self.assertIn("third_party_licenses", text)
        self.assertIn("LICENSES_DIR", text)

    def test_windows_spec_ships_third_party_licenses(self) -> None:
        text = (REPO_ROOT / "packaging" / "windows.spec").read_text(encoding="utf-8")
        self.assertIn("third_party_licenses", text)
        self.assertIn("LICENSES_DIR", text)


if __name__ == "__main__":
    unittest.main()
