"""Timecoded script parsing and WAV timeline rendering."""

from __future__ import annotations

import audioop
import json
import re
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from edge_service import CancelledError
from generation import MergeError, load_generation_session
from sherpa_generation import verify_wav_file


@dataclass(frozen=True)
class TimecodeCue:
    start_ms: int
    end_ms: int
    text: str


class TimecodeError(ValueError):
    pass


_TIME = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[,.]\d{1,3})?|\d+(?:[,.]\d+)?s"
_RANGE_RE = re.compile(
    rf"^\s*(?:\[|\()?({_TIME})\s*(?:-->|-|–|—)\s*({_TIME})(?:\]|\))?\s*(.*)$",
    re.IGNORECASE,
)


def _parse_time(value: str) -> int:
    value = value.strip().lower().rstrip("s").replace(",", ".")
    if ":" not in value:
        return int(round(float(value) * 1000))
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2])
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return int(round((hours * 3600 + minutes * 60 + seconds) * 1000))


def _clean_text(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines).strip()


def parse_timecode_text(script: str) -> list[TimecodeCue]:
    """Parse SRT/VTT or inline `[00:00 --> 00:05] text` scripts."""

    normalized = script.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    cues: list[TimecodeCue] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip("\ufeff ")
        if not line or line.upper().startswith(("WEBVTT", "NOTE")):
            index += 1
            continue
        if line.isdigit() and index + 1 < len(lines):
            index += 1
            line = lines[index].strip()
        match = _RANGE_RE.match(line)
        if not match:
            index += 1
            continue
        start_ms = _parse_time(match.group(1))
        end_ms = _parse_time(match.group(2))
        trailing = match.group(3).strip()
        text_lines: list[str] = [trailing] if trailing else []
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                break
            if _RANGE_RE.match(candidate):
                index -= 1
                break
            text_lines.append(candidate)
            index += 1
        text = _clean_text(text_lines)
        if text:
            cues.append(TimecodeCue(start_ms=start_ms, end_ms=end_ms, text=text))
        index += 1

    if not cues:
        raise TimecodeError("No timecode cues found.")
    cues.sort(key=lambda cue: (cue.start_ms, cue.end_ms))
    previous_end = -1
    for cue in cues:
        if cue.end_ms <= cue.start_ms:
            raise TimecodeError("A timecode cue has an invalid duration.")
        if cue.start_ms < previous_end:
            raise TimecodeError("Overlapping timecode cues are not supported.")
        previous_end = cue.end_ms
    return cues


def estimate_timecode_cues(script: str) -> int:
    try:
        return len(parse_timecode_text(script))
    except TimecodeError:
        return 0


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def _silence(frames: int, channels: int, sample_width: int) -> bytes:
    return b"\x00" * max(0, frames) * channels * sample_width


def _cue_frame_bounds(cue: TimecodeCue, sample_rate: int) -> tuple[int, int]:
    start_frame = int(cue.start_ms * sample_rate / 1000)
    end_frame = int(cue.end_ms * sample_rate / 1000)
    if end_frame <= start_frame:
        raise MergeError("Invalid timecode cue frame bounds.")
    return start_frame, end_frame


def render_timecoded_wav(
    cues: list[TimecodeCue],
    chunk_paths: list[Path],
    output_path: Path,
    *,
    volume_percent: int = 0,
) -> None:
    if len(cues) != len(chunk_paths) or not cues:
        raise MergeError("Timecode cue/audio count mismatch.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".timeline.tmp")
    temporary.unlink(missing_ok=True)
    expected = None
    current_frame = 0
    try:
        with wave.open(str(temporary), "wb") as destination:
            for cue, path in zip(cues, chunk_paths):
                if not verify_wav_file(path):
                    raise MergeError(f"Invalid WAV cue: {path.name}")
                with wave.open(str(path), "rb") as source:
                    params = (
                        source.getnchannels(),
                        source.getsampwidth(),
                        source.getframerate(),
                        source.getcomptype(),
                    )
                    if expected is None:
                        expected = params
                        destination.setnchannels(params[0])
                        destination.setsampwidth(params[1])
                        destination.setframerate(params[2])
                        destination.setcomptype(params[3], "not compressed")
                    elif params != expected:
                        raise MergeError("Timecode WAV chunks use different formats.")
                    channels, sample_width, sample_rate, _compression = params
                    start_frame, end_frame = _cue_frame_bounds(cue, sample_rate)
                    if start_frame > current_frame:
                        destination.writeframesraw(
                            _silence(start_frame - current_frame, channels, sample_width)
                        )
                        current_frame = start_frame
                    elif start_frame < current_frame:
                        raise MergeError("Timecode audio overlap detected.")
                    max_frames = max(0, end_frame - start_frame)
                    source_frames = source.getnframes()
                    frames_to_write = min(source_frames, max_frames)
                    frames = source.readframes(frames_to_write)
                    if volume_percent:
                        frames = audioop.mul(
                            frames,
                            sample_width,
                            max(0.05, 1.0 + volume_percent / 100.0),
                        )
                    destination.writeframesraw(frames)
                    current_frame += frames_to_write
            if expected is not None:
                channels, sample_width, sample_rate, _compression = expected
                final_frame = int(cues[-1].end_ms * sample_rate / 1000)
                if final_frame > current_frame:
                    destination.writeframesraw(
                        _silence(final_frame - current_frame, channels, sample_width)
                    )
        if not verify_wav_file(temporary):
            raise MergeError("Timecoded WAV validation failed.")
        temporary.replace(output_path)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        if isinstance(error, MergeError):
            raise
        raise MergeError(str(error)) from error


def retry_timecode_merge_session(session_dir: Path) -> Path:
    session = load_generation_session(session_dir)
    if not session or session.get("engine") != "timecode":
        raise MergeError("No resumable timecode merge session.")
    script = Path(session.get("script_path", "")).read_text(encoding="utf-8")
    cues = parse_timecode_text(script)
    chunks = [session_dir / name for name in session.get("temp_chunk_paths", [])]
    output = Path(str(session.get("final_output_path", "")))
    render_timecoded_wav(cues, chunks, output, volume_percent=int(session.get("volume", 0)))
    for path in chunks:
        path.unlink(missing_ok=True)
    session["status"] = "complete"
    _atomic_json(session_dir / "session.json", session)
    return output


def _wait_while_paused(pause_event, cancel_event) -> None:
    while pause_event is not None and pause_event.is_set():
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        time.sleep(0.15)
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()


def generate_timecoded_wav(
    *,
    script: str,
    synthesize_wav: Callable[[str, Path], None],
    output_path: Path,
    session_dir: Path,
    source: str,
    source_file_name: str,
    voice: str,
    language: str,
    rate: int,
    pitch: int,
    volume: int,
    base_engine: str,
    model_id: str = "",
    model_dir: str = "",
    speaker_id: int = 0,
    num_threads: int = 1,
    workers: int = 1,
    progress: Callable[[dict], None] | None = None,
    pause_event=None,
    cancel_event=None,
    resume: bool = False,
) -> Path:
    cues = parse_timecode_text(script)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"
    script_file = session_dir / "script.txt"
    if not resume:
        for old in session_dir.glob("timecode_*.wav"):
            old.unlink(missing_ok=True)
        script_file.write_text(script, encoding="utf-8")
    previous = load_generation_session(session_dir) if resume else None
    chunk_paths = [
        session_dir / f"timecode_{index:06d}.wav" for index in range(len(cues))
    ]
    completed = {
        index
        for index, path in enumerate(chunk_paths)
        if resume and verify_wav_file(path)
    }
    total_chars = sum(len(cue.text) for cue in cues)
    workers = max(1, min(12, int(workers)))
    processed_chars = sum(len(cues[index].text) for index in completed)
    session = {
        "engine": "timecode",
        "base_engine": base_engine,
        "model_id": model_id,
        "model_dir": model_dir,
        "speaker_id": int(speaker_id),
        "num_threads": int(num_threads),
        "status": "running",
        "script_path": str(script_file),
        "source": source,
        "source_file_name": source_file_name,
        "voice": voice,
        "language": language,
        "rate": int(rate),
        "pitch": int(pitch),
        "volume": int(volume),
        "pause_setting": 0,
        "workers": workers,
        "final_output_path": str(output_path),
        "temp_chunk_paths": [path.name for path in chunk_paths],
        "completed_chunks": sorted(completed),
        "processed_chars": processed_chars,
        "total_chars": total_chars,
        "total_chunks": len(cues),
        "failed_chunks": int((previous or {}).get("failed_chunks", 0)),
        "retry_status": "",
    }
    _atomic_json(session_file, session)

    started = time.monotonic()
    def mark_done(index: int) -> None:
        nonlocal processed_chars
        completed.add(index)
        processed_chars = sum(len(cues[item].text) for item in completed)
        session["completed_chunks"] = sorted(completed)
        session["processed_chars"] = processed_chars
        session["retry_status"] = ""
        _atomic_json(session_file, session)
        elapsed = max(0.1, time.monotonic() - started)
        done = len(completed)
        remaining = max(0, len(cues) - done)
        if progress:
            progress(
                {
                    "processed_chars": processed_chars,
                    "total_chars": total_chars,
                    "done": done,
                    "total": len(cues),
                    "percent": int(done * 100 / len(cues)),
                    "eta_seconds": int(elapsed / max(1, done) * remaining),
                    "failed_chunks": int(session.get("failed_chunks", 0)),
                    "retry_status": session.get("retry_status", ""),
                    "workers": workers,
                }
            )

    def synthesize_index(index: int) -> int:
        cue = cues[index]
        path = chunk_paths[index]
        last_error: Exception | None = None
        for attempt in range(1, 4):
            _wait_while_paused(pause_event, cancel_event)
            path.unlink(missing_ok=True)
            try:
                synthesize_wav(cue.text, path)
                if not verify_wav_file(path):
                    raise RuntimeError("Invalid timecode WAV chunk.")
                return index
            except Exception as error:
                last_error = error
                if attempt >= 3:
                    break
                session["retry_status"] = f"Cue {index + 1} retry {attempt + 1}/3"
                _atomic_json(session_file, session)
                time.sleep(0.8 * attempt)
        raise RuntimeError(str(last_error) if last_error else "Timecode cue failed.")

    try:
        pending = [index for index in range(len(cues)) if index not in completed]
        if workers > 1 and pending:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                for index in pending:
                    _wait_while_paused(pause_event, cancel_event)
                    futures[pool.submit(synthesize_index, index)] = index
                for future in as_completed(futures):
                    _wait_while_paused(pause_event, cancel_event)
                    index = futures[future]
                    try:
                        mark_done(future.result())
                    except Exception:
                        session["failed_chunks"] = int(session.get("failed_chunks", 0)) + 1
                        session["status"] = "failed"
                        session["retry_status"] = f"Cue {index + 1} failed"
                        _atomic_json(session_file, session)
                        raise

        for index, cue in enumerate(cues):
            _wait_while_paused(pause_event, cancel_event)
            if index not in completed:
                path = chunk_paths[index]
                path.unlink(missing_ok=True)
                try:
                    synthesize_wav(cue.text, path)
                    if not verify_wav_file(path):
                        raise RuntimeError("Invalid timecode WAV chunk.")
                except Exception:
                    session["failed_chunks"] = int(session.get("failed_chunks", 0)) + 1
                    session["status"] = "failed"
                    session["retry_status"] = f"Cue {index + 1} failed"
                    _atomic_json(session_file, session)
                    raise
                mark_done(index)
        session["status"] = "merging"
        _atomic_json(session_file, session)
        render_timecoded_wav(cues, chunk_paths, output_path, volume_percent=volume)
    except CancelledError:
        session["status"] = "paused" if pause_event is not None and pause_event.is_set() else "stopped"
        _atomic_json(session_file, session)
        raise
    except MergeError:
        session["status"] = "merge_failed"
        _atomic_json(session_file, session)
        raise

    for path in chunk_paths:
        path.unlink(missing_ok=True)
    if script_file.is_file():
        script_file.unlink(missing_ok=True)
    session["status"] = "complete"
    _atomic_json(session_file, session)
    return output_path
