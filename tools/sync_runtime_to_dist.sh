#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${1:?dist path is required}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

PY_MODULES=(
  main android_activity generation edge_service admob_service app_log audio_player audio_transcode
  desktop_io storage script_logic spreadsheet_io text_io offline_voice_catalog
  offline_voice_manager sherpa_generation sherpa_probe timecode_generation
  voice_clone_security voice_clone_engine clone_generation
  voice_clone_billing
)

for module in "${PY_MODULES[@]}"; do
  test -s "$SOURCE_PROJECT/$module.py"
  cp -f "$SOURCE_PROJECT/$module.py" "$STAGE/$module.py"
done
cp -a "$SOURCE_PROJECT/assets" "$STAGE/assets"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$STAGE" -type f -name '*.pyc' -delete

PRIVATE_TAR="$(find "$DIST" -type f -path '*/assets/private.tar' -print -quit)"
test -n "$PRIVATE_TAR" && test -f "$PRIVATE_TAR"
NEW_PRIVATE="$(mktemp)"
tar -czf "$NEW_PRIVATE" -C "$STAGE" .
mv -f "$NEW_PRIVATE" "$PRIVATE_TAR"
gzip -t "$PRIVATE_TAR"
if tar -tzf "$PRIVATE_TAR" | sed 's#^\./##' | grep -qx 'voice_consent_models.py'; then
  echo "retired voice_consent_models.py leaked into private.tar" >&2
  exit 8
fi

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$SOURCE_PROJECT/main.py" | head -n1)"
test -n "$VERSION"
tar -xOzf "$PRIVATE_TAR" ./main.py | grep "^__version__ = \"$VERSION\"$" >/dev/null

PRIVATE_HASH="$(sha1sum "$PRIVATE_TAR" | awk '{print $1}')"
while IFS= read -r strings; do
  python3 - "$strings" "$PRIVATE_HASH" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
s, count = re.subn(
    r'(<string\s+name="private_version">)[^<]*(</string>)',
    rf'\g<1>{sys.argv[2]}\g<2>',
    s,
)
if count:
    p.write_text(s, encoding="utf-8")
PY
done < <(find "$DIST" -path '*/res/values/strings.xml' -type f)

JAVA_DEST="$DIST/src/main/java/org/bmtts/bmtextspeech"
mkdir -p "$JAVA_DEST" "$DIST/libs" "$DIST/src/main/jniLibs/arm64-v8a"
cp -f "$SOURCE_PROJECT/android_src/org/bmtts/bmtextspeech/"*.java "$JAVA_DEST/"
cp -f "$SOURCE_PROJECT/libs/sherpa-onnx-1.13.4.jar" "$DIST/libs/"
cp -f "$SOURCE_PROJECT/libs/android-v8/"*.so "$DIST/src/main/jniLibs/arm64-v8a/"
python3 "$SOURCE_PROJECT/tools/patch_python_activity_bridge.py" \
  "$DIST/src/main/java/org/kivy/android/PythonActivity.java"
if grep -R -q -E 'prepareVoiceReference|evaluateVoiceConsent' \
  "$DIST/src/main/java/org/bmtts/bmtextspeech" \
  "$DIST/src/main/java/org/kivy/android/PythonActivity.java"; then
  echo "retired consent bridge API leaked into Java sources" >&2
  exit 9
fi
python3 "$SOURCE_PROJECT/tools/patch_billing_dependency.py" \
  "$DIST/build.gradle"
grep -q "com.android.billingclient:billing:9.1.0" "$DIST/build.gradle"

echo "RUNTIME_SYNC_OK:version=$VERSION private=$PRIVATE_TAR"
