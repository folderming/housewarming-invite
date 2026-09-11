#!/usr/bin/env bash
# Packages the signed app into a DMG, notarizes it and staples the ticket.
#
# Prerequisites, once per machine:
#   xcrun notarytool store-credentials lidfade-notary \
#     --apple-id you@example.com --team-id TEAMID --password <app-specific-password>
#
# Usage:
#   SIGN_ID="Developer ID Application: You (TEAMID)" ./scripts/notarize.sh
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="LidFade"
BUILD_DIR=".build/bundle"
APP="${BUILD_DIR}/${APP_NAME}.app"
DMG="${BUILD_DIR}/${APP_NAME}.dmg"
PROFILE="${NOTARY_PROFILE:-lidfade-notary}"
SIGN_ID="${SIGN_ID:?SIGN_ID must be set to your Developer ID Application identity}"

test -d "${APP}" || { echo "run build-app.sh first" >&2; exit 1; }

echo "==> Creating ${DMG}"
rm -f "${DMG}"
STAGE=$(mktemp -d)
cp -R "${APP}" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"
hdiutil create -volname "${APP_NAME}" -srcfolder "${STAGE}" \
  -ov -format UDZO "${DMG}"
rm -rf "${STAGE}"

echo "==> Signing the disk image"
codesign --force --sign "${SIGN_ID}" --timestamp "${DMG}"

echo "==> Submitting for notarization (this usually takes a few minutes)"
xcrun notarytool submit "${DMG}" --keychain-profile "${PROFILE}" --wait

echo "==> Stapling"
xcrun stapler staple "${DMG}"
xcrun stapler validate "${DMG}"

# Proves the result is what a first-time downloader will actually get.
echo "==> Gatekeeper assessment"
spctl -a -vvv -t install "${DMG}" || true

echo "==> Ready to ship: ${DMG}"
