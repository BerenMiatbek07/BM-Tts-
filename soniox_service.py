"""Personal-use Soniox web TTS client for BM Voice Studio on Windows.

This integration intentionally uses the public Soniox web TTS endpoint and does
not require an API key.  It is best-effort: Soniox may change or restrict the
web endpoint at any time.
"""

from __future__ import annotations

import json
import random
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote


SONIOX_VOICES = {
    "female": (
        "Emma", "Isla", "Arabella", "Freya", "Grace", "Harper", "Hazel", "Iris",
        "Lucia", "Mina", "Nora", "Piper", "Reese", "Ruby", "Sloane", "Victoria",
    ),
    "male": (
        "Daniel", "Adrian", "Arthur", "Bennett", "Cooper", "Dominic", "Elliot",
        "Emerson", "Evan", "Logan", "Mason", "Mateo", "Miles", "Nathan", "Oliver",
        "Owen", "Sebastian", "Silas", "Wesley",
    ),
}
SONIOX_VOICE_NAMES = tuple(SONIOX_VOICES["female"] + SONIOX_VOICES["male"])
SONIOX_MAX_CHARS = 235


class SonioxTtsError(RuntimeError):
    pass


def soniox_gender(voice: str) -> str:
    return "female" if voice in SONIOX_VOICES["female"] else "male"


def split_soniox_text(text: str, limit: int = SONIOX_MAX_CHARS) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    # Sentence-first chunking, then word fallback for a long sentence.
    sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+|\n+", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            if len(word) <= limit:
                current = word
                continue
            # Very long token: hard split only as a last resort.
            chunks.extend(word[i : i + limit] for i in range(0, len(word), limit))
            current = ""
        if current and len(current) >= int(limit * 0.75):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


class SonioxTTS:
    BASE_PAGE = "https://soniox.com/text-to-speech"
    TTS_ENDPOINT = "https://soniox.com/api/text-to-speech"

    def __init__(self, cookie_file: str | Path):
        self.cookie_file = Path(cookie_file)
        self._session = None
        self._using_curl_cffi = False
        self._initialized = False

    def _new_session(self):
        try:
            from curl_cffi import requests as curl_requests

            self._using_curl_cffi = True
            return curl_requests.Session(impersonate="chrome124")
        except Exception:
            import requests

            self._using_curl_cffi = False
            return requests.Session()

    @staticmethod
    def _posthog_cookie() -> str:
        now_ms = int(time.time() * 1000)
        device_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        payload = {
            "$device_id": device_id,
            "distinct_id": device_id,
            "$sesid": [now_ms, session_id, now_ms],
            "$initial_person_info": {"r": "$direct", "u": SonioxTTS.BASE_PAGE},
            "$user_state": "anonymous",
        }
        return quote(json.dumps(payload, separators=(",", ":")))

    def _load_cookies(self) -> None:
        try:
            data = json.loads(self.cookie_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                self._session.cookies.update(data)
        except Exception:
            pass

    def _save_cookies(self) -> None:
        try:
            self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
            if hasattr(self._session.cookies, "get_dict"):
                data = dict(self._session.cookies.get_dict())
            else:
                data = {cookie.name: cookie.value for cookie in self._session.cookies}
            temporary = self.cookie_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.cookie_file)
        except Exception:
            pass

    def _ensure_session(self, *, force_refresh: bool = False) -> None:
        if self._session is None or force_refresh:
            self._session = self._new_session()
            self._initialized = False
        if self._initialized and not force_refresh:
            return

        self._load_cookies()
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": "kk-KZ,kk;q=0.9,ru;q=0.8,en;q=0.7",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            self._session.get(self.BASE_PAGE, headers=headers, timeout=25)
        except Exception:
            # The endpoint itself may still work even when the landing page does not.
            pass

        now = int(time.time())
        generated = {
            "_ga": f"GA1.1.{random.randint(100000000, 999999999)}.{now}",
            "_gcl_au": f"1.1.{random.randint(100000000, 999999999)}.{now}",
            "ph_phc_E9iQnU37rxu5s5zEKzcN3DiutrWifYRwcwR4axY3SwK_posthog": self._posthog_cookie(),
        }
        try:
            self._session.cookies.update(generated)
        except Exception:
            pass
        self._save_cookies()
        self._initialized = True

    @staticmethod
    def _looks_like_mp3(payload: bytes, content_type: str = "") -> bool:
        if not payload or len(payload) < 16:
            return False
        lowered = str(content_type or "").lower()
        return (
            "audio" in lowered
            or payload.startswith(b"ID3")
            or payload[:1] == b"\xff"
        )

    def synthesize_chunk(self, text: str, *, voice: str = "Emma", language: str = "kk") -> bytes:
        piece = str(text or "").strip()
        if not piece:
            raise SonioxTtsError("Soniox: мәтін бос.")
        if len(piece) > SONIOX_MAX_CHARS:
            raise SonioxTtsError(f"Soniox chunk too long: {len(piece)} > {SONIOX_MAX_CHARS}")
        if voice not in SONIOX_VOICE_NAMES:
            voice = "Emma"
        lang = str(language or "kk").split("-", 1)[0].lower() or "kk"

        last_error: Exception | None = None
        for refresh in (False, True):
            try:
                self._ensure_session(force_refresh=refresh)
                headers = {
                    "accept": "*/*",
                    "accept-language": "kk-KZ,kk;q=0.9,ru;q=0.8,en;q=0.7",
                    "referer": self.BASE_PAGE,
                    "sec-fetch-dest": "audio",
                    "sec-fetch-mode": "no-cors",
                    "sec-fetch-site": "same-origin",
                    "user-agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                }
                response = self._session.get(
                    self.TTS_ENDPOINT,
                    params={"text": piece, "language": lang, "voice": voice},
                    headers=headers,
                    timeout=60,
                )
                payload = bytes(response.content)
                if int(response.status_code) != 200:
                    snippet = ""
                    try:
                        snippet = str(response.text)[:180]
                    except Exception:
                        pass
                    raise SonioxTtsError(
                        f"Soniox HTTP {response.status_code}" + (f": {snippet}" if snippet else "")
                    )
                if not self._looks_like_mp3(payload, response.headers.get("content-type", "")):
                    raise SonioxTtsError("Soniox жарамды MP3 аудио қайтармады.")
                self._save_cookies()
                return payload
            except Exception as error:
                last_error = error if isinstance(error, Exception) else Exception(str(error))
        if isinstance(last_error, SonioxTtsError):
            raise last_error
        raise SonioxTtsError(f"Soniox TTS қатесі: {last_error}") from last_error

    def synthesize_bytes(self, text: str, *, voice: str = "Emma", language: str = "kk") -> bytes:
        chunks = split_soniox_text(text)
        if not chunks:
            raise SonioxTtsError("Soniox: мәтін бос.")
        audio = bytearray()
        for chunk in chunks:
            audio.extend(self.synthesize_chunk(chunk, voice=voice, language=language))
        return bytes(audio)


__all__ = [
    "SONIOX_VOICES",
    "SONIOX_VOICE_NAMES",
    "SONIOX_MAX_CHARS",
    "SonioxTTS",
    "SonioxTtsError",
    "soniox_gender",
    "split_soniox_text",
]
