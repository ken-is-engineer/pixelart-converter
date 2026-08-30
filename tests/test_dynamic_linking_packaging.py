"""T6-3: packaging keeps Qt/PySide6 as dynamically linked shared libraries (onedir, not onefile)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MACOS_SPEC = REPO_ROOT / "packaging" / "macos.spec"
WINDOWS_SPEC = REPO_ROOT / "packaging" / "windows.spec"
BUILD_SCRIPTS = (
    REPO_ROOT / "scripts" / "build_macos_app.sh",
    REPO_ROOT / "scripts" / "build_windows.ps1",
)
SRC_DIR = REPO_ROOT / "src" / "pixelart_converter"


def _exe_block(spec_text: str) -> str:
    match = re.search(r"exe\s*=\s*EXE\s*\(", spec_text, flags=re.IGNORECASE)
    if match is None:
        raise AssertionError("EXE(...) block not found in spec")
    start = match.start()
    depth = 0
    for index in range(match.end() - 1, len(spec_text)):
        char = spec_text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return spec_text[start : index + 1]
    raise AssertionError("unterminated EXE(...) block in spec")


class SpecOnedirDynamicLinkingTest(unittest.TestCase):
    @staticmethod
    def _assert_onedir_not_onefile(spec_path: Path) -> None:
        text = spec_path.read_text(encoding="utf-8")
        self = unittest.TestCase()
        self.assertIn("COLLECT", text, msg=f"{spec_path.name} must use COLLECT for onedir")
        self.assertIn(
            "exclude_binaries=True",
            text,
            msg=f"{spec_path.name} EXE must set exclude_binaries=True (onedir)",
        )

        exe_block = _exe_block(text)
        self.assertNotIn(
            "a.binaries",
            exe_block,
            msg=f"{spec_path.name} EXE must not bundle a.binaries (onefile pattern)",
        )
        self.assertNotIn(
            "a.zipfiles",
            exe_block,
            msg=f"{spec_path.name} EXE must not bundle a.zipfiles (onefile pattern)",
        )
        self.assertNotIn(
            "a.datas",
            exe_block,
            msg=f"{spec_path.name} EXE must not bundle a.datas (onefile pattern)",
        )

    def test_macos_spec_is_onedir_collect_not_onefile(self) -> None:
        self._assert_onedir_not_onefile(MACOS_SPEC)

    def test_windows_spec_is_onedir_collect_not_onefile(self) -> None:
        self._assert_onedir_not_onefile(WINDOWS_SPEC)


class BuildScriptsNoOnefileTest(unittest.TestCase):
    def test_build_scripts_do_not_pass_onefile(self) -> None:
        for script in BUILD_SCRIPTS:
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file(), f"missing {script}")
                text = script.read_text(encoding="utf-8")
                self.assertNotIn(
                    "--onefile",
                    text,
                    msg=f"{script.name} must not pass PyInstaller --onefile",
                )
                self.assertIn("PyInstaller", text)


class AppUsesRuntimePySide6ImportTest(unittest.TestCase):
    """We depend on PySide6 at import/runtime, not compile-time Qt linking."""

    def test_source_imports_pyside6_not_native_qt(self) -> None:
        py_files = list(SRC_DIR.rglob("*.py"))
        self.assertTrue(py_files, "expected Python sources under src/pixelart_converter")
        combined = "\n".join(path.read_text(encoding="utf-8") for path in py_files)
        self.assertIn("PySide6", combined)
        self.assertNotRegex(combined, r"#include\s*<Qt")
        self.assertNotRegex(combined, r"find_package\s*\(\s*Qt")


class LgplQtDocTest(unittest.TestCase):
    def test_lgpl_qt_doc_covers_dynamic_linking(self) -> None:
        doc = (REPO_ROOT / "docs" / "lgpl-qt.md").read_text(encoding="utf-8")
        for fragment in (
            "COLLECT",
            "onedir",
            "onefile",
            "動的リンク",
            "pending",
            ".dylib",
            ".dll",
            "import PySide6",
        ):
            self.assertIn(fragment, doc, msg=f"lgpl-qt.md should mention {fragment!r}")


if __name__ == "__main__":
    unittest.main()
