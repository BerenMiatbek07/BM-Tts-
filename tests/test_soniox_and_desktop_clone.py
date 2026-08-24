from pathlib import Path
import sys
import types

if "kivy" not in sys.modules:
    kivy = types.ModuleType("kivy")
    kivy_utils = types.ModuleType("kivy.utils")
    kivy_utils.platform = "linux"
    kivy.utils = kivy_utils
    sys.modules["kivy"] = kivy
    sys.modules["kivy.utils"] = kivy_utils

from soniox_service import SONIOX_VOICE_NAMES, split_soniox_text
from desktop_omnivoice import DesktopOmniVoiceEngine, DesktopOmniVoiceModelManager


def test_soniox_catalog_and_chunking_are_kazakh_ready():
    assert "Emma" in SONIOX_VOICE_NAMES
    assert "Daniel" in SONIOX_VOICE_NAMES
    text = " ".join(["Қазақша мәтінді жақсы дыбыстау үшін осы сөйлем қайталанады."] * 25)
    chunks = split_soniox_text(text)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 235 for chunk in chunks)
    assert "Қазақша" in " ".join(chunks)


def test_desktop_clone_profile_accepts_kazakh(tmp_path: Path):
    wave = tmp_path / "voice.wav"
    wave.write_bytes(b"RIFF" + b"0" * 100)
    manager = DesktopOmniVoiceModelManager(tmp_path)
    profile = manager.save_verified_profile(
        wave,
        reference_text="Көк дәптерді, төрт алма. Код: бір екі үш төрт.",
        language="kk",
        consent_receipt={"consent": True},
    )
    assert profile["language"] == "kk"
    assert manager.load_profile()["language"] == "kk"


def test_desktop_clone_passes_kazakh_language_to_omnivoice(tmp_path: Path):
    import numpy as np
    calls = {}

    class FakeModel:
        def generate(self, **kwargs):
            calls.update(kwargs)
            return [np.linspace(-0.15, 0.15, 2400, dtype=np.float32)]

    engine = DesktopOmniVoiceEngine.__new__(DesktopOmniVoiceEngine)
    engine.model = FakeModel()
    engine._voice_prompt = lambda _wave, _text: "fake-prompt"
    ref = tmp_path / "reference.wav"
    ref.write_bytes(b"RIFF" + b"0" * 100)
    out = tmp_path / "clone.wav"
    engine.synthesize(
        text="Сәлем! Бұл қазақша дауыс клонының тексеруі.",
        reference_wave=ref,
        reference_text="Көк дәптерді, төрт алма.",
        language="kk",
        rate=0,
        volume=0,
        output_path=out,
    )
    assert calls["language"] == "kk"
    assert calls["text"].startswith("Сәлем")
    assert out.is_file() and out.stat().st_size > 44


def test_russian_clone_challenge_keeps_russian_language():
    from voice_clone_security import generate_challenge
    challenge = generate_challenge("ru")
    assert challenge.language == "ru"
    russian_markers = {"Сегодня", "Проверочное", "число", "тетрадь", "книгу", "ручку", "папку"}
    assert any(marker in challenge.phrase for marker in russian_markers)


def test_soniox_generation_forces_single_worker(tmp_path: Path, monkeypatch):
    import soniox_generation as sg
    calls = []

    class FakeClient:
        def synthesize_chunk(self, text, *, voice, language):
            calls.append((text, voice, language))
            return b"ID3" + b"0" * 64

    monkeypatch.setattr(sg, "merge_mp3_chunks", lambda paths, output: output.write_bytes(b"ID3" + b"1" * 64))
    output = tmp_path / "out.mp3"
    sg.generate_soniox_mp3(
        client=FakeClient(),
        text=" ".join(["Қазақша сөйлем." for _ in range(80)]),
        voice_key="soniox:Emma",
        language="kk",
        output_path=output,
        session_dir=tmp_path / "session",
        source="text",
        source_file_name="",
        workers=6,
    )
    session = __import__("json").loads((tmp_path / "session" / "session.json").read_text(encoding="utf-8"))
    assert session["workers"] == 1
    assert output.is_file()
    assert calls and all(item[2] == "kk" for item in calls)
