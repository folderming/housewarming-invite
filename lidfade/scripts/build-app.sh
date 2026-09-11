#!/usr/bin/env bash
# Builds a universal LidFade.app bundle from the SwiftPM executable.
#
#   ./scripts/build-app.sh                       # unsigned, for local testing
#   SIGN_ID="Developer ID Application: You (TEAMID)" ./scripts/build-app.sh
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="LidFade"
BUILD_DIR=".build/bundle"
APP="${BUILD_DIR}/${APP_NAME}.app"
SIGN_ID="${SIGN_ID:-}"

echo "==> Building universal binary"
swift build -c release --arch arm64 --arch x86_64

BINARY=$(swift build -c release --arch arm64 --arch x86_64 --show-bin-path)/"${APP_NAME}"
test -f "${BINARY}" || { echo "build product missing: ${BINARY}" >&2; exit 1; }

echo "==> Assembling ${APP}"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
cp "${BINARY}" "${APP}/Contents/MacOS/${APP_NAME}"
cp Resources/Info.plist "${APP}/Contents/Info.plist"
printf 'APPL????' > "${APP}/Contents/PkgInfo"

if [ -f "Resources/AppIcon.icns" ]; then
  cp Resources/AppIcon.icns "${APP}/Contents/Resources/AppIcon.icns"
  /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" \
    "${APP}/Contents/Info.plist" 2>/dev/null || true
fi

if [ -n "${SIGN_ID}" ]; then
  echo "==> Signing with: ${SIGN_ID}"
  # Hardened Runtime is mandatory for notarization. Timestamps are mandatory
  # too, and are the single most common cause of a rejected submission.
  codesign --force --deep --options runtime --timestamp \
    --entitlements Resources/LidFade.entitlements \
    --sign "${SIGN_ID}" "${APP}"
  codesign --verify --strict --verbose=2 "${APP}"
else
  echo "==> No SIGN_ID set; leaving the bundle unsigned (local use only)"
fi

echo "==> Done: ${APP}"
