from pathlib import Path
import wave

from timecode_generation import (
    generate_timecoded_wav,
    parse_timecode_text,
    render_timecoded_wav,
)


def _write_wav(path: Path, duration_ms: int, sample_rate: int = 24000) -> None:
    frames = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x01\x00" * frames)


def test_parse_srt_and_inline_timecodes() -> None:
    cues = parse_timecode_text(
        "1\n00:00:01,000 --> 00:00:02,500\nСәлем\n\n"
        "[00:00:03.000 --> 00:00:04.000] Қалайсың?"
    )
    assert len(cues) == 2
    assert cues[0].start_ms == 1000
    assert cues[0].end_ms == 2500
    assert cues[0].text == "Сәлем"
    assert cues[1].start_ms == 3000
    assert cues[1].text == "Қалайсың?"


def test_render_timecoded_wav_keeps_timeline(tmp_path: Path) -> None:
    script = (
        "00:00:01.000 --> 00:00:02.000 First\n"
        "00:00:03.000 --> 00:00:04.000 Second"
    )
    cues = parse_timecode_text(script)
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    output = tmp_path / "out.wav"
    _write_wav(first, 500)
    _write_wav(second, 500)
    render_timecoded_wav(cues, [first, second], output)
    with wave.open(str(output), "rb") as source:
        duration_ms = int(source.getnframes() / source.getframerate() * 1000)
    assert 3990 <= duration_ms <= 4010


def test_generate_timecoded_wav_accepts_parallel_workers(tmp_path: Path) -> None:
    script = (
        "00:00:00.000 --> 00:00:01.000 First\n"
        "00:00:01.000 --> 00:00:02.000 Second"
    )
    output = tmp_path / "parallel.wav"

    def synthesize(_text: str, path: Path) -> None:
        _write_wav(path, 250)

    generate_timecoded_wav(
        script=script,
        synthesize_wav=synthesize,
        output_path=output,
        session_dir=tmp_path / "session",
        source="timecode",
        source_file_name="demo.srt",
        voice="edge:demo",
        language="en",
        rate=0,
        pitch=0,
        volume=0,
        base_engine="edge",
        workers=2,
    )
    with wave.open(str(output), "rb") as source:
        duration_ms = int(source.getnframes() / source.getframerate() * 1000)
    assert 1990 <= duration_ms <= 2010


def test_render_timecoded_wav_clips_long_cue_to_end_time(tmp_path: Path) -> None:
    script = (
        "00:00:00.000 --> 00:00:01.000 First\n"
        "00:00:01.000 --> 00:00:02.000 Second"
    )
    cues = parse_timecode_text(script)
    first = tmp_path / "first_long.wav"
    second = tmp_path / "second.wav"
    output = tmp_path / "clipped.wav"
    _write_wav(first, 1800)
    _write_wav(second, 500)
    render_timecoded_wav(cues, [first, second], output)
    with wave.open(str(output), "rb") as source:
        duration_ms = int(source.getnframes() / source.getframerate() * 1000)
    assert 1990 <= duration_ms <= 2010


def test_generate_timecoded_wav_accepts_twelve_parallel_workers(tmp_path: Path) -> None:
    lines = [
        f"00:00:{index:02d}.000 --> 00:00:{index + 1:02d}.000 Cue {index}"
        for index in range(12)
    ]
    output = tmp_path / "twelve.wav"

    def synthesize(_text: str, path: Path) -> None:
        _write_wav(path, 200)

    generate_timecoded_wav(
        script="\n".join(lines),
        synthesize_wav=synthesize,
        output_path=output,
        session_dir=tmp_path / "session12",
        source="timecode",
        source_file_name="demo.srt",
        voice="edge:demo",
        language="en",
        rate=0,
        pitch=0,
        volume=0,
        base_engine="edge",
        workers=12,
    )
    with wave.open(str(output), "rb") as source:
        duration_ms = int(source.getnframes() / source.getframerate() * 1000)
    assert 11990 <= duration_ms <= 12010
