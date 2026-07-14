#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PACKAGE_VERSION="${VOICE_ASSISTANT_PACKAGE_VERSION:-2.0.1-test.4}"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64)
    ARCH_LABEL="AppleSilicon"
    ;;
  x86_64)
    ARCH_LABEL="Intel"
    ;;
  *)
    echo "Unsupported macOS architecture: $ARCH" >&2
    exit 1
    ;;
esac

BUILD_ROOT="$ROOT_DIR/build/macos"
ICONSET="$BUILD_ROOT/AppIcon.iconset"
ICNS="$BUILD_ROOT/AppIcon.icns"
DIST_ROOT="$ROOT_DIR/dist"
APP_PATH="$DIST_ROOT/语音输入助手.app"
OUTPUT_ROOT="$ROOT_DIR/macos-output"
STAGING="$BUILD_ROOT/dmg-staging"
DMG_NAME="VoiceInputAssistant-${PACKAGE_VERSION}-macOS-${ARCH_LABEL}.dmg"
DMG_PATH="$OUTPUT_ROOT/$DMG_NAME"

rm -rf "$ROOT_DIR/build" "$DIST_ROOT" "$OUTPUT_ROOT"
mkdir -p "$ICONSET" "$OUTPUT_ROOT"

SOURCE_ICON="$ROOT_DIR/assets/app-icon-v2.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$SOURCE_ICON" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double_size=$((size * 2))
  sips -z "$double_size" "$double_size" "$SOURCE_ICON" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"

python3 -m PyInstaller --noconfirm --clean "voice-assistant-macos.spec"
test -d "$APP_PATH"

# A personal test build uses an ad-hoc signature. It is intentionally not
# notarized and therefore still needs the user's first-launch approval.
codesign --force --deep --sign - --timestamp=none "$APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP_PATH" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
cp "$ROOT_DIR/macos/安装说明.txt" "$STAGING/安装说明.txt"

hdiutil create \
  -volname "语音输入助手" \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

shasum -a 256 "$DMG_PATH" > "$DMG_PATH.sha256.txt"
echo "$DMG_PATH"
