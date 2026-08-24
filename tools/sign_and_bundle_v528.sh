#!/usr/bin/env bash
set -Eeuo pipefail

DIST="/home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa"
SDK="/home/beren/.buildozer/android/platform/android-sdk"
SOURCE_PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
KEYSTORE="/mnt/d/keystore/bmquiz.keystore"
KEY_ALIAS="bmquiz"
OUT_DIR="$(printf '%s\n' "$SOURCE_PROJECT" | sed -E 's#^(/mnt/c/Users/[^/]+).*#\1/Downloads#')"
TEST_APK="$OUT_DIR/BM_Text_to_Voice_v5.6.2_102640934_STUDIO_TEST_signed.apk"
PROD_AAB="$OUT_DIR/BM_Text_to_Voice_v5.6.2_102640934_STUDIO_PROD_signed.aab"

if [[ -z "${KS_PASS:-}" ]]; then
  echo "KS_PASS is required" >&2
  exit 2
fi

BUILD_TOOLS="$(find "$SDK/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n1)"
AAPT="$BUILD_TOOLS/aapt"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"

cd "$DIST"
RAW_APK="$(find build/outputs/apk/release -maxdepth 1 -type f -name '*.apk' -printf '%T@ %p\n' | sort -n | tail -n1 | cut -d' ' -f2-)"
test -s "$RAW_APK"
ALIGNED="/tmp/bmtts_v562_test_aligned.apk"
rm -f "$ALIGNED" "$TEST_APK" "$PROD_AAB"
"$ZIPALIGN" -f -P 16 -v 4 "$RAW_APK" "$ALIGNED"
"$ZIPALIGN" -c -P 16 -v 4 "$ALIGNED"
"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-key-alias "$KEY_ALIAS" \
  --ks-pass env:KS_PASS \
  --key-pass env:KS_PASS \
  --out "$TEST_APK" \
  "$ALIGNED"
"$APKSIGNER" verify --verbose --print-certs "$TEST_APK"
"$ZIPALIGN" -c -P 16 -v 4 "$TEST_APK"

python3 "$SOURCE_PROJECT/tools/patch_android_manifest.py" production "$DIST/src/main/AndroidManifest.xml"
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"
export GRADLE_USER_HOME="/mnt/d/BM_TTS_BUILD_CACHE/gradle-bmtts-sherpa"
export GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.parallel=false -Dorg.gradle.workers.max=2 -Dorg.gradle.jvmargs=-Xmx2048m -Dhttps.protocols=TLSv1.2,TLSv1.3"
./gradlew bundleRelease --offline --no-daemon
RAW_AAB="$(find build/outputs/bundle/release -maxdepth 1 -type f -name '*.aab' -printf '%T@ %p\n' | sort -n | tail -n1 | cut -d' ' -f2-)"
test -s "$RAW_AAB"
AAB_SIGNING_TMP="/tmp/bmtts_562_prod_signed.aab"
rm -f "$AAB_SIGNING_TMP" "$AAB_SIGNING_TMP.sig"
cp -f "$RAW_AAB" "$AAB_SIGNING_TMP"
jarsigner \
  -keystore "$KEYSTORE" \
  -storetype PKCS12 \
  -storepass:env KS_PASS \
  -keypass:env KS_PASS \
  -sigalg SHA256withRSA \
  -digestalg SHA-256 \
  "$AAB_SIGNING_TMP" "$KEY_ALIAS"
jarsigner -verify -verbose -certs "$AAB_SIGNING_TMP" >/dev/null
cp -f "$AAB_SIGNING_TMP" "$PROD_AAB"

BADGING="$($AAPT dump badging "$TEST_APK")"
grep -E "package:|sdkVersion:|targetSdkVersion:|launchable-activity:" <<<"$BADGING"
grep -q "versionCode='102640934'" <<<"$BADGING"
grep -q "versionName='5.6.2'" <<<"$BADGING"
grep -q "targetSdkVersion:'36'" <<<"$BADGING"
echo "SIGNED_TEST_APK_OK:$TEST_APK"
echo "SIGNED_PROD_AAB_OK:$PROD_AAB"
