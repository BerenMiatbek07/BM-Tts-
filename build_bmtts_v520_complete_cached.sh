#!/usr/bin/env bash
set -Eeuo pipefail

VERSION_NAME="5.6.2"
VERSION_CODE="102640934"
PACKAGE_NAME="org.bmtts.bmtextspeech"
DIST="/home/beren/bmtts_sherpa_16kb_clean_storage/dists/bmtextspeech16kb510sherpa"
SDK="/home/beren/.buildozer/android/platform/android-sdk"
NDK16="/home/beren/android-ndk-r25b-16kb-v510-clean"
TARGET_PROJECT="/home/beren/bmtts_build/project"
KEYSTORE="/mnt/d/keystore/bmquiz.keystore"
KEY_ALIAS="bmquiz"
SOURCE_PROJECT="$(cd "$(dirname "$0")" && pwd)"
DOWNLOADS="$(printf '%s\n' "$SOURCE_PROJECT" | sed -E 's#^(/mnt/c/Users/[^/]+).*#\1/Downloads#')"
BACKUP_ROOT="/mnt/d/BM_TTS_BACKUP"
APP_STAGE="/home/beren/bmtts_v520_private_stage"
REPORT="$DOWNLOADS/BM_TTS_v5.6.2_COMPLETE_BUILD_$(date +%Y%m%d_%H%M%S).log"

TEST_APK="$DOWNLOADS/BM_Text_to_Voice_v5.6.2_102640934_STUDIO_TEST_signed.apk"
PROD_AAB="$DOWNLOADS/BM_Text_to_Voice_v5.6.2_102640934_STUDIO_PROD_signed.aab"

TEST_APP_ID="ca-app-pub-3940256099942544~3347511713"
LIVE_APP_ID="ca-app-pub-2408723079137167~4524564324"
LIVE_APP_OPEN_ID="ca-app-pub-2408723079137167/3211628443"

PY_MODULES=(
  main android_activity generation edge_service admob_service app_log audio_player audio_transcode desktop_io
  storage script_logic spreadsheet_io text_io offline_voice_catalog
  offline_voice_manager sherpa_generation sherpa_probe timecode_generation
  voice_clone_security voice_clone_engine clone_generation
  voice_clone_billing
)
JAVA_CLASSES=(
  BmLaunchActivity BmPythonActivity BmAdMobBridge BmArchiveBridge
  BmSherpaTtsBridge BmZipVoiceCloneBridge BmVoiceConsentBridge
  BmSherpaSelfTestActivity BmBillingBridge
)

exec > >(tee "$REPORT") 2>&1

echo "=== BM Text to Voice v5.6.2 COMPLETE CACHED BUILD ==="
echo "Р‘Р°СЂ 16 KB native РєСЌС€ Т›РѕР»РґР°РЅС‹Р»Р°РґС‹; Python/Kivy/SDL Т›Р°Р№С‚Р° РєРѕРјРїРёР»СЏС†РёСЏР»Р°РЅР±Р°Р№РґС‹."
echo "РЈР°Т›С‹С‚: $(date)"
echo

for path in \
  "$DIST/gradlew" \
  "$SDK" \
  "$NDK16/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" \
  "$KEYSTORE" \
  "$SOURCE_PROJECT/main.py" \
  "$SOURCE_PROJECT/libs/sherpa-onnx-1.13.4-arm64.aar" \
  "$SOURCE_PROJECT/libs/sherpa-onnx-1.13.4.jar"
do
  test -e "$path" || { echo "ТљРђРўР•: С‚Р°Р±С‹Р»РјР°РґС‹: $path"; exit 2; }
done
for module in "${PY_MODULES[@]}"; do
  test -s "$SOURCE_PROJECT/$module.py" || { echo "ТљРђРўР•: $module.py Р¶РѕТ›"; exit 3; }
done
for class_name in "${JAVA_CLASSES[@]}"; do
  test -s "$SOURCE_PROJECT/android_src/org/bmtts/bmtextspeech/$class_name.java" \
    || { echo "ТљРђРўР•: $class_name.java Р¶РѕТ›"; exit 4; }
done

mkdir -p "$DOWNLOADS" "$BACKUP_ROOT"
BACKUP="$BACKUP_ROOT/BM_TTS_BEFORE_V520_$(date +%Y%m%d_%H%M%S).tar.gz"
if [[ "${BM_SKIP_BACKUP:-0}" != "1" && -d "$TARGET_PROJECT" ]]; then
  tar -czf "$BACKUP" -C "$(dirname "$TARGET_PROJECT")" "$(basename "$TARGET_PROJECT")"
  gzip -t "$BACKUP"
  echo "BACKUP_OK: $BACKUP"
else
  echo "BACKUP_SKIPPED: current source-only rebuild"
fi

echo
echo "=== v5.2.0 source РЅРµРіС–Р·РіС– project РїР°РїРєР°СЃС‹РЅР° РєУ©С€С–СЂС–Р»РµРґС– ==="
mkdir -p "$TARGET_PROJECT"
for module in "${PY_MODULES[@]}"; do
  cp -f "$SOURCE_PROJECT/$module.py" "$TARGET_PROJECT/$module.py"
done
cp -f "$SOURCE_PROJECT/buildozer.spec" "$TARGET_PROJECT/buildozer.spec"
rm -rf "$TARGET_PROJECT/assets" "$TARGET_PROJECT/android_src" "$TARGET_PROJECT/libs"
cp -a "$SOURCE_PROJECT/assets" "$TARGET_PROJECT/assets"
cp -a "$SOURCE_PROJECT/android_src" "$TARGET_PROJECT/android_src"
cp -a "$SOURCE_PROJECT/libs" "$TARGET_PROJECT/libs"

python3 - "$TARGET_PROJECT" "${PY_MODULES[@]}" <<'PY'
import py_compile
import sys
from pathlib import Path
root = Path(sys.argv[1])
for name in sys.argv[2:]:
    py_compile.compile(str(root / f"{name}.py"), doraise=True)
print("PYTHON_SOURCE_OK")
PY
echo "SOURCE_COPY_OK"

echo
echo "=== Р‘Р°СЂ native dist 16 KB РµРєРµРЅС– С‚РµРєСЃРµСЂС–Р»С–Рї Р¶Р°С‚С‹СЂ ==="
python3 - "$NDK16/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" "$DIST/libs/arm64-v8a" <<'PY'
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path
readelf, root_value = sys.argv[1:3]
root = Path(root_value)
bad=[]; checked=0
for so in sorted(root.glob("*.so")):
    if so.name == "libpybundle.so" or so.read_bytes()[:4] != b"\x7fELF":
        continue
    out=subprocess.check_output([readelf,"-lW",str(so)],text=True,errors="replace")
    aligns=[int(line.split()[-1],16) for line in out.splitlines() if re.match(r"\s*LOAD\s",line)]
    value=min(aligns) if aligns else 0
    print(f"{so.name}: 0x{value:x}")
    checked+=1
    if value < 0x4000: bad.append((so.name,hex(value)))
if bad:
    raise SystemExit(f"ТљРђРўР•: dist С–С€С–РЅРґРµ 4 KB ELF Р±Р°СЂ: {bad}")
print(f"CACHED_16KB_NATIVE_OK: {checked} ELF")
PY

echo
echo "=== private.tar v5.2.0 РјРѕРґСѓР»СЊРґРµСЂС–РјРµРЅ Р¶Р°ТЈР°СЂС‚С‹Р»Р°РґС‹ ==="
rm -rf "$APP_STAGE"
mkdir -p "$APP_STAGE"
for module in "${PY_MODULES[@]}"; do
  cp -f "$TARGET_PROJECT/$module.py" "$APP_STAGE/$module.py"
done
mkdir -p "$APP_STAGE/assets/ui_icons"
for icon_name in \
  waveform document spreadsheet clipboard trash timecode microphone \
  play pause save theme chevron_down
do
  cp -f "$SOURCE_PROJECT/assets/ui_icons/$icon_name.png" \
    "$APP_STAGE/assets/ui_icons/$icon_name.png"
done
mkdir -p "$APP_STAGE/assets/voice_previews"
cp -f "$SOURCE_PROJECT/assets/voice_previews/iseke.wav" \
  "$APP_STAGE/assets/voice_previews/iseke.wav"
cp -f "$SOURCE_PROJECT/assets/voice_previews/raya.wav" \
  "$APP_STAGE/assets/voice_previews/raya.wav"
cp -f "$SOURCE_PROJECT/assets/voice_previews/daulet.mp3" \
  "$APP_STAGE/assets/voice_previews/daulet.mp3"
cp -f "$SOURCE_PROJECT/assets/cacert.pem" "$APP_STAGE/assets/cacert.pem"
find "$APP_STAGE" -type d -name __pycache__ -prune -exec rm -rf '{}' +
find "$APP_STAGE" -type f -name '*.pyc' -delete

PRIVATE_TAR="$(find "$DIST" -type f -path '*/assets/private.tar' -print -quit)"
test -n "$PRIVATE_TAR" && test -f "$PRIVATE_TAR" || {
  echo "ТљРђРўР•: dist С–С€С–РЅРґРµ assets/private.tar С‚Р°Р±С‹Р»РјР°РґС‹"; exit 5;
}
NEW_PRIVATE="$(mktemp)"
tar -czf "$NEW_PRIVATE" -C "$APP_STAGE" .
mv -f "$NEW_PRIVATE" "$PRIVATE_TAR"
gzip -t "$PRIVATE_TAR"
PRIVATE_LIST="$(tar -tzf "$PRIVATE_TAR" | sed 's#^\./##')"
for module in "${PY_MODULES[@]}"; do
  grep -qx "$module.py" <<<"$PRIVATE_LIST" || {
    echo "ТљРђРўР•: private.tar С–С€С–РЅРґРµ $module.py Р¶РѕТ›"; exit 6;
  }
done
grep -qx 'assets/ui_icons/waveform.png' <<<"$PRIVATE_LIST" || {
  echo "ERROR: private.tar missing PNG UI icons"; exit 6;
}
for runtime_asset in \
  assets/voice_previews/iseke.wav assets/voice_previews/raya.wav \
  assets/voice_previews/daulet.mp3 assets/cacert.pem
do
  grep -qx "$runtime_asset" <<<"$PRIVATE_LIST" || {
    echo "ERROR: private.tar missing $runtime_asset"; exit 6;
  }
done
PRIVATE_HASH="$(sha1sum "$PRIVATE_TAR" | awk '{print $1}')"
while IFS= read -r strings; do
  python3 - "$strings" "$PRIVATE_HASH" <<'PY'
import re, sys
from pathlib import Path
p=Path(sys.argv[1]); h=sys.argv[2]
s=p.read_text(encoding="utf-8")
s,n=re.subn(r'(<string\s+name="private_version">)[^<]*(</string>)',rf'\g<1>{h}\g<2>',s)
if n: p.write_text(s,encoding="utf-8")
PY
done < <(find "$DIST" -path '*/res/values/strings.xml' -type f)
echo "PRIVATE_MODULES_STAGED_OK: ${#PY_MODULES[@]} modules"

echo
echo "=== Sherpa JAR, native .so Р¶У™РЅРµ Java bridge Т›РѕСЃС‹Р»Р°РґС‹ ==="
mkdir -p "$DIST/libs" "$DIST/src/main/jniLibs/arm64-v8a"
cp -f "$TARGET_PROJECT/libs/sherpa-onnx-1.13.4.jar" "$DIST/libs/"
rm -f "$DIST/src/main/jniLibs/arm64-v8a"/libonnxruntime.so
rm -f "$DIST/src/main/jniLibs/arm64-v8a"/libsherpa-onnx-*.so
cp -f "$TARGET_PROJECT/libs/android-v8/"*.so "$DIST/src/main/jniLibs/arm64-v8a/"

# Stage the exact reviewed sources in the one Java root used by Gradle. This
# avoids an old cached p4a copy silently winning over the current source.
BRIDGE_PACKAGE="$DIST/src/main/java/org/bmtts/bmtextspeech"
mkdir -p "$BRIDGE_PACKAGE"
find "$DIST/src/main/java" -type f -name 'Bm*.java' -delete
for class_name in "${JAVA_CLASSES[@]}"; do
  cp -f \
    "$TARGET_PROJECT/android_src/org/bmtts/bmtextspeech/$class_name.java" \
    "$BRIDGE_PACKAGE/$class_name.java"
done

# PyJNIus reliably exposes the generated org.kivy.android.PythonActivity.
# Keep the Python-facing bridge methods on that exact class so a fresh cached
# build cannot regress to ClassNotFoundException/NoSuchMethod errors.
python3 - "$DIST/src/main/java/org/kivy/android/PythonActivity.java" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"Generated PythonActivity is missing: {path}")
source = path.read_text(encoding="utf-8")
marker = "    // Stable Python-facing API."
if marker not in source:
    methods = r'''
    // Stable Python-facing API. PyJNIus can always resolve this generated
    // activity class, even when an app-specific subclass is not visible.
    public String consumePendingActivityResult() {
        return org.bmtts.bmtextspeech.BmPythonActivity.consumeActivityResult();
    }

    public void extractTarBz2(String archivePath, String destinationPath)
            throws java.io.IOException {
        org.bmtts.bmtextspeech.BmArchiveBridge.extractTarBz2(
                archivePath, destinationPath);
    }

    public boolean synthesizeSherpaToWave(
            String modelDirectory, int numThreads, String text,
            int speakerId, float speed, String outputPath)
            throws java.io.IOException {
        return org.bmtts.bmtextspeech.BmAdMobBridge.synthesizeSherpaToWave(
                this, modelDirectory, numThreads, text, speakerId, speed,
                outputPath);
    }

    public void releaseSherpa() {
        org.bmtts.bmtextspeech.BmAdMobBridge.releaseSherpa();
    }

    public String sherpaRuntimeProbe() {
        return org.bmtts.bmtextspeech.BmSherpaTtsBridge.runtimeProbe(this);
    }

    public String startVoiceConsentRecording(int maxSeconds) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.startLiveRecording(
                this, maxSeconds);
    }

    public String startVoiceReferenceRecording(int maxSeconds) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.startReferenceRecording(
                this, maxSeconds);
    }

    public String stopVoiceConsentRecording() {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.stopLiveRecording();
    }

    public String voiceConsentRecordingStatus() {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.liveRecordingStatus();
    }

    public boolean deleteVoiceConsentAudio(String path) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.deleteConsentAudio(
                path, this);
    }

    public void initializeAds(String appOpenId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.initialize(this, appOpenId);
    }

    public void loadAppOpenAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadAppOpenAd(this, unitId);
    }

    public void loadAndShowAppOpenAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadAndShowAppOpenAd(this, unitId);
    }

    public void loadBanner(String slot, String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadBanner(this, slot, unitId);
    }

    public void updateBannerFrame(
            String slot, int x, int y, int width, int height,
            int windowHeight, boolean visible) {
        org.bmtts.bmtextspeech.BmAdMobBridge.updateBannerFrame(
                this, slot, x, y, width, height, windowHeight, visible);
    }

    public void loadInterstitialAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadInterstitialAd(this, unitId);
    }

    public void showInterstitialAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.showInterstitialAd(this, unitId);
    }

'''
    anchor = "    @Override\n    protected void onCreate(Bundle savedInstanceState)"
    if anchor not in source:
        raise SystemExit("PythonActivity onCreate anchor is missing")
    source = source.replace(anchor, methods + anchor, 1)
    path.write_text(source, encoding="utf-8")
print("PYTHON_ACTIVITY_BRIDGE_API_OK")
PY
python3 "$TARGET_PROJECT/tools/patch_python_activity_bridge.py" \
  "$DIST/src/main/java/org/kivy/android/PythonActivity.java"

python3 - "$DIST/build.gradle" <<'PY'
from __future__ import annotations
import re, sys
from pathlib import Path
path=Path(sys.argv[1])
s=path.read_text(encoding="utf-8")
s=re.sub(r"compileSdkVersion\s+\d+", "compileSdkVersion 36", s)
s=re.sub(r"targetSdkVersion\s+\d+", "targetSdkVersion 36", s)
s=re.sub(r"versionCode\s+\d+", "versionCode 102640934", s)
s=re.sub(r"versionName\s+'[^']+'", "versionName '5.6.2'", s)
# Remove stale local-AAR forms and prior source-root lines.
s=re.sub(r"(?m)^.*sherpa-onnx-1\.13\.4-arm64.*\n?", "", s)
s=re.sub(r"(?m)^.*android_src.*java\.srcDirs.*\n?", "", s)

def add_dependency(line: str) -> None:
    global s
    if line in s:
        return
    m=re.search(r"(?m)^dependencies\s*\{\s*$",s)
    if not m: raise SystemExit("dependencies block missing")
    s=s[:m.end()]+"\n    "+line+s[m.end():]

add_dependency("implementation files('libs/sherpa-onnx-1.13.4.jar')")
add_dependency("implementation 'org.apache.commons:commons-compress:1.26.2'")
add_dependency("implementation 'com.android.billingclient:billing:9.1.0'")

if "useLegacyPackaging true" not in s:
    marker="android {"
    block="""
    packagingOptions {
        jniLibs {
            useLegacyPackaging true
        }
    }
"""
    if marker not in s: raise SystemExit("android block missing")
    s=s.replace(marker,marker+block,1)

# Keep exactly one source root. Cached project/android_src paths are forbidden.
if "android.sourceSets.main.java.setSrcDirs([file('src/main/java')])" not in s:
    s += "\nandroid.sourceSets.main.java.setSrcDirs([file('src/main/java')])\n"
path.write_text(s,encoding="utf-8")
print("GRADLE_V520_PATCH_OK")
PY

if [[ -f "$DIST/gradle.properties" ]]; then
  grep -q '^android.suppressUnsupportedCompileSdk=' "$DIST/gradle.properties" \
    && sed -i 's/^android\.suppressUnsupportedCompileSdk=.*/android.suppressUnsupportedCompileSdk=36/' "$DIST/gradle.properties" \
    || printf '\nandroid.suppressUnsupportedCompileSdk=36\n' >> "$DIST/gradle.properties"
else
  printf 'android.suppressUnsupportedCompileSdk=36\n' > "$DIST/gradle.properties"
fi

grep -q "sherpa-onnx-1.13.4.jar" "$DIST/build.gradle"
grep -q "commons-compress:1.26.2" "$DIST/build.gradle"
grep -q "com.android.billingclient:billing:9.1.0" "$DIST/build.gradle"
echo "SHERPA_AND_ARCHIVE_BRIDGE_STAGED_OK"

patch_manifest() {
  local mode="$1"
  python3 - "$DIST/AndroidManifest.xml" "$DIST/src/main/AndroidManifest.xml" "$mode" <<'PY'
from __future__ import annotations
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID="http://schemas.android.com/apk/res/android"
A="{%s}"%ANDROID
ET.register_namespace("android",ANDROID)
mode=sys.argv[-1]
test_ads=mode=="test"
app_id=("ca-app-pub-3940256099942544~3347511713" if test_ads else "ca-app-pub-2408723079137167~4524564324")
paths=[Path(x) for x in sys.argv[1:-1]]

for path in paths:
    if not path.exists(): continue
    tree=ET.parse(path); root=tree.getroot(); app=root.find("application")
    if app is None: raise SystemExit(f"application missing: {path}")
    root.set(A+"versionCode","102640934")
    root.set(A+"versionName","5.6.2")
    app.set(A+"extractNativeLibs","true")
    app.set(A+"resizeableActivity","true")

    # Required permissions, without duplicates.
    wanted=(
      "android.permission.INTERNET",
      "android.permission.ACCESS_NETWORK_STATE",
      "android.permission.WAKE_LOCK",
      "android.permission.RECORD_AUDIO",
      "com.google.android.gms.permission.AD_ID",
    )
    existing={node.get(A+"name") for node in root.findall("uses-permission")}
    for permission in wanted:
        if permission not in existing:
            node=ET.Element("uses-permission"); node.set(A+"name",permission); root.insert(0,node)

    def name(node): return node.get(A+"name","")
    python_activity=None
    for node in app.findall("activity"):
        if name(node) in ("org.bmtts.bmtextspeech.BmPythonActivity","org.kivy.android.PythonActivity",".BmPythonActivity"):
            python_activity=node; break
    if python_activity is None: raise SystemExit(f"Python activity missing: {path}")
    python_activity.set(A+"name","org.bmtts.bmtextspeech.BmPythonActivity")
    python_activity.set(A+"exported","false")
    python_activity.set(A+"launchMode","singleTask")
    python_activity.set(A+"screenOrientation","portrait")
    for filt in list(python_activity.findall("intent-filter")):
        if any(x.get(A+"name")=="android.intent.action.MAIN" for x in filt.findall("action")) or any(x.get(A+"name")=="android.intent.category.LAUNCHER" for x in filt.findall("category")):
            python_activity.remove(filt)

    for node in list(app.findall("activity")):
        if name(node) in ("org.bmtts.bmtextspeech.BmLaunchActivity",".BmLaunchActivity"):
            app.remove(node)
    launch=ET.SubElement(app,"activity")
    launch.set(A+"name","org.bmtts.bmtextspeech.BmLaunchActivity")
    launch.set(A+"exported","true")
    launch.set(A+"launchMode","singleTask")
    launch.set(A+"theme","@android:style/Theme.Material.Light.NoActionBar")
    launch.set(A+"excludeFromRecents","false")
    launch.set(A+"screenOrientation","portrait")
    launch.set(A+"configChanges","mcc|mnc|locale|touchscreen|keyboard|keyboardHidden|navigation|screenLayout|fontScale|uiMode|orientation|screenSize|smallestScreenSize|density")
    filt=ET.SubElement(launch,"intent-filter")
    action=ET.SubElement(filt,"action"); action.set(A+"name","android.intent.action.MAIN")
    category=ET.SubElement(filt,"category"); category.set(A+"name","android.intent.category.LAUNCHER")

    # ADB-only end-to-end voice test. Never expose it in production.
    for node in list(app.findall("activity")):
        if name(node) in (
            "org.bmtts.bmtextspeech.BmSherpaSelfTestActivity",
            ".BmSherpaSelfTestActivity",
        ):
            app.remove(node)
    if test_ads:
        self_test=ET.SubElement(app,"activity")
        self_test.set(A+"name","org.bmtts.bmtextspeech.BmSherpaSelfTestActivity")
        self_test.set(A+"exported","true")
        self_test.set(A+"theme","@android:style/Theme.Material.Light.NoActionBar")
        self_test.set(A+"screenOrientation","portrait")

    def metadata(key,value):
        for node in list(app.findall("meta-data")):
            if node.get(A+"name")==key: app.remove(node)
        node=ET.SubElement(app,"meta-data"); node.set(A+"name",key); node.set(A+"value",value)
    metadata("com.google.android.gms.ads.APPLICATION_ID",app_id)
    metadata("BM_APP_OPEN_UNIT_ID","ca-app-pub-2408723079137167/3211628443")
    metadata("BM_USE_TEST_ADS","true" if test_ads else "false")
    tree.write(path,encoding="utf-8",xml_declaration=True)
print(f"MANIFEST_{mode.upper()}_OK")
PY
}

export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"
export GRADLE_USER_HOME="/mnt/d/BM_TTS_BUILD_CACHE/gradle-bmtts-sherpa"
export GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.parallel=false -Dorg.gradle.workers.max=2 -Dorg.gradle.jvmargs=-Xmx2048m -Dhttps.protocols=TLSv1.2,TLSv1.3"
cd "$DIST"

run_gradle() {
  if ./gradlew "$@" --offline --no-daemon; then
    echo "OFFLINE_GRADLE_OK: $*"
  else
    echo "РљСЌС€С‚Рµ Р¶Р°ТЈР° dependency Р¶РµС‚С–СЃРїРµР№РґС–; С‚РµРє СЃРѕРЅС‹ РѕРЅР»Р°Р№РЅ Р°Р»Р°РґС‹."
    ./gradlew "$@" --no-daemon
    echo "ONLINE_GRADLE_FALLBACK_OK: $*"
  fi
}

echo
echo "=== TEST APK: Google test ads ==="
patch_manifest test
run_gradle clean assembleRelease
RAW_APK="$(find build/outputs/apk/release -maxdepth 1 -type f -name '*.apk' -printf '%T@ %p\n' | sort -n | tail -n1 | cut -d' ' -f2-)"
test -s "$RAW_APK"

BUILD_TOOLS="$(find "$SDK/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n1)"
AAPT="$BUILD_TOOLS/aapt"; ZIPALIGN="$BUILD_TOOLS/zipalign"; APKSIGNER="$BUILD_TOOLS/apksigner"
for tool in "$AAPT" "$ZIPALIGN" "$APKSIGNER"; do test -x "$tool"; done
ALIGNED="/tmp/bmtts_v561_test_aligned.apk"
rm -f "$ALIGNED" "$TEST_APK" "$PROD_AAB"
"$ZIPALIGN" -f -P 16 -v 4 "$RAW_APK" "$ALIGNED"
"$ZIPALIGN" -c -P 16 -v 4 "$ALIGNED"

if [[ -z "${KS_PASS:-}" ]]; then
  read -rsp "Keystore password: " KS_PASS
  echo
fi
export KS_PASS
"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-key-alias "$KEY_ALIAS" \
  --ks-pass env:KS_PASS \
  --key-pass env:KS_PASS \
  --out "$TEST_APK" \
  "$ALIGNED"
"$APKSIGNER" verify --verbose --print-certs "$TEST_APK"
"$ZIPALIGN" -c -P 16 -v 4 "$TEST_APK"

echo
echo "=== PRODUCTION AAB: live ads ==="
patch_manifest production
run_gradle bundleRelease
RAW_AAB="$(find build/outputs/bundle/release -maxdepth 1 -type f -name '*.aab' -printf '%T@ %p\n' | sort -n | tail -n1 | cut -d' ' -f2-)"
test -s "$RAW_AAB"
AAB_SIGNING_TMP="/tmp/bmtts_561_prod_signed.aab"
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
unset KS_PASS
rm -f "$ALIGNED"

echo
echo "=== APK manifest/version verification ==="
BADGING="$($AAPT dump badging "$TEST_APK")"
grep -E "package:|sdkVersion:|targetSdkVersion:|launchable-activity:" <<<"$BADGING"
grep -q "versionCode='102640934'" <<<"$BADGING"
grep -q "versionName='5.6.2'" <<<"$BADGING"
grep -q "targetSdkVersion:'36'" <<<"$BADGING"
grep -q "launchable-activity: name='org.bmtts.bmtextspeech.BmLaunchActivity'" <<<"$BADGING"
MANIFEST_XML="$($AAPT dump xmltree "$TEST_APK" AndroidManifest.xml)"
grep -q 'android.permission.RECORD_AUDIO' <<<"$MANIFEST_XML"
grep -q 'com.android.vending.BILLING' <<<"$MANIFEST_XML"
grep -q "$TEST_APP_ID" <<<"$MANIFEST_XML"
AD_METADATA="$(grep -A3 -B2 'BM_USE_TEST_ADS' <<<"$MANIFEST_XML")"
grep -Eq '0xffffffff|Raw: "true"|="true"' <<<"$AD_METADATA"
echo "TEST_MANIFEST_AND_VERSION_OK"

python3 - "$PROD_AAB" "$LIVE_APP_ID" "$TEST_APP_ID" <<'PY'
import sys
import zipfile
from pathlib import Path
aab=Path(sys.argv[1]); live=sys.argv[2]; test=sys.argv[3]
with zipfile.ZipFile(aab) as z:
    data=z.read("base/manifest/AndroidManifest.xml")
def has(text: str) -> bool:
    return text.encode("utf-8") in data or text.encode("utf-16le") in data
if not has(live):
    raise SystemExit("ТљРђРўР•: production AAB manifest С–С€С–РЅРґРµ live AdMob app ID Р¶РѕТ›")
if has(test):
    raise SystemExit("ТљРђРўР•: production AAB manifest С–С€С–РЅРґРµ test AdMob app ID Т›Р°Р»С‹Рї Т›РѕР№РґС‹")
if not has("com.android.vending.BILLING"):
    raise SystemExit("ERROR: production AAB manifest missing Google Play Billing permission")
print("PRODUCTION_AAB_ADMOB_MANIFEST_OK")
PY

echo
echo "=== DEX and private modules verification ==="
VERIFY="$(mktemp -d)"
trap 'chmod -R u+rwX "$VERIFY" 2>/dev/null || true; rm -rf "$VERIFY" 2>/dev/null || true' EXIT
unzip -q "$TEST_APK" 'classes*.dex' -d "$VERIFY/dex"
for symbol in OfflineTtsConfig BmLaunchActivity BmPythonActivity BmAdMobBridge BmArchiveBridge BmSherpaTtsBridge BmZipVoiceCloneBridge BmVoiceConsentBridge BmBillingBridge startVoiceConsentRecording synthesizeZipVoiceToWave transcodeMp3ToWav voice_clone_lifetime recordCompletedGeneration; do
  grep -aR -q "$symbol" "$VERIFY/dex" || { echo "ТљРђРўР•: DEX С–С€С–РЅРґРµ $symbol Р¶РѕТ›"; exit 20; }
done
for retired_symbol in evaluateVoiceConsent prepareVoiceReference; do
  if grep -aR -q "$retired_symbol" "$VERIFY/dex"; then
    echo "ERROR: DEX contains retired consent symbol: $retired_symbol"; exit 20
  fi
done
echo "SHERPA_AND_BRIDGES_DEX_OK"

unzip -p "$TEST_APK" assets/private.tar > "$VERIFY/private.tar"
gzip -t "$VERIFY/private.tar"
APK_PRIVATE_LIST="$(tar -tzf "$VERIFY/private.tar" | sed 's#^\./##')"
for module in "${PY_MODULES[@]}"; do
  grep -qx "$module.py" <<<"$APK_PRIVATE_LIST" || {
    echo "ТљРђРўР•: APK private.tar С–С€С–РЅРґРµ $module.py Р¶РѕТ›"; exit 21;
  }
done
if grep -qx 'voice_consent_models.py' <<<"$APK_PRIVATE_LIST"; then
  echo "ERROR: APK private.tar contains retired voice_consent_models.py"; exit 21
fi
for runtime_asset in assets/voice_previews/iseke.wav assets/voice_previews/raya.wav assets/voice_previews/daulet.mp3 assets/cacert.pem; do
  grep -qx "$runtime_asset" <<<"$APK_PRIVATE_LIST" || {
    echo "ERROR: APK private.tar missing $runtime_asset"; exit 21;
  }
done
unzip -p "$PROD_AAB" base/assets/private.tar > "$VERIFY/private_aab.tar"
gzip -t "$VERIFY/private_aab.tar"
AAB_PRIVATE_LIST="$(tar -tzf "$VERIFY/private_aab.tar" | sed 's#^\./##')"
for module in "${PY_MODULES[@]}"; do
  grep -qx "$module.py" <<<"$AAB_PRIVATE_LIST" || {
    echo "ТљРђРўР•: AAB private.tar С–С€С–РЅРґРµ $module.py Р¶РѕТ›"; exit 22;
  }
done
if grep -qx 'voice_consent_models.py' <<<"$AAB_PRIVATE_LIST"; then
  echo "ERROR: AAB private.tar contains retired voice_consent_models.py"; exit 22
fi
for runtime_asset in assets/voice_previews/iseke.wav assets/voice_previews/raya.wav assets/voice_previews/daulet.mp3 assets/cacert.pem; do
  grep -qx "$runtime_asset" <<<"$AAB_PRIVATE_LIST" || {
    echo "ERROR: AAB private.tar missing $runtime_asset"; exit 22;
  }
done
echo "PRIVATE_MODULES_APK_AAB_OK: ${#PY_MODULES[@]} modules"

echo
echo "=== All top-level and Python-bundle ELF 16 KB verification ==="
python3 - "$NDK16/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" "$TEST_APK" "$PROD_AAB" <<'PY'
from __future__ import annotations
import io, re, subprocess, sys, tarfile, tempfile, zipfile
from pathlib import Path
readelf=sys.argv[1]
artifacts=[(Path(sys.argv[2]),"lib/arm64-v8a/"),(Path(sys.argv[3]),"base/lib/arm64-v8a/")]

def alignment(data: bytes, label: str) -> int:
    with tempfile.NamedTemporaryFile(suffix=".so") as temp:
        temp.write(data); temp.flush()
        out=subprocess.check_output([readelf,"-lW",temp.name],text=True,errors="replace")
    aligns=[int(line.split()[-1],16) for line in out.splitlines() if re.match(r"\s*LOAD\s",line)]
    value=min(aligns) if aligns else 0
    print(f"{label}: 0x{value:x}")
    return value

required={"libonnxruntime.so","libsherpa-onnx-c-api.so","libsherpa-onnx-cxx-api.so","libsherpa-onnx-jni.so"}
for artifact,prefix in artifacts:
    bad=[]; top=0; nested=0
    with zipfile.ZipFile(artifact) as z:
        names=[n for n in z.namelist() if n.startswith(prefix) and n.endswith(".so")]
        present={Path(n).name for n in names}
        if not required.issubset(present):
            raise SystemExit(f"{artifact.name}: Sherpa native missing: {required-present}")
        bundle_name=prefix+"libpybundle.so"
        bundle=z.read(bundle_name)
        for name in names:
            if name == bundle_name:
                continue
            data=z.read(name)
            if data[:4] != b"\x7fELF":
                bad.append((name,"NON_ELF")); continue
            value=alignment(data,f"{artifact.name}:{name}"); top+=1
            if value < 0x4000:
                bad.append((name,hex(value)))
    with tarfile.open(fileobj=io.BytesIO(bundle),mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".so"):
                continue
            f=tar.extractfile(member)
            if f is None:
                continue
            data=f.read()
            if data[:4] != b"\x7fELF":
                continue
            value=alignment(data,f"{artifact.name}:{member.name}"); nested+=1
            if value < 0x4000:
                bad.append((member.name,hex(value)))
    if top == 0 or nested == 0:
        raise SystemExit(f"{artifact.name}: ELF scan incomplete: top={top}, nested={nested}")
    if bad:
        raise SystemExit(f"{artifact.name}: 16KB check failed: {bad}")
    print(f"16KB_ARTIFACT_OK: {artifact.name}, top={top}, python_bundle={nested}")
print("16KB_APK_AAB_ALL_ELF_OK")
PY

sha256sum "$TEST_APK" > "$TEST_APK.sha256"
sha256sum "$PROD_AAB" > "$PROD_AAB.sha256"

echo
echo "============================================================"
echo "BM_TTS_V520_COMPLETE_BUILD_OK"
echo "TEST APK: $TEST_APK"
echo "PRODUCTION AAB: $PROD_AAB"
ls -lh "$TEST_APK" "$TEST_APK.sha256" "$PROD_AAB" "$PROD_AAB.sha256"
echo "LOG: $REPORT"
echo "============================================================"
