"""Headless smoke: the window can be created and the process exits 0."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest


class SmokeTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
