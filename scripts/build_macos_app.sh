#!/usr/bin/env bash
#
# Build the unsigned onedir macOS .app with PyInstaller.
#
# Usage:
#   scripts/build_macos_app.sh
#
# Refuses to run when vendor/ffmpeg/macos/ffmpeg is missing or free disk is
# under 5 GB (override with PIXELART_APP_MIN_FREE_MB). Does not install
# PyInstaller. Written for bash 3.2 (the /bin/bash shipped with macOS).

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SPEC="$REPO_ROOT/packaging/macos.spec"
FFMPEG="${PIXELART_FFMPEG_BUNDLE:-$REPO_ROOT/vendor/ffmpeg/macos/ffmpeg}"
MIN_FREE_MB="${PIXELART_APP_MIN_FREE_MB:-5120}"
PYTHON="${PYTHON:-python3}"

die() {
    echo "error: $*" >&2
    exit 1
}

free_mb() {
    local target="$1"
    while [ ! -d "$target" ]; do
        target=$(dirname "$target")
    done
    df -Pk "$target" | awk 'NR == 2 { print int($4 / 1024) }'
}

[ -f "$SPEC" ] || die "missing PyInstaller spec at $SPEC"

problems=0

if [ ! -f "$FFMPEG" ]; then
    echo "error: bundled ffmpeg is missing at $FFMPEG.
The .app cannot convert without it. Build it first:
  scripts/build_ffmpeg_lgpl.sh" >&2
    problems=1
fi

AVAILABLE_MB=$(free_mb "$REPO_ROOT")
if [ "$AVAILABLE_MB" -lt "$MIN_FREE_MB" ]; then
    echo "error: only ${AVAILABLE_MB} MB free where the .app would be built ($REPO_ROOT), need ${MIN_FREE_MB} MB (5 GB).
PyInstaller plus Qt/FFmpeg staging needs several GB. Free disk space before building.
This machine cannot produce the .app until ffmpeg is built and disk is freed." >&2
    problems=1
fi

if [ "$problems" -ne 0 ]; then
    die "cannot build the macOS .app until the problems above are fixed"
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    die "PyInstaller is not installed for $PYTHON.
On a machine with enough disk: pip install pyinstaller
Do not install it on a volume that is already nearly full."
fi

cd "$REPO_ROOT"
echo "building unsigned onedir .app with $PYTHON -m PyInstaller"
"$PYTHON" -m PyInstaller --noconfirm --clean "$SPEC"

APP="$REPO_ROOT/dist/pixelart-converter.app"
[ -d "$APP" ] || die "PyInstaller finished but $APP was not created"

# datas copies can drop the execute bit; restore it on any bundled ffmpeg.
find "$APP" -type f -name ffmpeg -exec chmod +x {} +

echo "ok: $APP"
echo "Unsigned local run: open \"$APP\""
echo "Gatekeeper may block the first launch; see docs/packaging.md"
