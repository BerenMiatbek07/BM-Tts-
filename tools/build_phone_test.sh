#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
DIST=/home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa
SDK=/home/beren/.buildozer/android/platform/android-sdk
OUT=/mnt/c/Users/Берен/Downloads/BM_Text_to_Voice_v5.6.2_PHONE_TEST.apk
DEBUG_KEYSTORE=/home/beren/.android/debug.keystore

test -s "$DEBUG_KEYSTORE"
python3 "$SOURCE_PROJECT/tools/patch_android_manifest.py" test \
  "$DIST/src/main/AndroidManifest.xml"
bash "$SOURCE_PROJECT/tools/sync_runtime_to_dist.sh" "$DIST"

cd "$DIST"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export GRADLE_USER_HOME=/mnt/d/BM_TTS_BUILD_CACHE/gradle-bmtts-sherpa
./gradlew assembleRelease --offline --no-daemon --rerun-tasks \
  --init-script "$SOURCE_PROJECT/tools/phone_test.init.gradle"

RAW="$(find build/outputs/apk/release -maxdepth 1 -type f -name '*.apk' \
  -printf '%T@ %p\n' | sort -n | tail -n1 | cut -d' ' -f2-)"
BT="$(find "$SDK/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n1)"
"$BT/zipalign" -f -P 16 -v 4 "$RAW" /tmp/bmtts_phone_aligned.apk
"$BT/apksigner" sign \
  --ks "$DEBUG_KEYSTORE" \
  --ks-key-alias androiddebugkey \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$OUT" \
  /tmp/bmtts_phone_aligned.apk
"$BT/apksigner" verify --verbose "$OUT"
"$BT/zipalign" -c -P 16 -v 4 "$OUT"
"$BT/aapt" dump badging "$OUT" | grep -F \
  "package: name='org.bmtts.bmtextspeech.test' versionCode='102640934' versionName='5.6.2'" >/dev/null
unzip -p "$OUT" assets/private.tar | tar -xOzf - ./main.py | \
  grep '^__version__ = "5.6.2"$' >/dev/null
echo "PHONE_TEST_APK_OK:$OUT"
