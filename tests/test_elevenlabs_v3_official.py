from pathlib import Path
import json

import pytest

from elevenlabs_service import (
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_VOICES,
    ElevenLabsTtsError,
    ElevenLabsV3TTS,
    split_elevenlabs_text,
)
from elevenlabs_generation import generate_elevenlabs_mp3


class FakeResponse:
    def __init__(self, status_code=200, content=b"ID3" + b"x" * 40, headers=None, payload=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"content-type": "audio/mpeg"}
        self._payload = payload
        self.text = "" if payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_split_elevenlabs_text_preserves_long_text():
    text = ("Сәлем әлем. " * 900).strip()
    chunks = split_elevenlabs_text(text, max_chars=400)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 400 for chunk in chunks)
    assert " ".join(chunks).replace("  ", " ") == text.replace("  ", " ")


def test_official_client_sends_v3_and_kazakh_language():
    fake = FakeSession()
    client = ElevenLabsV3TTS("secret-key", session=fake)
    voice_id = ELEVENLABS_VOICES[0][1]
    audio = client.synthesize_chunk("Сәлем!", voice_id=voice_id, language="kk")
    assert audio.startswith(b"ID3")
    url, kwargs = fake.calls[0]
    assert voice_id in url
    assert kwargs["headers"]["xi-api-key"] == "secret-key"
    body = json.loads(kwargs["data"].decode("utf-8"))
    assert body["model_id"] == ELEVENLABS_MODEL_ID == "eleven_v3"
    assert body["language_code"] == "kk"


def test_official_client_rejects_missing_key():
    with pytest.raises(ElevenLabsTtsError):
        ElevenLabsV3TTS("").synthesize_chunk("Сәлем", voice_id=ELEVENLABS_VOICES[0][1], language="kk")


def test_official_client_explains_access_error():
    fake = FakeSession(FakeResponse(status_code=403, content=b"", headers={"content-type": "application/json"}, payload={"detail": "model_access_denied"}))
    with pytest.raises(ElevenLabsTtsError) as exc:
        ElevenLabsV3TTS("bad", session=fake).synthesize_chunk("Сәлем", voice_id=ELEVENLABS_VOICES[0][1], language="kk")
    assert "API key" in str(exc.value)


def test_generation_creates_resumable_mp3(tmp_path: Path):
    class Client:
        def synthesize_chunk(self, text, *, voice_id, language):
            assert language == "kk"
            assert voice_id == ELEVENLABS_VOICES[0][1]
            return b"ID3" + text.encode("utf-8") + b"x" * 20

    output = tmp_path / "out.mp3"
    session_dir = tmp_path / "session"
    generate_elevenlabs_mp3(
        client=Client(),
        text="Сәлем әлем. Бұл Eleven v3 тесті.",
        voice_key=f"elevenv3:{ELEVENLABS_VOICES[0][1]}",
        language="kk",
        output_path=output,
        session_dir=session_dir,
        source="manual",
        source_file_name="",
    )
    assert output.exists()
    assert output.read_bytes().startswith(b"ID3")
    state = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    assert state["status"] == "complete"
    assert state["engine"] == "elevenv3"


def test_main_integrates_official_eleven_v3_without_bypass_code():
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert 'startswith("elevenv3:")' in source
    assert "ElevenLabsV3TTS" in source
    assert "generate_elevenlabs_mp3" in source
    assert "Firebase login" not in source
    assert "Playwright" not in source
    assert "browser headers" not in source
