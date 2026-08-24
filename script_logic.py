"""Text-source rules shared by the UI and tests."""

from __future__ import annotations

MANUAL_TTS_LIMIT = 1_000_000
FILE_TEXT_LIMIT = 1_000_000
FILE_SOURCES = {"file", "excel", "clipboard"}


def text_for_tts(full_text: str, source: str) -> str:
    if len(full_text) > FILE_TEXT_LIMIT:
        raise ValueError("Text exceeds 1,000,000 characters.")
    return full_text


def spoken_character_count(full_text: str, source: str) -> int:
    return len(text_for_tts(full_text, source))


def is_manual_over_limit(full_text: str, source: str) -> bool:
    return len(full_text) > MANUAL_TTS_LIMIT
