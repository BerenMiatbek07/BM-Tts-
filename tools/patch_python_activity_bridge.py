#!/usr/bin/env python3
"""Expose every BM Android bridge through generated PythonActivity.

PyJNIus can always resolve ``org.kivy.android.PythonActivity``.  App-specific
classes, however, may be invisible when a Python worker thread attaches to the
JVM on some Android/OEM runtimes.  Declaring the public API on the generated
base activity keeps model extraction, TTS and cloning independent of the
calling thread's class loader.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


METHODS = {
    "consumePendingActivityResult": r'''
    public String consumePendingActivityResult() {
        return org.bmtts.bmtextspeech.BmPythonActivity.consumeActivityResult();
    }
''',
    "extractTarBz2": r'''
    public void extractTarBz2(String archivePath, String destinationPath)
            throws java.io.IOException {
        org.bmtts.bmtextspeech.BmArchiveBridge.extractTarBz2(
                archivePath, destinationPath);
    }
''',
    "extractTarBz2Selected": r'''
    public void extractTarBz2Selected(
            String archivePath, String destinationPath,
            String commaSeparatedBaseNames) throws java.io.IOException {
        org.bmtts.bmtextspeech.BmArchiveBridge.extractTarBz2Selected(
                archivePath, destinationPath, commaSeparatedBaseNames);
    }
''',
    "synthesizeSherpaToWave": r'''
    public boolean synthesizeSherpaToWave(
            String modelDirectory, int numThreads, String text,
            int speakerId, float speed, String outputPath)
            throws java.io.IOException {
        return org.bmtts.bmtextspeech.BmAdMobBridge.synthesizeSherpaToWave(
                this, modelDirectory, numThreads, text, speakerId, speed,
                outputPath);
    }
''',
    "releaseSherpa": r'''
    public void releaseSherpa() {
        org.bmtts.bmtextspeech.BmAdMobBridge.releaseSherpa();
    }
''',
    "sherpaRuntimeProbe": r'''
    public String sherpaRuntimeProbe() {
        return org.bmtts.bmtextspeech.BmSherpaTtsBridge.runtimeProbe(this);
    }
''',
    "synthesizeZipVoiceToWave": r'''
    public boolean synthesizeZipVoiceToWave(
            String modelDirectory, int numThreads, String text,
            String referenceWavePath, String referenceText, float speed,
            String outputPath) throws java.io.IOException {
        return ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .synthesizeZipVoiceToWave(
                        modelDirectory, numThreads, text, referenceWavePath,
                        referenceText, speed, outputPath);
    }
''',
    "releaseZipVoice": r'''
    public void releaseZipVoice() {
        ((org.bmtts.bmtextspeech.BmPythonActivity) this).releaseZipVoice();
    }
''',
    "startVoiceConsentRecording": r'''
    public String startVoiceConsentRecording(int maxSeconds) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.startLiveRecording(
                this, maxSeconds);
    }
''',
    "startVoiceReferenceRecording": r'''
    public String startVoiceReferenceRecording(int maxSeconds) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.startReferenceRecording(
                this, maxSeconds);
    }
''',
    "stopVoiceConsentRecording": r'''
    public String stopVoiceConsentRecording() {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.stopLiveRecording();
    }
''',
    "voiceConsentRecordingStatus": r'''
    public String voiceConsentRecordingStatus() {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.liveRecordingStatus();
    }
''',
    "deleteVoiceConsentAudio": r'''
    public boolean deleteVoiceConsentAudio(String path) {
        return org.bmtts.bmtextspeech.BmVoiceConsentBridge.deleteConsentAudio(
                path, this);
    }
''',
    "transcodeMp3ToWav": r'''
    public boolean transcodeMp3ToWav(String inputPath, String outputPath)
            throws java.io.IOException {
        return ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .transcodeMp3ToWav(inputPath, outputPath);
    }
''',
    "setNativeBannersSuspended": r'''
    public void setNativeBannersSuspended(boolean suspended) {
        ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .setNativeBannersSuspended(suspended);
    }
''',
    "setModelDownloadActive": r'''
    public void setModelDownloadActive(boolean active) {
        ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .setModelDownloadActive(active);
    }
''',
    "hasMicrophonePermission": r'''
    public boolean hasMicrophonePermission() {
        return ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .hasMicrophonePermission();
    }
''',
    "requestMicrophonePermission": r'''
    public String requestMicrophonePermission() {
        return ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .requestMicrophonePermission();
    }
''',
    "microphonePermissionState": r'''
    public String microphonePermissionState() {
        return ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .microphonePermissionState();
    }
''',
    "openApplicationSettings": r'''
    public void openApplicationSettings() {
        ((org.bmtts.bmtextspeech.BmPythonActivity) this)
                .openApplicationSettings();
    }
''',
    "initializeAds": r'''
    public void initializeAds(String appOpenId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.initialize(this, appOpenId);
    }
''',
    "loadAppOpenAd": r'''
    public void loadAppOpenAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadAppOpenAd(this, unitId);
    }
''',
    "loadAndShowAppOpenAd": r'''
    public void loadAndShowAppOpenAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadAndShowAppOpenAd(this, unitId);
    }
''',
    "loadBanner": r'''
    public void loadBanner(String slot, String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadBanner(this, slot, unitId);
    }
''',
    "updateBannerFrame": r'''
    public void updateBannerFrame(
            String slot, int x, int y, int width, int height,
            int windowHeight, boolean visible) {
        org.bmtts.bmtextspeech.BmAdMobBridge.updateBannerFrame(
                this, slot, x, y, width, height, windowHeight, visible);
    }
''',
    "loadInterstitialAd": r'''
    public void loadInterstitialAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.loadInterstitialAd(this, unitId);
    }
''',
    "showInterstitialAd": r'''
    public void showInterstitialAd(String unitId) {
        org.bmtts.bmtextspeech.BmAdMobBridge.showInterstitialAd(this, unitId);
    }
''',
}

# Cached p4a distributions can retain methods injected by an older release.
# Remove the retired file-import and offline speaker/ASR entry points even
# when every current bridge method is already present.
RETIRED_METHODS = ("prepareVoiceReference", "evaluateVoiceConsent")


def has_method(source: str, name: str) -> bool:
    return bool(
        re.search(
            rf"(?m)^\s+public\s+(?:synchronized\s+)?[\w<>\[\].]+\s+{re.escape(name)}\s*\(",
            source,
        )
    )


def remove_method(source: str, name: str) -> tuple[str, bool]:
    declaration = re.compile(
        rf"(?m)^\s+public\s+(?:synchronized\s+)?[\w<>\[\].]+\s+"
        rf"{re.escape(name)}\s*\("
    )
    removed = False
    while match := declaration.search(source):
        opening = source.find("{", match.end())
        if opening < 0:
            raise RuntimeError(f"Java method body is missing: {name}")
        depth = 0
        closing = -1
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    closing = index + 1
                    break
        if closing < 0:
            raise RuntimeError(f"Java method body is incomplete: {name}")
        while closing < len(source) and source[closing] in " \t":
            closing += 1
        if closing < len(source) and source[closing] == "\n":
            closing += 1
        source = source[: match.start()] + source[closing:]
        removed = True
    return source, removed


def patch(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Generated PythonActivity is missing: {path}")
    source = path.read_text(encoding="utf-8")
    retired = []
    for name in RETIRED_METHODS:
        source, removed = remove_method(source, name)
        if removed:
            retired.append(name)
    missing = [name for name in METHODS if not has_method(source, name)]
    if missing:
        anchor = "    @Override\n    protected void onCreate(Bundle savedInstanceState)"
        if anchor not in source:
            raise SystemExit("PythonActivity onCreate anchor is missing")
        methods = "\n    // BM stable Python-facing bridge API.\n" + "".join(
            METHODS[name] for name in missing
        ) + "\n"
        source = source.replace(anchor, methods + anchor, 1)
    if missing or retired:
        path.write_text(source, encoding="utf-8")
    status = missing or ["unchanged"]
    print(
        "PYTHON_ACTIVITY_BRIDGE_API_OK:"
        + ",".join(status)
        + ":retired="
        + ",".join(retired or ["none"])
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_python_activity_bridge.py PythonActivity.java")
    patch(Path(sys.argv[1]))
