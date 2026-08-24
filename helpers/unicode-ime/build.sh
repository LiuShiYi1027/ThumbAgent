#!/bin/bash
# Build the ThumbAgent Unicode IME helper APK without Gradle.
#
# 信任模型见 README.md 与 ADR-0019：源码入仓、一次性本地构建、
# 产物 APK 与 SHA-256 固定登记；签名密钥仅用于本仓库内固定产物，
# 不承载任何外部安全语义。
#
# 依赖：Android SDK（build-tools + platforms）与 JDK 17+。
set -euo pipefail

HELPER_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$HELPER_DIR/build"
DIST_DIR="$HELPER_DIR/dist"
APK_NAME="unicode-ime.apk"

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
if [[ ! -d "$ANDROID_HOME/build-tools" ]]; then
  echo "error: Android SDK build-tools not found under $ANDROID_HOME" >&2
  exit 1
fi
BUILD_TOOLS="$(ls -1d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
PLATFORM="$(ls -1d "$ANDROID_HOME"/platforms/android-* | sort -V | tail -1)"
AAPT2="$BUILD_TOOLS/aapt2"
D8="$BUILD_TOOLS/d8"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"
ANDROID_JAR="$PLATFORM/android.jar"

# JDK：优先 JAVA_HOME，其次已知安装位置。
if [[ -n "${JAVA_HOME:-}" && -x "$JAVA_HOME/bin/javac" ]]; then
  :
elif [[ -x /opt/homebrew/opt/openjdk@17/bin/javac ]]; then
  JAVA_HOME=/opt/homebrew/opt/openjdk@17
elif [[ -x /usr/local/opt/openjdk@17/bin/javac ]]; then
  JAVA_HOME=/usr/local/opt/openjdk@17
else
  echo "error: JDK 17+ not found (set JAVA_HOME or brew install openjdk@17)" >&2
  exit 1
fi
JAVAC="$JAVA_HOME/bin/javac"
export PATH="$JAVA_HOME/bin:$PATH"

KEYSTORE="$HELPER_DIR/keystore.jks"
KEYSTORE_PASSWORD="thumbagent-unicode-ime"
KEY_ALIAS="unicode-ime"

if [[ ! -f "$KEYSTORE" ]]; then
  echo "error: keystore.jks missing; it is a committed build fixture" >&2
  echo "       regenerate with:" >&2
  echo "       keytool -genkeypair -keystore keystore.jks -alias $KEY_ALIAS \\" >&2
  echo "         -keyalg RSA -keysize 2048 -validity 10000 \\" >&2
  echo "         -storepass $KEYSTORE_PASSWORD -keypass $KEYSTORE_PASSWORD \\" >&2
  echo "         -dname \"CN=ThumbAgent Unicode IME, O=ThumbAgent\"" >&2
  exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/classes" "$BUILD_DIR/dex" "$DIST_DIR"

echo "==> aapt2 compile"
"$AAPT2" compile --dir "$HELPER_DIR/res" -o "$BUILD_DIR/res.zip"

echo "==> aapt2 link"
"$AAPT2" link \
  -o "$BUILD_DIR/unsigned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$HELPER_DIR/AndroidManifest.xml" \
  --min-sdk-version 24 \
  --target-sdk-version 34 \
  "$BUILD_DIR/res.zip"

echo "==> javac"
"$JAVAC" --release 8 \
  -classpath "$ANDROID_JAR" \
  -d "$BUILD_DIR/classes" \
  "$HELPER_DIR/src/com/thumbagent/unicodeime/UnicodeImeService.java"

echo "==> d8"
"$D8" --min-api 24 --output "$BUILD_DIR/dex" \
  "$BUILD_DIR/classes/com/thumbagent/unicodeime/UnicodeImeService.class"

echo "==> package + align + sign"
# 固定 dex 的 zip 时间戳，保证同一工具链下重复构建产出相同 SHA-256。
touch -t 198001010000.00 "$BUILD_DIR/dex/classes.dex"
(cd "$BUILD_DIR/dex" && zip -q -X "$BUILD_DIR/unsigned.apk" classes.dex)
"$ZIPALIGN" -f 4 "$BUILD_DIR/unsigned.apk" "$BUILD_DIR/aligned.apk"
"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-pass "pass:$KEYSTORE_PASSWORD" \
  --ks-key-alias "$KEY_ALIAS" \
  --out "$DIST_DIR/$APK_NAME" \
  "$BUILD_DIR/aligned.apk"

DIGEST="$(shasum -a 256 "$DIST_DIR/$APK_NAME" | awk '{print $1}')"
echo "$DIGEST  $APK_NAME" > "$DIST_DIR/SHA256SUMS.txt"

echo ""
echo "built: $DIST_DIR/$APK_NAME"
echo "sha256: $DIGEST"
echo "若摘要有意变更（源码评审后重建），请同步更新 README.md 与 Runtime 登记值。"
