"""T5-1 packaging infrastructure: spec is onedir + ffmpeg; script refuses low disk."""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = REPO_ROOT / "packaging" / "macos.spec"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_macos_app.sh"


class MacosSpecTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), f"missing {SPEC}")
        self.text = SPEC.read_text(encoding="utf-8")

    def test_mentions_ffmpeg_in_datas(self) -> None:
        self.assertIn("ffmpeg", self.text)
        self.assertIn("datas", self.text)
        self.assertIn("vendor/ffmpeg/macos", self.text)

    def test_is_onedir_collect_bundle(self) -> None:
        self.assertIn("COLLECT", self.text)
        self.assertIn("BUNDLE", self.text)
        self.assertIn("onedir", self.text)
        self.assertIn("exclude_binaries=True", self.text)

    def test_entry_and_bundle_name(self) -> None:
        self.assertIn("__main__.py", self.text)
        self.assertIn("pixelart-converter", self.text)
        self.assertIn("PySide6-Essentials", self.text)


class BuildMacosAppScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is not available")
        self.assertTrue(BUILD_SCRIPT.is_file(), f"missing {BUILD_SCRIPT}")

    def _run(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(BUILD_SCRIPT)],
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
        self.assertIn("error:", combined)
        self.assertRegex(combined.lower(), r"free|disk|mb")
        self.assertIn("99999999", combined)
        self.assertNotIn("building unsigned", combined.lower())

    def test_refuses_missing_ffmpeg(self) -> None:
        missing = REPO_ROOT / "vendor" / "ffmpeg" / "macos" / "no-such-ffmpeg"
        result = self._run(
            {
                "PIXELART_FFMPEG_BUNDLE": str(missing),
                "PIXELART_APP_MIN_FREE_MB": "0",
            }
        )
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        combined = result.stderr + result.stdout
        self.assertIn("ffmpeg", combined.lower())
        self.assertIn("build_ffmpeg_lgpl.sh", combined)
        self.assertNotIn("building unsigned", combined.lower())


if __name__ == "__main__":
    unittest.main()
