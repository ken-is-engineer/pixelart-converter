"""Check a bundled ffmpeg when one is present; skip when it has not been built.

The binaries are build artifacts and are not committed (vendor/ffmpeg/README.md),
so on a fresh clone every test here skips.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "ffmpeg"
CANDIDATES = (
    VENDOR_DIR / "macos" / "ffmpeg",
    VENDOR_DIR / "windows" / "ffmpeg.exe",
)


def bundled_ffmpeg() -> Path | None:
    for candidate in CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


class BundledFfmpegLicenseTest(unittest.TestCase):
    def setUp(self) -> None:
        binary = bundled_ffmpeg()
        if binary is None:
            self.skipTest("no bundled ffmpeg; run scripts/build_ffmpeg_lgpl.sh first")
        self.binary = binary

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            [str(self.binary), "-hide_banner", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result.stdout + result.stderr

    def test_version_reports_no_x264_and_no_gpl(self) -> None:
        output = self._run("-version").lower()
        self.assertNotIn("libx264", output)
        self.assertNotIn("--enable-gpl", output)

    def test_no_x264_encoder_is_available(self) -> None:
        self.assertNotIn("x264", self._run("-encoders").lower())


if __name__ == "__main__":
    unittest.main()
