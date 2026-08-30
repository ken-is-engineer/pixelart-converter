# PyInstaller spec for an onedir macOS .app (COLLECT + BUNDLE).
#
# Entry is the same as `python -m pixelart_converter`: src/pixelart_converter/__main__.py
# with `src` on pathex. Bundle name is pixelart-converter.
#
# Qt: the runtime dependency is PySide6-Essentials (not the full PySide6
# metapackage). Analysis excludes Addons modules so a machine that happens to
# have Addons installed does not pull them into the .app.
#
# ffmpeg: copied into datas as vendor/ffmpeg/macos/ffmpeg when present so
# conversion.binary.resolve_ffmpeg can find it under sys._MEIPASS. Missing
# binary prints a warning; scripts/build_macos_app.sh refuses to build.

from __future__ import annotations

import sys
from pathlib import Path

# PyInstaller injects SPEC (this file's path) when it evaluates the spec.
REPO_ROOT = Path(SPEC).resolve().parent.parent
SRC = REPO_ROOT / "src"
FFMPEG_SRC = REPO_ROOT / "vendor" / "ffmpeg" / "macos" / "ffmpeg"
FFPROBE_SRC = FFMPEG_SRC.parent / "ffprobe"
LICENSES_DIR = REPO_ROOT / "third_party_licenses"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PyInstaller.utils.hooks import collect_submodules

# PySide6-Addons (and other unused Qt) — Essentials is enough for this GUI.
PYSIDE6_ADDONS_EXCLUDES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQuick3D",
    "PySide6.QtRemoteObjects",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtScxml",
]

datas: list[tuple[str, str]] = []
if FFMPEG_SRC.is_file():
    datas.append((str(FFMPEG_SRC), "vendor/ffmpeg/macos"))
    if FFPROBE_SRC.is_file():
        datas.append((str(FFPROBE_SRC), "vendor/ffmpeg/macos"))
else:
    print(
        "WARNING: vendor/ffmpeg/macos/ffmpeg is missing; the .app cannot convert. "
        "Build it with scripts/build_ffmpeg_lgpl.sh before packaging.",
        file=sys.stderr,
    )

if LICENSES_DIR.is_dir():
    datas.append((str(LICENSES_DIR), "third_party_licenses"))
else:
    print(
        "WARNING: third_party_licenses/ is missing; license texts will not ship.",
        file=sys.stderr,
    )

hiddenimports = collect_submodules("pixelart_converter") + [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PIL",
    "PIL.Image",
    "PIL.GifImagePlugin",
]

a = Analysis(
    [str(SRC / "pixelart_converter" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PYSIDE6_ADDONS_EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pixelart-converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="pixelart-converter",
)

app = BUNDLE(
    coll,
    name="pixelart-converter.app",
    icon=None,
    bundle_identifier="engineer.ken.pixelart-converter",
    info_plist={
        "CFBundleName": "pixelart-converter",
        "CFBundleDisplayName": "pixelart-converter",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
