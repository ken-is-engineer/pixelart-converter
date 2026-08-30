"""T5-2 packaging infrastructure: spec is onedir + ffmpeg; script refuses low disk."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "packaging" / "windows.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_windows.ps1"


class WindowsSpecTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), f"missing {SPEC}")
        self.text = SPEC.read_text(encoding="utf-8")

    def test_mentions_ffmpeg_in_datas(self) -> None:
        self.assertIn("ffmpeg", self.text)
        self.assertIn("datas", self.text)
        self.assertIn("vendor/ffmpeg/windows", self.text)
        self.assertIn("ffmpeg.exe", self.text)
        self.assertIn("iterdir", self.text)

    def test_copies_sibling_dlls_next_to_ffmpeg(self) -> None:
        self.assertIn("iterdir", self.text)
        self.assertIn("libwinpthread", self.text)

    def test_is_onedir_collect(self) -> None:
        self.assertIn("COLLECT", self.text)
        self.assertIn("onedir", self.text)
        self.assertIn("exclude_binaries=True", self.text)
        self.assertNotIn("BUNDLE", self.text)

    def test_entry_and_console(self) -> None:
        self.assertIn("__main__.py", self.text)
        self.assertIn("pixelart-converter", self.text)
        self.assertIn("console=False", self.text)
        self.assertIn("PySide6-Essentials", self.text)


class BuildWindowsScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.shell = shutil.which("pwsh") or shutil.which("powershell")
        if self.shell is None:
            self.skipTest("PowerShell is not available")
        self.assertTrue(BUILD_SCRIPT.is_file(), f"missing {BUILD_SCRIPT}")

    def _run(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [self.shell, "-NoProfile", "-File", str(BUILD_SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
            env=env,
        )

    def test_refuses_low_disk(self) -> None:
        result = self._run({"PIXELART_APP_MIN_FREE_MB": "99999999"})
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        combined = result.stderr + result.stdout
        self.assertRegex(combined.lower(), r"free|disk|mb")
        self.assertIn("99999999", combined)
        self.assertNotIn("building unsigned", combined.lower())

    def test_refuses_missing_ffmpeg(self) -> None:
        missing = REPO_ROOT / "vendor" / "ffmpeg" / "windows" / "no-such-ffmpeg.exe"
        result = self._run(
            {
                "PIXELART_FFMPEG_BUNDLE": str(missing),
                "PIXELART_APP_MIN_FREE_MB": "0",
            }
        )
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        combined = result.stderr + result.stdout
        self.assertIn("ffmpeg", combined.lower())
        self.assertIn("build_ffmpeg_lgpl", combined)
        self.assertNotIn("building unsigned", combined.lower())


if __name__ == "__main__":
    unittest.main()
