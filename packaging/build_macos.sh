#!/bin/bash
# Build (and optionally sign + notarize) the distributable macOS app + DMG.
#
#   ./packaging/build_macos.sh                # unsigned build → dist/
#   CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
#   APPLE_ID=you@example.com APPLE_TEAM_ID=TEAMID APPLE_APP_PASSWORD=xxxx \
#   ./packaging/build_macos.sh                # signed + notarized + stapled
#
# APPLE_APP_PASSWORD is an app-specific password from appleid.apple.com.
# Unsigned builds are for local testing only — Gatekeeper will block them on
# other people's Macs (see DISTRIBUTION.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="${APP_VERSION:-1.0.0}"
PYI="${PYINSTALLER:-pyinstaller}"

command -v "$PYI" >/dev/null || {
  echo "pyinstaller not found — pip install pyinstaller" >&2; exit 1; }

rm -rf build dist
"$PYI" --noconfirm packaging/mission_control.spec
APP="dist/Mission Control.app"
[ -d "$APP" ] || { echo "build failed: $APP missing" >&2; exit 1; }

DMG="dist/MissionControl-${VERSION}.dmg"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Mission Control" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --force --sign "$CODESIGN_IDENTITY" "$DMG"
  if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_PASSWORD:-}" ]; then
    echo "notarizing (this waits for Apple)…"
    xcrun notarytool submit "$DMG" \
      --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
      --password "$APPLE_APP_PASSWORD" --wait
    xcrun stapler staple "$DMG"
    xcrun stapler staple "$APP"
    echo "notarized + stapled"
  else
    echo "signed but NOT notarized (set APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD)"
  fi
else
  echo "UNSIGNED build — fine locally, Gatekeeper will block it elsewhere"
fi
echo "done: $DMG"
