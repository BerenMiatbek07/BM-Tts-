from __future__ import annotations

import math
import random
import wave
from array import array

import pytest

from voice_clone_security import (
    CHALLENGE_SECONDS,
    LEGAL_ATTESTATION_CLAIMS,
    LEGAL_ATTESTATION_VERSION,
    VerificationReason,
    VerificationState,
    VoiceConsentVerifier,
    cleanup_legacy_verification_data,
    generate_challenge,
    inspect_reference_wave,
    legal_attestation_sha256,
    normalize_transcript,
    validate_reference,
)


def _write_test_wave(path, sample_value) -> None:
    samples = array("h", (int(sample_value(index)) for index in range(16_000)))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(samples.tobytes())


def test_legacy_verification_cleanup_is_one_time_and_preserves_clone_engine(tmp_path):
    retired = tmp_path / "voice_clone_verification"
    retired.mkdir()
    (retired / "speaker.onnx").write_bytes(b"old-model")
    engine = tmp_path / "voice_clone_engine"
    engine.mkdir()
    profile = engine / "verified_profile.json"
    profile.write_text('{"voice":"mine"}', encoding="utf-8")

    assert cleanup_legacy_verification_data(tmp_path) is True
    assert not retired.exists()
    assert profile.read_text(encoding="utf-8") == '{"voice":"mine"}'
    assert cleanup_legacy_verification_data(tmp_path) is False
    assert profile.exists()


def test_reference_duration_and_source_are_enforced():
    assert validate_reference(source="microphone", duration_seconds=5)[1] is VerificationReason.OK
    assert validate_reference(source="microphone", duration_seconds=10)[1] is VerificationReason.OK
    assert validate_reference(source="microphone", duration_seconds=4.99)[1] is VerificationReason.REFERENCE_TOO_SHORT
    assert validate_reference(source="microphone", duration_seconds=10.01)[1] is VerificationReason.REFERENCE_TOO_LONG
    assert validate_reference(source="file", duration_seconds=8)[1] is VerificationReason.INVALID_REFERENCE_SOURCE
    assert validate_reference(source="gallery", duration_seconds=10)[1] is VerificationReason.INVALID_REFERENCE_SOURCE


@pytest.mark.parametrize(
    ("language", "expected_language"),
    [("kk", "kk"), ("kk-KZ", "kk"), ("en", "en"), ("ru", "ru")],
)
def test_challenge_is_short_localized_unique_and_10_seconds(language, expected_language):
    first = generate_challenge(language, now=100, rng=random.Random(1))
    second = generate_challenge(language, now=100, rng=random.Random(2))
    assert first.language == expected_language
    assert first.phrase != second.phrase
    assert len(normalize_transcript(first.phrase, first.language).split()) <= 14
    assert len(first.nonce_digits) == 4
    assert len(set(first.nonce_digits)) == 4
    assert first.expires_at - first.issued_at == CHALLENGE_SECONDS
    public = first.public_dict()
    assert public["verification_playback_allowed"] is False
    assert "audio" not in public
    assert "path" not in public


def _ready(clock):
    verifier = VoiceConsentVerifier(clock=clock)
    verifier.grant_consent(True)
    return verifier


def test_clone_unlocks_after_fresh_microphone_reference_and_attestation():
    now = [100.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("kk")
    now[0] = 108
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=101,
        capture_finished_at=108,
        live_duration_seconds=7,
        reference_sha256="abc",
    )
    assert result.passed
    assert verifier.clone_unlocked
    receipt = verifier.consent_receipt()
    assert "phrase" not in receipt
    assert "audio" not in receipt
    assert receipt["legal_attestation_version"] == LEGAL_ATTESTATION_VERSION
    assert receipt["legal_attestation_sha256"] == legal_attestation_sha256()
    assert receipt["legal_attestation_accepted_at"] == 100.0
    assert receipt["live_capture_source"] == "microphone"
    assert receipt["verification_playback_allowed"] is False
    assert receipt["verification_mode"] == "fresh_microphone_legal_attestation_v1"
    assert receipt["automatic_speaker_match"] is False
    assert receipt["automatic_prompt_recognition"] is False
    assert receipt["reference_duration_seconds"] == 7
    assert "speaker_score" not in receipt
    assert "phrase_score" not in receipt
    assert "accept_legal_responsibility_for_false_attestation_or_unauthorized_use" in LEGAL_ATTESTATION_CLAIMS


def test_revoking_legal_attestation_locks_cloning_and_clears_timestamp():
    now = [125.0]
    verifier = _ready(lambda: now[0])
    assert verifier.attestation_accepted_at == 125.0
    verifier.grant_consent(False)
    assert not verifier.consent_granted
    assert verifier.attestation_accepted_at is None
    assert verifier.state is VerificationState.REFERENCE_REQUIRED
    with pytest.raises(PermissionError):
        verifier.issue_challenge("kk")


def test_file_cannot_be_used_for_liveness_and_attempt_is_single_use():
    now = [200.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("en")
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="file",
        capture_started_at=201,
        capture_finished_at=208,
        live_duration_seconds=7,
        reference_sha256="bad",
    )
    assert result.reason is VerificationReason.LIVE_MIC_REQUIRED
    assert not verifier.clone_unlocked
    second = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=201,
        capture_finished_at=208,
        live_duration_seconds=7,
        reference_sha256="abc",
    )
    assert second.reason is VerificationReason.CHALLENGE_ALREADY_USED


def test_cancelled_challenge_cannot_unlock_cloning():
    now = [250.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("kk")
    verifier.cancel_challenge()
    assert verifier.state is VerificationState.READY
    assert not verifier.clone_unlocked
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=251,
        capture_finished_at=258,
        live_duration_seconds=7,
        reference_sha256="abc",
    )
    assert result.reason is VerificationReason.CHALLENGE_NOT_FOUND


def test_expired_challenge_is_rejected():
    now = [300.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("ru")
    now[0] = 312
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=301,
        capture_finished_at=312,
        live_duration_seconds=10,
        reference_sha256="abc",
    )
    assert result.reason is VerificationReason.CHALLENGE_EXPIRED
    assert result.state is VerificationState.EXPIRED


@pytest.mark.parametrize("seconds", [4.99, 10.01])
def test_fresh_reference_must_be_between_five_and_ten_seconds(seconds):
    now = [400.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("kk")
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=400,
        capture_finished_at=400 + min(seconds, 10.0),
        live_duration_seconds=seconds,
        reference_sha256="abc",
    )
    assert not result.passed
    assert result.reason in {
        VerificationReason.REFERENCE_TOO_SHORT,
        VerificationReason.REFERENCE_TOO_LONG,
    }


def test_lightweight_wave_quality_rejects_silence_and_clipping(tmp_path):
    silence = tmp_path / "silence.wav"
    clipped = tmp_path / "clipped.wav"
    speech_like = tmp_path / "speech.wav"
    _write_test_wave(silence, lambda _index: 0)
    _write_test_wave(clipped, lambda index: 32767 if index % 2 else -32767)
    _write_test_wave(
        speech_like,
        lambda index: 5000 * math.sin((2 * math.pi * 220 * index) / 16_000),
    )

    assert inspect_reference_wave(silence).reason is VerificationReason.LIVE_AUDIO_SILENT
    assert inspect_reference_wave(clipped).reason is VerificationReason.LIVE_AUDIO_CLIPPED
    assert inspect_reference_wave(speech_like).accepted


def test_audio_quality_failure_blocks_fresh_reference():
    now = [500.0]
    verifier = _ready(lambda: now[0])
    challenge = verifier.issue_challenge("en")
    result = verifier.verify_fresh_reference(
        challenge_id=challenge.challenge_id,
        capture_source="microphone",
        capture_started_at=501,
        capture_finished_at=507,
        live_duration_seconds=6,
        reference_sha256="silent",
        audio_quality_reason=VerificationReason.LIVE_AUDIO_SILENT,
    )
    assert not result.passed
    assert result.reason is VerificationReason.LIVE_AUDIO_SILENT
