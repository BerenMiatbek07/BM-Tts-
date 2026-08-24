from __future__ import annotations

import wave
from pathlib import Path

from clone_generation import split_clone_text
from voice_clone_engine import REQUIRED_FILES, VOCODER_FILE, VOCODER_SIZE, VoiceCloneModelManager


def _wave(path: Path, seconds: float = 2.0) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\x00\x00" * int(16_000 * seconds))


def test_verified_profile_is_copied_and_tamper_checked(tmp_path: Path) -> None:
    manager = VoiceCloneModelManager(tmp_path)
    source = tmp_path / "live.wav"
    _wave(source)
    profile = manager.save_verified_profile(source, reference_text="This is the exact live phrase.", language="en", consent_receipt={"consent_version": "test"})
    assert profile["storage"] == "app_private"
    assert manager.has_profile()
    assert manager.profile_wave.read_bytes() == source.read_bytes()
    with manager.profile_wave.open("ab") as output:
        output.write(b"tampered")
    assert not manager.has_profile()


def test_runtime_paths_require_complete_model_and_profile(tmp_path: Path) -> None:
    manager = VoiceCloneModelManager(tmp_path)
    manager.model_dir.mkdir(parents=True)
    for name in REQUIRED_FILES:
        (manager.model_dir / name).write_bytes(b"model")
    (manager.model_dir / "espeak-ng-data").mkdir()
    (manager.model_dir / "espeak-ng-data" / "phontab").write_bytes(b"data")
    with (manager.model_dir / VOCODER_FILE).open("wb") as output:
        output.truncate(VOCODER_SIZE)
    source = tmp_path / "live.wav"
    _wave(source)
    manager.save_verified_profile(source, reference_text="This is the exact live phrase.", language="en", consent_receipt={})
    paths = manager.runtime_paths()
    assert paths["reference_text"] == "This is the exact live phrase."
    assert Path(paths["model_dir"]) == manager.model_dir


def test_unsupported_legacy_kazakh_profile_is_not_reused(tmp_path: Path) -> None:
    manager = VoiceCloneModelManager(tmp_path)
    source = tmp_path / "live.wav"
    _wave(source)
    manager.save_verified_profile(source, reference_text="Көк дәптер және төрт сегіз екі жеті.", language="kk", consent_receipt={"consent_version": "legacy-test"})
    assert manager.load_profile() is None
    assert not manager.has_profile()


def test_clone_text_split_preserves_all_words() -> None:
    text = " ".join(f"word{index}" for index in range(300))
    chunks = split_clone_text(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 420 for chunk in chunks)
    assert " ".join(chunks) == text
