#!/usr/bin/env bash
# Build RDP Tree.app and RDP Tree.dmg
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="RDP Tree"
DMG_NAME="RDP Tree"

echo "==> Cleaning previous build..."
rm -rf build dist

echo "==> Building .app with py2app..."
python3 setup.py py2app 2>&1 | grep -v "^creating\|^copying\|^--- Skipping"

echo "==> Staging DMG contents..."
DMG_STAGING="dist/dmg-staging"
rm -rf "$DMG_STAGING"
mkdir "$DMG_STAGING"
cp -R "dist/${APP_NAME}.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

echo "==> Creating .dmg..."
hdiutil create \
    -volname "$DMG_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "dist/${DMG_NAME}.dmg"

rm -rf "$DMG_STAGING"

echo ""
echo "Done!"
echo "  App:  dist/${APP_NAME}.app  ($(du -sh "dist/${APP_NAME}.app" | cut -f1))"
echo "  DMG:  dist/${DMG_NAME}.dmg  ($(du -sh "dist/${DMG_NAME}.dmg" | cut -f1))"
