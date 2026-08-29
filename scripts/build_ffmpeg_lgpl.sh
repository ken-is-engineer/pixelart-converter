#!/usr/bin/env bash
#
# Build an LGPL FFmpeg (no GPL, no libx264) into vendor/ffmpeg/<platform>/.
#
# The configure flags come from vendor/ffmpeg/build_flags.txt so that the
# script, the documentation and the tests cannot drift apart. Every flag,
# including anything passed on the command line, is checked against a deny
# list first: this script refuses to produce a binary we may not ship.
#
# Usage:
#   scripts/build_ffmpeg_lgpl.sh [--check-flags] [--platform macos|windows]
#                                [--jobs N] [-- <extra configure flags>]
#
# Written for bash 3.2 (the /bin/bash shipped with macOS).

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
FLAGS_FILE="$REPO_ROOT/vendor/ffmpeg/build_flags.txt"
BUILD_DIR="${FFMPEG_BUILD_DIR:-$REPO_ROOT/.build/ffmpeg}"

# Free space needed to unpack the source and build it. The unpacked tree plus
# object files is well over 2 GB; stopping early beats failing at 90%.
MIN_FREE_MB="${FFMPEG_MIN_FREE_MB:-6000}"

# Substrings that must never appear in a configure flag. --enable-gpl and
# --enable-nonfree change the licence of the whole build; the libraries are the
# GPL-only or nonfree externals listed in FFmpeg's own licence documentation.
FORBIDDEN_SUBSTRINGS="
--enable-gpl
--enable-nonfree
libx264
libx265
libxvid
libxavs
libdavs2
libxavs2
librubberband
libvidstab
libsmbclient
libzvbi
libcdio
frei0r
fdk-aac
libnpp
decklink
"

die() {
    echo "error: $*" >&2
    exit 1
}

to_lower() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

# Reject a single configure flag if it would pull in GPL or nonfree code.
assert_flag_allowed() {
    local flag="$1"
    local origin="$2"
    local lowered
    local bad
    lowered=$(to_lower "$flag")
    for bad in $FORBIDDEN_SUBSTRINGS; do
        case "$lowered" in
        *"$bad"*)
            die "refusing to build: forbidden flag '$flag' (matched '$bad') from $origin.
The bundled FFmpeg must stay LGPL without libx264 (docs/requirements.md 5.2)."
            ;;
        esac
    done
}

read_setting() {
    local key="$1"
    local value
    value=$(sed -n "s/^${key}=//p" "$FLAGS_FILE" | head -n 1)
    [ -n "$value" ] || die "missing '$key=' in $FLAGS_FILE"
    printf '%s' "$value"
}

# Print the flags of one [section] of the flags file, one per line.
read_section() {
    local section="$1"
    awk -v want="[$section]" '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        /^\[.*\]$/ { in_section = ($0 == want); next }
        in_section && /^--/ { print }
    ' "$FLAGS_FILE"
}

detect_platform() {
    case "$(uname -s)" in
    Darwin) printf 'macos' ;;
    MINGW* | MSYS* | CYGWIN*) printf 'windows' ;;
    *) die "unsupported build host '$(uname -s)'. Pass --platform macos|windows." ;;
    esac
}

free_mb() {
    local target="$1"
    while [ ! -d "$target" ]; do
        target=$(dirname "$target")
    done
    df -Pk "$target" | awk 'NR == 2 { print int($4 / 1024) }'
}

CHECK_ONLY=0
PLATFORM=""
JOBS=""
EXTRA_FLAGS=""

while [ $# -gt 0 ]; do
    case "$1" in
    --check-flags)
        CHECK_ONLY=1
        shift
        ;;
    --platform)
        [ $# -ge 2 ] || die "--platform needs a value"
        PLATFORM="$2"
        shift 2
        ;;
    --jobs)
        [ $# -ge 2 ] || die "--jobs needs a value"
        JOBS="$2"
        shift 2
        ;;
    --help | -h)
        sed -n '3,15p' "$0"
        exit 0
        ;;
    --)
        shift
        EXTRA_FLAGS="$*"
        break
        ;;
    *)
        # Anything else is treated as an extra configure flag so that the deny
        # list also covers "let me just add --enable-gpl here" attempts.
        EXTRA_FLAGS="$EXTRA_FLAGS $1"
        shift
        ;;
    esac
done

[ -f "$FLAGS_FILE" ] || die "flags file not found: $FLAGS_FILE"
[ -n "$PLATFORM" ] || PLATFORM=$(detect_platform)
case "$PLATFORM" in
macos | windows) ;;
*) die "unknown platform '$PLATFORM' (expected macos or windows)" ;;
esac

VERSION=$(read_setting version)
SOURCE_URL=$(read_setting source_url)

CONFIGURE_FLAGS=""
for flag in $(read_section common) $(read_section "$PLATFORM"); do
    assert_flag_allowed "$flag" "$FLAGS_FILE"
    CONFIGURE_FLAGS="$CONFIGURE_FLAGS $flag"
done
[ -n "$CONFIGURE_FLAGS" ] || die "no configure flags found for platform '$PLATFORM' in $FLAGS_FILE"

for flag in $EXTRA_FLAGS; do
    assert_flag_allowed "$flag" "command line"
    CONFIGURE_FLAGS="$CONFIGURE_FLAGS $flag"
done

DEST_DIR="$REPO_ROOT/vendor/ffmpeg/$PLATFORM"
PREFIX="$BUILD_DIR/install-$PLATFORM"
CONFIGURE_LINE="./configure --prefix=$PREFIX$CONFIGURE_FLAGS"

echo "FFmpeg $VERSION ($PLATFORM)"
echo "source:  $SOURCE_URL"
echo "install: $DEST_DIR"
echo "configure:"
echo "  $CONFIGURE_LINE"

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "ok: no GPL or libx264 flags (checked ${FLAGS_FILE#"$REPO_ROOT"/} and command line)"
    exit 0
fi

AVAILABLE_MB=$(free_mb "$BUILD_DIR")
if [ "$AVAILABLE_MB" -lt "$MIN_FREE_MB" ]; then
    die "only ${AVAILABLE_MB} MB free where the build would run ($BUILD_DIR), need ${MIN_FREE_MB} MB.
Free some space, or point FFMPEG_BUILD_DIR at a larger volume."
fi

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v make >/dev/null 2>&1 || die "make is required"

TARBALL_NAME="ffmpeg-$VERSION.tar.xz"
SOURCE_DIR="$BUILD_DIR/ffmpeg-$VERSION"

mkdir -p "$BUILD_DIR"
if [ ! -f "$BUILD_DIR/$TARBALL_NAME" ]; then
    echo "downloading $SOURCE_URL"
    curl -fsSL -o "$BUILD_DIR/$TARBALL_NAME.part" "$SOURCE_URL"
    mv "$BUILD_DIR/$TARBALL_NAME.part" "$BUILD_DIR/$TARBALL_NAME"
fi

if command -v shasum >/dev/null 2>&1; then
    SHA256=$(shasum -a 256 "$BUILD_DIR/$TARBALL_NAME" | awk '{ print $1 }')
else
    SHA256=$(sha256sum "$BUILD_DIR/$TARBALL_NAME" | awk '{ print $1 }')
fi
echo "sha256:  $SHA256"

# Signature check when possible. The FFmpeg release key has to be imported
# beforehand; an unavailable signature is a warning, a bad one is fatal.
if command -v gpg >/dev/null 2>&1; then
    if curl -fsSL -o "$BUILD_DIR/$TARBALL_NAME.asc" "$SOURCE_URL.asc"; then
        if ! gpg --verify "$BUILD_DIR/$TARBALL_NAME.asc" "$BUILD_DIR/$TARBALL_NAME"; then
            die "GPG verification of $TARBALL_NAME failed"
        fi
    else
        echo "warning: could not download $SOURCE_URL.asc, skipping signature check" >&2
    fi
else
    echo "warning: gpg not installed, skipping signature check" >&2
fi

rm -rf "$SOURCE_DIR" "$PREFIX"
tar -xf "$BUILD_DIR/$TARBALL_NAME" -C "$BUILD_DIR"
[ -d "$SOURCE_DIR" ] || die "unexpected archive layout: $SOURCE_DIR not found"

if [ -z "$JOBS" ]; then
    JOBS=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)
fi

(
    cd "$SOURCE_DIR"
    # Word splitting is intended: CONFIGURE_FLAGS is a vetted flag list.
    # shellcheck disable=SC2086
    ./configure --prefix="$PREFIX" $CONFIGURE_FLAGS
    make -j"$JOBS"
    make install
)

if [ "$PLATFORM" = "windows" ]; then
    SUFFIX=".exe"
else
    SUFFIX=""
fi

mkdir -p "$DEST_DIR"
for tool in ffmpeg ffprobe; do
    [ -f "$PREFIX/bin/$tool$SUFFIX" ] || die "$tool was not built"
    cp "$PREFIX/bin/$tool$SUFFIX" "$DEST_DIR/$tool$SUFFIX"
done

for licence in COPYING.LGPLv2.1 LICENSE.md; do
    if [ -f "$SOURCE_DIR/$licence" ]; then
        cp "$SOURCE_DIR/$licence" "$DEST_DIR/$licence"
    fi
done

FFMPEG_BIN="$DEST_DIR/ffmpeg$SUFFIX"
VERSION_OUTPUT=$("$FFMPEG_BIN" -version 2>&1)

if printf '%s' "$VERSION_OUTPUT" | grep -qi -- 'libx264'; then
    rm -f "$DEST_DIR/ffmpeg$SUFFIX" "$DEST_DIR/ffprobe$SUFFIX"
    die "built binary reports libx264; removed it. Check for a stray x264 in the build environment."
fi
if printf '%s' "$VERSION_OUTPUT" | grep -qi -- '--enable-gpl'; then
    rm -f "$DEST_DIR/ffmpeg$SUFFIX" "$DEST_DIR/ffprobe$SUFFIX"
    die "built binary reports --enable-gpl; removed it."
fi

# Everything the LGPL source offer and a later audit need, next to the binary.
cat >"$DEST_DIR/BUILD-INFO.txt" <<EOF
ffmpeg $VERSION ($PLATFORM), built by scripts/build_ffmpeg_lgpl.sh
built at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
source:   $SOURCE_URL
sha256:   $SHA256
license:  LGPL v2.1 or later (no --enable-gpl, no libx264)

configure:
$CONFIGURE_LINE

ffmpeg -version:
$VERSION_OUTPUT
EOF

echo
echo "$VERSION_OUTPUT" | head -n 1
echo "ok: no libx264, no --enable-gpl. Installed to $DEST_DIR"
