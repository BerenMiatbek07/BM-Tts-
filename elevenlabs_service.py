"""Official ElevenLabs Eleven v3 TTS client used by the Windows personal build.

This module deliberately uses ElevenLabs' documented API.  It does not copy the
browser-header/Firebase/Playwright bypass methods from the historical
``elevenlabs-alpha-v3`` repository.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

import requests

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_MODEL_ID = "eleven_v3"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_MAX_CHARS = 3_500

# Example public voice ids documented by the repository the user supplied.
# The official API accepts any voice_id the user's ElevenLabs account can use.
ELEVENLABS_VOICES: tuple[tuple[str, str], ...] = (
    ("Jessica", "cgSgspJ2msm6clMCkdW9"),
    ("Liam", "TX3LPaxmHKxFdv7VOQHJ"),
    ("Announcer", "gU0LNdkMOQCOrPrwtbee"),
    ("Sammara", "19STyYD15bswVz51nqLf"),
    ("Sergeant", "DGzg6RaUqxGRTHSBjfgF"),
    ("Spuds", "NOpBlnGInO9m6vDvFkFC"),
)
ELEVENLABS_VOICE_BY_ID = {voice_id: name for name, voice_id in ELEVENLABS_VOICES}
ELEVENLABS_VOICE_IDS = tuple(voice_id for _name, voice_id in ELEVENLABS_VOICES)


class ElevenLabsTtsError(RuntimeError):
    """Raised when the official ElevenLabs TTS endpoint rejects a request."""


@dataclass(frozen=True)
class ElevenLabsVoice:
    name: str
    voice_id: str


def split_elevenlabs_text(text: str, max_chars: int = ELEVENLABS_MAX_CHARS) -> list[str]:
    """Split long scripts on paragraph/sentence boundaries without losing text."""

    clean = str(text or "").strip()
    if not clean:
        return []
    if len(clean) <= max_chars:
        return [clean]

    # Split while preserving punctuation at the end of each sentence/paragraph.
    units = [part.strip() for part in re.split(r"(?<=[.!?…])\s+|\n{2,}", clean) if part.strip()]
    chunks: list[str] = []
    current = ""
    for unit in units:
        if len(unit) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(unit):
                end = min(len(unit), start + max_chars)
                if end < len(unit):
                    split_at = unit.rfind(" ", start, end)
                    if split_at > start + max_chars // 2:
                        end = split_at
                piece = unit[start:end].strip()
                if piece:
                    chunks.append(piece)
                start = end
            continue
        candidate = unit if not current else f"{current} {unit}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


class ElevenLabsV3TTS:
    """Small official-API client with no SDK dependency."""

    def __init__(self, api_key: str, *, timeout: float = 90.0, session: requests.Session | None = None):
        self.api_key = str(api_key or "").strip()
        self.timeout = float(timeout)
        self.session = session or requests.Session()

    def _require_key(self) -> str:
        key = self.api_key.strip()
        if not key:
            raise ElevenLabsTtsError("ElevenLabs API key енгізілмеген.")
        return key

    @staticmethod
    def _looks_like_mp3(payload: bytes, content_type: str) -> bool:
        if not payload:
            return False
        media_type = str(content_type or "").split(";", 1)[0].strip().lower()
        return media_type in {"audio/mpeg", "audio/mp3", "application/octet-stream"} or payload[:3] == b"ID3" or payload[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}

    def synthesize_chunk(self, text: str, *, voice_id: str, language: str = "kk") -> bytes:
        key = self._require_key()
        piece = str(text or "").strip()
        if not piece:
            raise ElevenLabsTtsError("ElevenLabs: мәтін бос.")
        voice_id = str(voice_id or "").strip()
        if not voice_id:
            raise ElevenLabsTtsError("ElevenLabs voice_id бос.")
        language_code = str(language or "").split("-", 1)[0].lower()
        payload = {
            "text": piece,
            "model_id": ELEVENLABS_MODEL_ID,
            "language_code": language_code or None,
        }
        headers = {
            "xi-api-key": key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "User-Agent": "BM-Voice-Studio/5.6.4-personal",
        }
        url = ELEVENLABS_API_URL.format(voice_id=voice_id)
        try:
            response = self.session.post(
                url,
                params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise ElevenLabsTtsError(f"ElevenLabs желі қатесі: {error}") from error

        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                detail = str(parsed.get("detail") or parsed.get("error") or parsed)
            except Exception:
                detail = str(getattr(response, "text", "") or "")
            detail = detail.replace("\n", " ").strip()[:300]
            if response.status_code in {401, 403}:
                prefix = "ElevenLabs рұқсат қатесі. API key және v3 қолжетімділігін тексеріңіз."
            elif response.status_code == 429:
                prefix = "ElevenLabs лимиті/квотасы уақытша бітті."
            else:
                prefix = f"ElevenLabs HTTP {response.status_code}."
            raise ElevenLabsTtsError(prefix + (f" {detail}" if detail else ""))

        audio = bytes(response.content)
        if not self._looks_like_mp3(audio, response.headers.get("content-type", "")):
            raise ElevenLabsTtsError("ElevenLabs жарамды MP3 аудио қайтармады.")
        return audio

    def synthesize_bytes(self, text: str, *, voice_id: str, language: str = "kk") -> bytes:
        chunks = split_elevenlabs_text(text)
        if not chunks:
            raise ElevenLabsTtsError("ElevenLabs: мәтін бос.")
        result = bytearray()
        for chunk in chunks:
            result.extend(self.synthesize_chunk(chunk, voice_id=voice_id, language=language))
        return bytes(result)


def voice_name(voice_id: str) -> str:
    return ELEVENLABS_VOICE_BY_ID.get(str(voice_id or ""), "ElevenLabs Voice")


__all__ = [
    "ELEVENLABS_API_URL",
    "ELEVENLABS_MODEL_ID",
    "ELEVENLABS_OUTPUT_FORMAT",
    "ELEVENLABS_MAX_CHARS",
    "ELEVENLABS_VOICES",
    "ELEVENLABS_VOICE_IDS",
    "ElevenLabsTtsError",
    "ElevenLabsV3TTS",
    "ElevenLabsVoice",
    "split_elevenlabs_text",
    "voice_name",
]
