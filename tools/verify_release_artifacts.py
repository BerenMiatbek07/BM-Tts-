#!/usr/bin/env python3
"""Verify BM Text to Voice APK/AAB runtime contents and 16 KB ELF alignment."""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


MODULES = (
    "main",
    "android_activity",
    "generation",
    "edge_service",
    "admob_service",
    "app_log",
    "audio_player",
    "audio_transcode",
    "desktop_io",
    "storage",
    "script_logic",
    "spreadsheet_io",
    "text_io",
    "offline_voice_catalog",
    "offline_voice_manager",
    "sherpa_generation",
    "sherpa_probe",
    "timecode_generation",
    "voice_clone_security",
    "voice_clone_engine",
    "clone_generation",
    "voice_clone_billing",
)
REQUIRED_NATIVE = {
    "libonnxruntime.so",
    "libsherpa-onnx-c-api.so",
    "libsherpa-onnx-cxx-api.so",
    "libsherpa-onnx-jni.so",
}
DEX_SYMBOLS = (
    b"OfflineTtsConfig",
    b"BmLaunchActivity",
    b"BmPythonActivity",
    b"BmAdMobBridge",
    b"BmArchiveBridge",
    b"BmSherpaTtsBridge",
    b"BmVoiceConsentBridge",
    b"BmBillingBridge",
    b"startVoiceConsentRecording",
    b"extractTarBz2Selected",
    b"synthesizeZipVoiceToWave",
    b"transcodeMp3ToWav",
    b"recordCompletedGeneration",
    b"voice_clone_lifetime",
)
RETIRED_MODULES = ("voice_consent_models.py",)
RETIRED_DEX_SYMBOLS = (b"evaluateVoiceConsent", b"prepareVoiceReference")


def elf_alignment(readelf: Path, data: bytes) -> int:
    with tempfile.NamedTemporaryFile(suffix=".so") as temp:
        temp.write(data)
        temp.flush()
        output = subprocess.check_output(
            [str(readelf), "-lW", temp.name], text=True, errors="replace"
        )
    alignments = [
        int(line.split()[-1], 16)
        for line in output.splitlines()
        if re.match(r"\s*LOAD\s", line)
    ]
    return min(alignments) if alignments else 0


def contains_manifest_text(data: bytes, text: str) -> bool:
    return text.encode("utf-8") in data or text.encode("utf-16le") in data


def verify(path: Path, readelf: Path, *, aab: bool) -> None:
    native_prefix = "base/lib/arm64-v8a/" if aab else "lib/arm64-v8a/"
    private_name = "base/assets/private.tar" if aab else "assets/private.tar"
    manifest_name = "base/manifest/AndroidManifest.xml" if aab else "AndroidManifest.xml"
    top_count = 0
    nested_count = 0
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        native_names = [
            name for name in names if name.startswith(native_prefix) and name.endswith(".so")
        ]
        present = {Path(name).name for name in native_names}
        missing = REQUIRED_NATIVE - present
        if missing:
            raise RuntimeError(f"{path.name}: missing native libraries: {sorted(missing)}")

        pybundle_name = native_prefix + "libpybundle.so"
        pybundle = archive.read(pybundle_name)
        for name in native_names:
            if name == pybundle_name:
                continue
            data = archive.read(name)
            if not data.startswith(b"\x7fELF"):
                raise RuntimeError(f"{path.name}: non-ELF native file: {name}")
            alignment = elf_alignment(readelf, data)
            if alignment < 0x4000:
                raise RuntimeError(f"{path.name}: {name} alignment={alignment:#x}")
            top_count += 1

        private_data = archive.read(private_name)
        manifest_data = archive.read(manifest_name)
        if not contains_manifest_text(manifest_data, "android.permission.RECORD_AUDIO"):
            raise RuntimeError(f"{path.name}: RECORD_AUDIO permission is missing")
        if not contains_manifest_text(manifest_data, "com.android.vending.BILLING"):
            raise RuntimeError(f"{path.name}: Google Play Billing permission is missing")
        if aab:
            live_id = "ca-app-pub-2408723079137167~4524564324"
            test_id = "ca-app-pub-3940256099942544~3347511713"
            if not contains_manifest_text(manifest_data, live_id):
                raise RuntimeError("AAB production AdMob App ID is missing")
            if contains_manifest_text(manifest_data, test_id):
                raise RuntimeError("AAB contains the Google test AdMob App ID")
            if contains_manifest_text(manifest_data, "BmSherpaSelfTestActivity"):
                raise RuntimeError("AAB exposes the ADB-only self-test activity")
        else:
            dex_data = b"".join(
                archive.read(name)
                for name in names
                if re.fullmatch(r"classes(?:\d+)?\.dex", Path(name).name)
            )
            for symbol in DEX_SYMBOLS:
                if symbol not in dex_data:
                    raise RuntimeError(f"APK DEX symbol missing: {symbol.decode()}")
            for symbol in RETIRED_DEX_SYMBOLS:
                if symbol in dex_data:
                    raise RuntimeError(f"APK DEX contains retired symbol: {symbol.decode()}")

    with tarfile.open(fileobj=io.BytesIO(private_data), mode="r:gz") as private_tar:
        members = {
            member.name.removeprefix("./"): member
            for member in private_tar.getmembers()
            if member.isfile()
        }
        for module in MODULES:
            if f"{module}.py" not in members:
                raise RuntimeError(f"{path.name}: private module missing: {module}.py")
        for retired in RETIRED_MODULES:
            if retired in members:
                raise RuntimeError(f"{path.name}: retired private module present: {retired}")
        main_file = private_tar.extractfile(members["main.py"])
        catalog_file = private_tar.extractfile(members["offline_voice_catalog.py"])
        if main_file is None or b'__version__ = "5.6.2"' not in main_file.read():
            raise RuntimeError(f"{path.name}: v5.6.2 main runtime missing")
        if catalog_file is None:
            raise RuntimeError(f"{path.name}: voice catalog unreadable")
        catalog = catalog_file.read()
        if b"is_runtime_compatible_model" not in catalog or b"CATALOG_SCHEMA = 5" not in catalog:
            raise RuntimeError(f"{path.name}: FP16 compatibility filter missing")

    with tarfile.open(fileobj=io.BytesIO(pybundle), mode="r:gz") as py_tar:
        for member in py_tar.getmembers():
            if not member.isfile() or not member.name.endswith(".so"):
                continue
            extracted = py_tar.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            if not data.startswith(b"\x7fELF"):
                continue
            alignment = elf_alignment(readelf, data)
            if alignment < 0x4000:
                raise RuntimeError(
                    f"{path.name}: {member.name} alignment={alignment:#x}"
                )
            nested_count += 1

    if top_count == 0 or nested_count == 0:
        raise RuntimeError(
            f"{path.name}: incomplete ELF scan: top={top_count}, nested={nested_count}"
        )
    print(
        f"RELEASE_ARTIFACT_OK:{path.name}:top_elf={top_count}:python_elf={nested_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--aab", type=Path, required=True)
    parser.add_argument("--readelf", type=Path, required=True)
    args = parser.parse_args()
    verify(args.apk, args.readelf, aab=False)
    verify(args.aab, args.readelf, aab=True)


if __name__ == "__main__":
    main()
