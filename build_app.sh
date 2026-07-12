#!/bin/bash
# Build "Mission Control.app" — a native Dock app wrapping app.py (pywebview).
# Idempotent: rebuilds the bundle + icon from source each run.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/Mission Control.app"
PY="$HERE/.venv/bin/python"

# --- icon: icon_1024.png -> icon.icns ---
ICONSET="$HERE/.icon.iconset"
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for s in 16 32 64 128 256 512 1024; do
  sips -z $s $s "$HERE/icon_1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
done
# retina @2x variants
cp "$ICONSET/icon_32x32.png"     "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"     "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png"   "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png"   "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$HERE/icon.icns"
rm -rf "$ICONSET"

# --- bundle skeleton ---
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$HERE/icon.icns" "$APP/Contents/Resources/icon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Mission Control</string>
    <key>CFBundleDisplayName</key><string>Mission Control</string>
    <key>CFBundleIdentifier</key><string>com.keane.mission-control.app</string>
    <key>CFBundleExecutable</key><string>launcher</string>
    <key>CFBundleIconFile</key><string>icon</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
exec "$PY" "$HERE/app.py"
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"

# refresh Launch Services / icon cache for this bundle
touch "$APP"
echo "built: $APP"
