#!/usr/bin/env python3
"""Patch the generated Android manifests for test or production packaging."""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ANDROID = "http://schemas.android.com/apk/res/android"
A = f"{{{ANDROID}}}"
ET.register_namespace("android", ANDROID)

TEST_APP_ID = "ca-app-pub-3940256099942544~3347511713"
LIVE_APP_ID = "ca-app-pub-2408723079137167~4524564324"
LIVE_APP_OPEN_ID = "ca-app-pub-2408723079137167/3211628443"


def patch_manifest(path: Path, *, test_ads: bool) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise RuntimeError(f"application missing: {path}")

    root.set(A + "versionCode", "102640934")
    root.set(A + "versionName", "5.6.2")
    app.set(A + "extractNativeLibs", "true")
    # BM Voice Studio is a phone-first portrait editor.  A resizable task lets
    # several OEM launchers restore it with the previous sensor orientation,
    # even though the activity requests portrait.  Lock the task as well as
    # each activity so reopening from Recents cannot rotate the Kivy surface.
    app.set(A + "resizeableActivity", "false")

    permissions = (
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.WAKE_LOCK",
        "android.permission.RECORD_AUDIO",
        "com.google.android.gms.permission.AD_ID",
    )
    existing = {node.get(A + "name") for node in root.findall("uses-permission")}
    for permission in permissions:
        if permission not in existing:
            node = ET.Element("uses-permission")
            node.set(A + "name", permission)
            root.insert(0, node)

    def android_name(node: ET.Element) -> str:
        return node.get(A + "name", "")

    python_activity = next(
        (
            node
            for node in app.findall("activity")
            if android_name(node)
            in {
                "org.bmtts.bmtextspeech.BmPythonActivity",
                "org.kivy.android.PythonActivity",
                ".BmPythonActivity",
            }
        ),
        None,
    )
    if python_activity is None:
        raise RuntimeError(f"Python activity missing: {path}")
    python_activity.set(A + "name", "org.bmtts.bmtextspeech.BmPythonActivity")
    python_activity.set(A + "exported", "false")
    python_activity.set(A + "launchMode", "singleTask")
    python_activity.set(A + "screenOrientation", "portrait")
    python_activity.set(A + "resizeableActivity", "false")
    for intent_filter in list(python_activity.findall("intent-filter")):
        values = {
            item.get(A + "name")
            for tag in ("action", "category")
            for item in intent_filter.findall(tag)
        }
        if "android.intent.action.MAIN" in values or "android.intent.category.LAUNCHER" in values:
            python_activity.remove(intent_filter)

    for node in list(app.findall("activity")):
        if android_name(node) in {
            "org.bmtts.bmtextspeech.BmLaunchActivity",
            ".BmLaunchActivity",
        }:
            app.remove(node)
    launch = ET.SubElement(app, "activity")
    launch.set(A + "name", "org.bmtts.bmtextspeech.BmLaunchActivity")
    launch.set(A + "exported", "true")
    launch.set(A + "launchMode", "singleTask")
    launch.set(A + "theme", "@android:style/Theme.Material.Light.NoActionBar")
    # The app must remain in Android's recent-apps list so switching to a
    # browser/file picker does not look like the session was discarded.
    launch.set(A + "excludeFromRecents", "false")
    launch.set(A + "screenOrientation", "portrait")
    launch.set(A + "resizeableActivity", "false")
    launch.set(
        A + "configChanges",
        "mcc|mnc|locale|touchscreen|keyboard|keyboardHidden|navigation|screenLayout|fontScale|uiMode|orientation|screenSize|smallestScreenSize|density",
    )
    intent_filter = ET.SubElement(launch, "intent-filter")
    action = ET.SubElement(intent_filter, "action")
    action.set(A + "name", "android.intent.action.MAIN")
    category = ET.SubElement(intent_filter, "category")
    category.set(A + "name", "android.intent.category.LAUNCHER")

    for node in list(app.findall("activity")):
        if android_name(node) in {
            "org.bmtts.bmtextspeech.BmSherpaSelfTestActivity",
            ".BmSherpaSelfTestActivity",
        }:
            app.remove(node)
    if test_ads:
        self_test = ET.SubElement(app, "activity")
        self_test.set(A + "name", "org.bmtts.bmtextspeech.BmSherpaSelfTestActivity")
        self_test.set(A + "exported", "true")
        self_test.set(A + "theme", "@android:style/Theme.Material.Light.NoActionBar")
        self_test.set(A + "screenOrientation", "portrait")
        self_test.set(A + "resizeableActivity", "false")

    def metadata(key: str, value: str) -> None:
        for node in list(app.findall("meta-data")):
            if node.get(A + "name") == key:
                app.remove(node)
        node = ET.SubElement(app, "meta-data")
        node.set(A + "name", key)
        node.set(A + "value", value)

    metadata("com.google.android.gms.ads.APPLICATION_ID", TEST_APP_ID if test_ads else LIVE_APP_ID)
    metadata("BM_APP_OPEN_UNIT_ID", LIVE_APP_OPEN_ID)
    metadata("BM_USE_TEST_ADS", "true" if test_ads else "false")
    tree.write(path, encoding="utf-8", xml_declaration=True)

    # Recent Android Gradle Plugin versions take these two values from
    # defaultConfig and overwrite the same attributes in AndroidManifest.xml.
    # Keep both sources synchronized so an incremental/cached build cannot
    # silently publish an old version code.
    gradle_file = path.parents[2] / "build.gradle"
    if gradle_file.exists():
        gradle_text = gradle_file.read_text(encoding="utf-8")
        gradle_text, code_count = re.subn(
            r"(?m)^(\s*versionCode\s+)\d+\s*$",
            r"\g<1>102640934",
            gradle_text,
            count=1,
        )
        gradle_text, name_count = re.subn(
            r"(?m)^(\s*versionName\s+)[\"'][^\"']+[\"']\s*$",
            r"\g<1>'5.6.2'",
            gradle_text,
            count=1,
        )
        if code_count != 1 or name_count != 1:
            raise RuntimeError(f"Gradle version fields missing: {gradle_file}")
        gradle_file.write_text(gradle_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("test", "production"))
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        if path.exists():
            patch_manifest(path, test_ads=args.mode == "test")
            print(f"MANIFEST_{args.mode.upper()}_OK:{path}")


if __name__ == "__main__":
    main()
