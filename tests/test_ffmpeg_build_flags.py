"""The documented FFmpeg build must stay LGPL: no --enable-gpl, no libx264."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "ffmpeg"
FLAGS_FILE = VENDOR_DIR / "build_flags.txt"
VENDOR_README = VENDOR_DIR / "README.md"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_ffmpeg_lgpl.sh"

BLOCK_START = "<!-- BEGIN build_flags.txt -->"
BLOCK_END = "<!-- END build_flags.txt -->"

# Substrings that turn the build into GPL, or into something we may not ship.
FORBIDDEN = ("--enable-gpl", "--enable-nonfree", "libx264", "libx265", "libxvid")


def parse_flags(text: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Split the flags file into 'key=value' settings and per-section flags."""
    settings: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], [])
        elif line.startswith("--"):
            if current is None:
                raise AssertionError(f"flag outside of any section: {line}")
            current.append(line)
        elif "=" in line:
            key, _, value = line.partition("=")
            settings[key.strip()] = value.strip()
        else:
            raise AssertionError(f"unparsable line: {line}")
    return settings, sections


class BuildFlagsFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FLAGS_FILE.read_text(encoding="utf-8")
        self.settings, self.sections = parse_flags(self.text)

    def test_no_gpl_or_x264_anywhere_in_the_file(self) -> None:
        lowered = self.text.lower()
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, lowered)

    def test_gpl_and_nonfree_are_explicitly_disabled(self) -> None:
        common = self.sections["common"]
        self.assertIn("--disable-gpl", common)
        self.assertIn("--disable-nonfree", common)

    def test_external_libraries_are_not_autodetected(self) -> None:
        # Without this an x264 installed on the build machine gets linked in.
        self.assertIn("--disable-autodetect", self.sections["common"])

    def test_version_and_source_are_pinned(self) -> None:
        version = self.settings["version"]
        self.assertRegex(version, r"^\d+\.\d+(\.\d+)?$")
        self.assertIn(version, self.settings["source_url"])

    def test_hardware_encoders_are_enabled_per_platform(self) -> None:
        self.assertIn("--enable-videotoolbox", self.sections["macos"])
        self.assertIn("--enable-encoder=h264_videotoolbox", self.sections["macos"])
        self.assertIn("--enable-mediafoundation", self.sections["windows"])
        self.assertIn("--enable-encoder=h264_mf", self.sections["windows"])


class VendorReadmeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = VENDOR_README.read_text(encoding="utf-8")

    def _embedded_flags(self) -> str:
        _, _, rest = self.text.partition(BLOCK_START)
        block, marker, _ = rest.partition(BLOCK_END)
        self.assertTrue(marker, f"{BLOCK_END} not found in {VENDOR_README}")
        block = block.strip()
        self.assertTrue(block.startswith("```text"), "embedded block must be fenced")
        self.assertTrue(block.endswith("```"), "embedded block must be fenced")
        return block[len("```text") : -len("```")].strip()

    def test_embedded_flags_match_the_flags_file(self) -> None:
        self.assertEqual(
            self._embedded_flags(),
            FLAGS_FILE.read_text(encoding="utf-8").strip(),
        )

    def test_documents_the_pinned_version(self) -> None:
        settings, _ = parse_flags(FLAGS_FILE.read_text(encoding="utf-8"))
        self.assertIn(settings["version"], self.text)

    def test_warns_against_public_gpl_builds(self) -> None:
        self.assertIn("gyan.dev", self.text)
        self.assertIn("libx264", self.text)

    def test_mentions_the_lgpl_source_offer(self) -> None:
        self.assertIn("ソース", self.text)
        self.assertIn("LGPL", self.text)


class BuildScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is not available")

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(BUILD_SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_check_flags_prints_a_clean_configure_line(self) -> None:
        for platform in ("macos", "windows"):
            with self.subTest(platform=platform):
                result = self._run("--check-flags", "--platform", platform)
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                configure_lines = [
                    line
                    for line in result.stdout.lower().splitlines()
                    if "./configure" in line
                ]
                self.assertEqual(len(configure_lines), 1, msg=result.stdout)
                for forbidden in FORBIDDEN:
                    self.assertNotIn(forbidden, configure_lines[0])

    def test_refuses_gpl_flag_from_the_command_line(self) -> None:
        result = self._run("--check-flags", "--platform", "macos", "--enable-gpl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--enable-gpl", result.stderr)

    def test_refuses_x264_flag_from_the_command_line(self) -> None:
        result = self._run("--check-flags", "--platform", "macos", "--enable-libx264")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("libx264", result.stderr)


class VendorLayoutTest(unittest.TestCase):
    def test_platform_directories_exist(self) -> None:
        for platform in ("macos", "windows"):
            self.assertTrue((VENDOR_DIR / platform / ".gitkeep").is_file())

    def _check_ignore(self, path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            self.skipTest("git check-ignore is unavailable here")
        return result.returncode == 0

    def test_gitignore_hides_binaries_but_keeps_the_documentation(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is not available")
        for ignored in (
            "vendor/ffmpeg/macos/ffmpeg",
            "vendor/ffmpeg/windows/ffmpeg.exe",
            "vendor/ffmpeg/macos/BUILD-INFO.txt",
        ):
            with self.subTest(path=ignored):
                self.assertTrue(self._check_ignore(ignored))
        for kept in (
            "vendor/ffmpeg/README.md",
            "vendor/ffmpeg/build_flags.txt",
            "vendor/ffmpeg/macos/.gitkeep",
            "vendor/ffmpeg/windows/.gitkeep",
        ):
            with self.subTest(path=kept):
                self.assertFalse(self._check_ignore(kept))


if __name__ == "__main__":
    unittest.main()
