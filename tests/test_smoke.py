"""Headless smoke: the window can be created and the process exits 0."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class SmokeTest(unittest.TestCase):
    def _run_module(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        return subprocess.run(
            [sys.executable, "-m", "pixelart_converter", *extra_args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_module_smoke_exits_zero(self) -> None:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PIXELART_SMOKE"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "pixelart_converter"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

    def test_demo_error_logs_classified_message(self) -> None:
        result = self._run_module("--demo-error")
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn("encoder_unavailable", result.stderr)
        self.assertNotIn("probe:", result.stderr.split("detail:")[0])


if __name__ == "__main__":
    unittest.main()
