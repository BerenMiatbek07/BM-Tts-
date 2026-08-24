"""Consent and liveness rules for BM Voice Studio voice cloning.

This module deliberately contains no microphone or ML implementation. Android
captures one fresh, microphone-only reference while this module enforces the
short recording window, single-use prompt, explicit legal attestation, and an
auditable receipt. It does not claim to prove identity without a speaker model.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import shutil
import sys
import time
import unicodedata
import uuid
import wave
from array import array
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Callable


REFERENCE_MIN_SECONDS = 5.0
REFERENCE_MAX_SECONDS = 10.0
CHALLENGE_SECONDS = 10.0
DEFAULT_SPEAKER_THRESHOLD = 0.65
DEFAULT_PHRASE_THRESHOLD = 0.82
CONSENT_VERSION = "bm-voice-consent-v2"
LEGAL_ATTESTATION_VERSION = "bm-voice-rights-attestation-v1"
LEGAL_ATTESTATION_CLAIMS = (
    "voice_owner_or_authorized_by_owner",
    "consent_to_on_device_voice_cloning",
    "no_impersonation_fraud_harassment_or_other_harm",
    "accept_legal_responsibility_for_false_attestation_or_unauthorized_use",
)


class VerificationState(str, Enum):
    REFERENCE_REQUIRED = "reference_required"
    READY = "ready"
    CHALLENGE_ACTIVE = "challenge_active"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class VerificationReason(str, Enum):
    OK = "ok"
    CONSENT_REQUIRED = "consent_required"
    INVALID_REFERENCE_SOURCE = "invalid_reference_source"
    REFERENCE_TOO_SHORT = "reference_too_short"
    REFERENCE_TOO_LONG = "reference_too_long"
    CHALLENGE_NOT_FOUND = "challenge_not_found"
    CHALLENGE_EXPIRED = "challenge_expired"
    CHALLENGE_ALREADY_USED = "challenge_already_used"
    LIVE_MIC_REQUIRED = "live_mic_required"
    LIVE_AUDIO_TOO_SHORT = "live_audio_too_short"
    LIVE_AUDIO_TOO_LONG = "live_audio_too_long"
    LIVE_AUDIO_INVALID = "live_audio_invalid"
    LIVE_AUDIO_SILENT = "live_audio_silent"
    LIVE_AUDIO_CLIPPED = "live_audio_clipped"
    SPEAKER_MISMATCH = "speaker_mismatch"
    PHRASE_MISMATCH = "phrase_mismatch"
    NONCE_MISMATCH = "nonce_mismatch"


_WORDS = {
    "kk": {
        "colors": ("көк", "қызыл", "жасыл", "сары"),
        "objects": ("дәптерді", "кітапты", "телефонды", "қаламды"),
        "places": ("үстелге", "сөреге", "сөмкеге", "терезе алдына"),
        "foods": ("алма", "алмұрт", "өрік", "шие"),
        "templates": (
            "Айтыңыз: {color} {object}, {count} {food}. Код: {nonce_words}.",
            "Сөздер: {color} {object}, {count} {food}. Сан: {nonce_words}.",
        ),
        "digits": ("нөл", "бір", "екі", "үш", "төрт", "бес", "алты", "жеті", "сегіз", "тоғыз"),
    },
    "ru": {
        "colors": ("синюю", "красную", "зелёную", "жёлтую"),
        "objects": ("тетрадь", "книгу", "ручку", "папку"),
        "places": ("на стол", "на полку", "в сумку", "к окну"),
        "foods": ("яблок", "груш", "слив", "вишен"),
        "templates": (
            "Скажите: {color} {object}, {count} {food}. Код: {nonce_words}.",
            "Слова: {color} {object}, {count} {food}. Число: {nonce_words}.",
        ),
        "digits": ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"),
    },
    "en": {
        "colors": ("blue", "red", "green", "yellow"),
        "objects": ("notebook", "book", "phone", "pencil"),
        "places": ("on the table", "on the shelf", "in the bag", "near the window"),
        "foods": ("apples", "pears", "plums", "cherries"),
        "templates": (
            "Say: {color} {object}, {count} {food}. Code: {nonce_words}.",
            "Words: {color} {object}, {count} {food}. Number: {nonce_words}.",
        ),
        "digits": ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
    },
}


@dataclass(frozen=True)
class VoiceReference:
    source: str
    duration_seconds: float
    sha256: str


@dataclass
class LivenessChallenge:
    challenge_id: str
    language: str
    phrase: str
    nonce_digits: str
    issued_at: float
    expires_at: float
    used: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "challenge_id": self.challenge_id,
            "language": self.language,
            "phrase": self.phrase,
            "nonce_digits": self.nonce_digits,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "seconds": CHALLENGE_SECONDS,
            "verification_playback_allowed": False,
        }


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    state: VerificationState
    reason: VerificationReason
    speaker_score: float
    phrase_score: float
    nonce_match: bool
    verified_at: float | None


def sha256_file(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ReferenceAudioQuality:
    reason: VerificationReason
    rms: float
    peak: float
    active_fraction: float
    clipped_fraction: float

    @property
    def accepted(self) -> bool:
        return self.reason is VerificationReason.OK


def inspect_reference_wave(path: str | Path) -> ReferenceAudioQuality:
    """Reject invalid, silent, or badly clipped captures without an ML model."""

    try:
        with wave.open(str(path), "rb") as source:
            if (
                source.getnchannels() != 1
                or source.getsampwidth() != 2
                or source.getframerate() < 8_000
                or source.getnframes() <= 0
            ):
                raise ValueError("unsupported_wave")
            payload = source.readframes(source.getnframes())
        samples = array("h")
        samples.frombytes(payload)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            raise ValueError("empty_wave")
    except (OSError, EOFError, ValueError, wave.Error):
        return ReferenceAudioQuality(
            VerificationReason.LIVE_AUDIO_INVALID, 0.0, 0.0, 0.0, 0.0
        )

    count = len(samples)
    square_sum = 0
    peak_sample = 0
    active = 0
    clipped = 0
    for sample in samples:
        absolute = abs(int(sample))
        square_sum += int(sample) * int(sample)
        peak_sample = max(peak_sample, absolute)
        active += int(absolute >= 500)
        clipped += int(absolute >= 32_600)
    rms = math.sqrt(square_sum / count) / 32_768.0
    peak = peak_sample / 32_768.0
    active_fraction = active / count
    clipped_fraction = clipped / count
    reason = VerificationReason.OK
    if peak < 0.02 or rms < 0.004 or active_fraction < 0.01:
        reason = VerificationReason.LIVE_AUDIO_SILENT
    elif clipped_fraction > 0.05:
        reason = VerificationReason.LIVE_AUDIO_CLIPPED
    return ReferenceAudioQuality(
        reason,
        round(rms, 6),
        round(peak, 6),
        round(active_fraction, 6),
        round(clipped_fraction, 6),
    )


def cleanup_legacy_verification_data(user_data_dir: str | Path) -> bool:
    """Delete only the retired verification pack and leave clone data intact."""
    root = Path(user_data_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "voice_clone_verification"
    marker = root / ".voice_clone_verification_removed_v1"
    if marker.exists():
        return False

    removed = False
    resolved_root = root.resolve()
    if target.is_symlink():
        target.unlink()
        removed = True
    elif target.exists():
        resolved_target = target.resolve()
        if (
            resolved_target.parent != resolved_root
            or resolved_target.name != "voice_clone_verification"
        ):
            raise RuntimeError("unsafe legacy verification cleanup path")
        shutil.rmtree(target)
        removed = True
    marker.write_text("removed\n", encoding="utf-8")
    return removed


def validate_reference(
    *, source: str, duration_seconds: float, sha256: str = ""
) -> tuple[VoiceReference | None, VerificationReason]:
    if source != "microphone":
        return None, VerificationReason.INVALID_REFERENCE_SOURCE
    duration = float(duration_seconds)
    if duration < REFERENCE_MIN_SECONDS:
        return None, VerificationReason.REFERENCE_TOO_SHORT
    if duration > REFERENCE_MAX_SECONDS:
        return None, VerificationReason.REFERENCE_TOO_LONG
    return VoiceReference(source, duration, sha256), VerificationReason.OK


def _language(language: str) -> str:
    code = (language or "kk").lower().split("-", 1)[0]
    return code if code in {"kk", "ru", "en"} else "en"


def legal_attestation_sha256() -> str:
    canonical = json.dumps(
        {
            "claims": LEGAL_ATTESTATION_CLAIMS,
            "version": LEGAL_ATTESTATION_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_challenge(
    language: str,
    *,
    now: float | None = None,
    rng: secrets.SystemRandom | None = None,
) -> LivenessChallenge:
    code = _language(language)
    words = _WORDS[code]
    randomizer = rng or secrets.SystemRandom()
    nonce = "".join(str(value) for value in randomizer.sample(range(10), 4))
    nonce_words = " ".join(words["digits"][int(value)] for value in nonce)
    count_value = randomizer.choice((3, 4, 5, 6, 7, 8, 9))
    phrase = randomizer.choice(words["templates"]).format(
        color=randomizer.choice(words["colors"]),
        object=randomizer.choice(words["objects"]),
        place=randomizer.choice(words["places"]),
        count=words["digits"][count_value],
        food=randomizer.choice(words["foods"]),
        nonce_words=nonce_words,
    )
    issued = float(time.time() if now is None else now)
    return LivenessChallenge(
        challenge_id=uuid.uuid4().hex,
        language=code,
        phrase=phrase,
        nonce_digits=nonce,
        issued_at=issued,
        expires_at=issued + CHALLENGE_SECONDS,
    )


def normalize_transcript(text: str, language: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").lower().replace("ё", "е")
    digit_aliases: dict[str, str] = {}
    for language_words in _WORDS.values():
        for digit, word in enumerate(language_words["digits"]):
            digit_aliases[word.replace("ё", "е")] = str(digit)
    mixed_digit_suffixes = {
        f"{digit}{word.replace('ё', 'е')[1:]}": str(digit)
        for language_words in _WORDS.values()
        for digit, word in enumerate(language_words["digits"])
        if len(word) > 1
    }
    for mixed, digit in mixed_digit_suffixes.items():
        normalized = re.sub(
            rf"(?<![0-9a-zа-яәіңғүұқөһ]){re.escape(mixed)}(?![a-zа-яәіңғүұқөһ])",
            digit,
            normalized,
            flags=re.IGNORECASE,
        )
    tokens = re.findall(r"[a-zа-яәіңғүұқөһ]+|\d", normalized, flags=re.IGNORECASE)
    return " ".join(digit_aliases.get(token, token) for token in tokens)


def extract_digit_sequence(text: str, language: str) -> str:
    return "".join(token for token in normalize_transcript(text, language).split() if token.isdigit())


def phrase_similarity(expected: str, actual: str, language: str) -> float:
    left = normalize_transcript(expected, language)
    right = normalize_transcript(actual, language)
    if not left or not right:
        return 0.0
    token_score = SequenceMatcher(None, left.split(), right.split()).ratio()
    character_score = SequenceMatcher(None, left, right).ratio()
    compact_score = SequenceMatcher(None, left.replace(" ", ""), right.replace(" ", "")).ratio()
    return round(
        (token_score * 0.45) + (character_score * 0.25) + (compact_score * 0.30),
        6,
    )


class VoiceConsentVerifier:
    """Single-use challenge state machine."""

    def __init__(
        self,
        *,
        speaker_threshold: float = DEFAULT_SPEAKER_THRESHOLD,
        phrase_threshold: float = DEFAULT_PHRASE_THRESHOLD,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.speaker_threshold = float(speaker_threshold)
        self.phrase_threshold = float(phrase_threshold)
        self.clock = clock
        self.reference: VoiceReference | None = None
        self.consent_granted = False
        self.attestation_accepted_at: float | None = None
        self.challenge: LivenessChallenge | None = None
        self.verification_mode = ""
        self.state = VerificationState.REFERENCE_REQUIRED
        self.last_result: VerificationResult | None = None

    def set_reference(
        self, *, source: str, duration_seconds: float, sha256: str = ""
    ) -> VerificationReason:
        reference, reason = validate_reference(
            source=source, duration_seconds=duration_seconds, sha256=sha256
        )
        if reference is None:
            return reason
        self.reference = reference
        self.challenge = None
        self.last_result = None
        self.state = VerificationState.READY if self.consent_granted else VerificationState.REFERENCE_REQUIRED
        return VerificationReason.OK

    def grant_consent(self, granted: bool) -> None:
        self.consent_granted = bool(granted)
        if not granted:
            self.attestation_accepted_at = None
            self.challenge = None
            self.state = VerificationState.REFERENCE_REQUIRED
        else:
            self.attestation_accepted_at = float(self.clock())
            self.state = VerificationState.READY

    def issue_challenge(self, language: str) -> LivenessChallenge:
        if not self.consent_granted:
            raise PermissionError(VerificationReason.CONSENT_REQUIRED.value)
        self.challenge = generate_challenge(language, now=self.clock())
        self.state = VerificationState.CHALLENGE_ACTIVE
        return self.challenge

    def cancel_challenge(self) -> None:
        if self.challenge is not None:
            self.challenge.used = True
        self.challenge = None
        self.last_result = None
        self.state = (
            VerificationState.READY
            if self.consent_granted
            else VerificationState.REFERENCE_REQUIRED
        )

    def verify_fresh_reference(
        self,
        *,
        challenge_id: str,
        capture_source: str,
        capture_started_at: float,
        capture_finished_at: float,
        live_duration_seconds: float,
        reference_sha256: str,
        audio_quality_reason: VerificationReason = VerificationReason.OK,
    ) -> VerificationResult:
        challenge = self.challenge
        now = float(self.clock())
        reason = VerificationReason.OK
        reference: VoiceReference | None = None

        if not self.consent_granted or self.attestation_accepted_at is None:
            reason = VerificationReason.CONSENT_REQUIRED
        elif challenge is None or challenge.challenge_id != challenge_id:
            reason = VerificationReason.CHALLENGE_NOT_FOUND
        elif challenge.used:
            reason = VerificationReason.CHALLENGE_ALREADY_USED
        else:
            challenge.used = True
            if capture_source != "microphone":
                reason = VerificationReason.LIVE_MIC_REQUIRED
            elif (
                capture_started_at < challenge.issued_at - 0.25
                or capture_finished_at > challenge.expires_at + 0.75
            ):
                reason = VerificationReason.CHALLENGE_EXPIRED
            elif audio_quality_reason is not VerificationReason.OK:
                reason = audio_quality_reason
            else:
                reference, reason = validate_reference(
                    source=capture_source,
                    duration_seconds=live_duration_seconds,
                    sha256=reference_sha256,
                )

        passed = reason is VerificationReason.OK and reference is not None
        if passed:
            self.reference = reference
            self.verification_mode = "fresh_microphone_legal_attestation_v1"
        self.state = VerificationState.VERIFIED if passed else (
            VerificationState.EXPIRED
            if reason is VerificationReason.CHALLENGE_EXPIRED
            else VerificationState.REJECTED
        )
        result = VerificationResult(
            passed=passed,
            state=self.state,
            reason=reason,
            speaker_score=0.0,
            phrase_score=0.0,
            nonce_match=False,
            verified_at=now if passed else None,
        )
        self.last_result = result
        return result

    def verify(
        self,
        *,
        challenge_id: str,
        capture_source: str,
        capture_started_at: float,
        capture_finished_at: float,
        live_duration_seconds: float,
        speaker_score: float,
        transcript: str,
    ) -> VerificationResult:
        challenge = self.challenge
        now = float(self.clock())
        reason = VerificationReason.OK
        phrase_score = 0.0
        nonce_match = False

        if challenge is None or challenge.challenge_id != challenge_id:
            reason = VerificationReason.CHALLENGE_NOT_FOUND
        elif challenge.used:
            reason = VerificationReason.CHALLENGE_ALREADY_USED
        else:
            challenge.used = True
            if capture_source != "microphone":
                reason = VerificationReason.LIVE_MIC_REQUIRED
            elif capture_started_at < challenge.issued_at or capture_finished_at > challenge.expires_at + 0.25:
                reason = VerificationReason.CHALLENGE_EXPIRED
            elif live_duration_seconds < 2.0:
                reason = VerificationReason.LIVE_AUDIO_TOO_SHORT
            elif live_duration_seconds > CHALLENGE_SECONDS + 0.25:
                reason = VerificationReason.LIVE_AUDIO_TOO_LONG
            else:
                phrase_score = phrase_similarity(challenge.phrase, transcript, challenge.language)
                digits = extract_digit_sequence(transcript, challenge.language)
                nonce_match = challenge.nonce_digits in digits
                if float(speaker_score) < self.speaker_threshold:
                    reason = VerificationReason.SPEAKER_MISMATCH
                elif not nonce_match:
                    reason = VerificationReason.NONCE_MISMATCH
                elif phrase_score < self.phrase_threshold:
                    reason = VerificationReason.PHRASE_MISMATCH

        passed = reason is VerificationReason.OK
        self.state = VerificationState.VERIFIED if passed else (
            VerificationState.EXPIRED if reason is VerificationReason.CHALLENGE_EXPIRED else VerificationState.REJECTED
        )
        result = VerificationResult(
            passed=passed,
            state=self.state,
            reason=reason,
            speaker_score=round(float(speaker_score), 6),
            phrase_score=phrase_score,
            nonce_match=nonce_match,
            verified_at=now if passed else None,
        )
        self.last_result = result
        if passed:
            self.verification_mode = "speaker_and_phrase_model"
        return result

    @property
    def clone_unlocked(self) -> bool:
        return bool(self.last_result and self.last_result.passed and self.state is VerificationState.VERIFIED)

    def consent_receipt(self) -> dict[str, object]:
        if not self.clone_unlocked or self.reference is None or self.challenge is None:
            raise PermissionError("voice clone is not verified")
        return {
            "consent_version": CONSENT_VERSION,
            "legal_attestation_version": LEGAL_ATTESTATION_VERSION,
            "legal_attestation_sha256": legal_attestation_sha256(),
            "legal_attestation_accepted_at": self.attestation_accepted_at,
            "challenge_id": self.challenge.challenge_id,
            "challenge_sha256": hashlib.sha256(self.challenge.phrase.encode("utf-8")).hexdigest(),
            "reference_sha256": self.reference.sha256,
            "reference_source": self.reference.source,
            "reference_duration_seconds": self.reference.duration_seconds,
            "verification_mode": self.verification_mode,
            "automatic_speaker_match": self.verification_mode == "speaker_and_phrase_model",
            "automatic_prompt_recognition": self.verification_mode == "speaker_and_phrase_model",
            "verified_at": self.last_result.verified_at,
            "live_capture_source": "microphone",
            "verification_playback_allowed": False,
        }

    def receipt_json(self) -> str:
        return json.dumps(self.consent_receipt(), ensure_ascii=False, sort_keys=True)
