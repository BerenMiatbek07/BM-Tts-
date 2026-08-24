import json

from edge_service import _speech_config, _ssml_message


def test_speech_config_contains_complete_valid_json():
    request = _speech_config()
    _headers, payload = request.split("\r\n\r\n", 1)
    parsed = json.loads(payload)

    assert (
        parsed["context"]["synthesis"]["audio"]["outputFormat"]
        == "audio-24khz-48kbitrate-mono-mp3"
    )


def test_edge_short_voice_id_is_expanded_for_current_protocol():
    request = _ssml_message(
        "Сәлем!",
        "kk-KZ-DauletNeural",
        0,
        0,
        0,
    )

    assert "Microsoft Server Speech Text to Speech Voice (kk-KZ, DauletNeural)" in request
    assert "<voice name='kk-KZ-DauletNeural'>" not in request


def test_multiregion_voice_id_is_expanded_without_losing_suffix():
    request = _ssml_message(
        "Hello",
        "en-US-EmmaMultilingualNeural",
        10,
        -5,
        20,
    )

    assert "Microsoft Server Speech Text to Speech Voice (en-US, EmmaMultilingualNeural)" in request
    assert "rate='+10%'" in request
    assert "pitch='-5Hz'" in request
    assert "volume='+20%'" in request
