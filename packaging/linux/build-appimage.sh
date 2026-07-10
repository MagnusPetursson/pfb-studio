#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${1:-$ROOT/build/release-linux}"
DIST_DIR="${2:-$ROOT/dist}"
LINUXDEPLOY="${LINUXDEPLOY:-linuxdeploy-x86_64.AppImage}"
APPDIR="$BUILD_DIR/AppDir"

rm -rf "$APPDIR"
DESTDIR="$APPDIR" cmake --install "$BUILD_DIR" --prefix /usr --strip

mkdir -p "$DIST_DIR"
LDAI_OUTPUT="$DIST_DIR/PFB-Studio-0.1.0-x86_64.AppImage" \
LDAI_NO_APPSTREAM=1 \
APPIMAGE_EXTRACT_AND_RUN=1 "$LINUXDEPLOY" \
    --appdir "$APPDIR" \
    --output appimage
