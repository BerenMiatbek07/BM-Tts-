"""Chunked WAV generation for downloaded Sherpa/Piper voices."""

from __future__ import annotations

import audioop
import json
import os
import re
import time
import wave
from pathlib import Path
from typing import Callable

from kivy.utils import platform

from edge_service import CancelledError
from generation import MergeError, load_generation_session

MAX_SHERPA_CHARS = 1200
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？…])\s+|\n+")


def _atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temp.replace(path)


def split_sherpa_text(text: str, limit: int = MAX_SHERPA_CHARS) -> list[str]:
    text = " ".join(text.replace("\r", "\n").split())
    if not text:
        return []
    sentences = [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) <= limit:
            candidate = f"{current} {sentence}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
            continue
        words = sentence.split()
        for word in words:
            if len(word) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(
                    word[index : index + limit]
                    for index in range(0, len(word), limit)
                )
                continue
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = word
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def estimate_sherpa_chunks(text: str) -> int:
    return max(1, len(split_sherpa_text(text)))


def verify_wav_file(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 44:
            return False
        with wave.open(str(path), "rb") as source:
            return source.getnframes() > 0 and source.getframerate() > 0
    except Exception:
        return False


def _wait_while_paused(pause_event, cancel_event) -> None:
    while pause_event is not None and pause_event.is_set():
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        time.sleep(0.15)


def _merge_wav_chunks(
    chunk_paths: list[Path],
    output_path: Path,
    *,
    sentence_pause_ms: int = 0,
    volume_percent: int = 0,
) -> None:
    if not chunk_paths:
        raise MergeError("No WAV chunks to merge")
    temp = output_path.with_suffix(".wav.tmp")
    temp.unlink(missing_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        expected = None
        with wave.open(str(temp), "wb") as destination:
            for index, chunk in enumerate(chunk_paths):
                if not verify_wav_file(chunk):
                    raise MergeError(f"Invalid WAV chunk: {chunk.name}")
                with wave.open(str(chunk), "rb") as source:
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
                        raise MergeError("WAV chunks use different audio formats")
                    while True:
                        frames = source.readframes(16384)
                        if not frames:
                            break
                        if volume_percent:
                            factor = max(0.05, 1.0 + volume_percent / 100.0)
                            frames = audioop.mul(frames, params[1], factor)
                        destination.writeframesraw(frames)
                if sentence_pause_ms > 0 and index < len(chunk_paths) - 1:
                    channels, sample_width, sample_rate, _compression = expected
                    silence_frames = int(sample_rate * sentence_pause_ms / 1000)
                    destination.writeframesraw(
                        b"\x00" * silence_frames * channels * sample_width
                    )
        if not verify_wav_file(temp):
            raise MergeError("Merged WAV validation failed")
        os.replace(temp, output_path)
    except Exception as error:
        temp.unlink(missing_ok=True)
        if isinstance(error, MergeError):
            raise
        raise MergeError(str(error)) from error


def retry_sherpa_merge_session(session_dir: Path) -> Path:
    session = load_generation_session(session_dir)
    if not session or session.get("engine") != "sherpa":
        raise MergeError("No resumable Sherpa merge session")
    chunks = [session_dir / name for name in session.get("temp_chunk_paths", [])]
    output = Path(str(session.get("final_output_path", "")))
    _merge_wav_chunks(
        chunks,
        output,
        sentence_pause_ms=int(session.get("pause_setting", 0)),
        volume_percent=int(session.get("volume", 0)),
    )
    session["status"] = "complete"
    _atomic_json(session_dir / "session.json", session)
    return output


def generate_one_wav(
    *,
    text: str,
    model_dir: Path,
    model_id: str,
    language: str,
    rate: int,
    pitch: int,
    volume: int,
    sentence_pause_ms: int,
    output_path: Path,
    session_dir: Path,
    source: str,
    source_file_name: str,
    progress: Callable[[dict], None] | None = None,
    pause_event=None,
    cancel_event=None,
    resume: bool = False,
    speaker_id: int = 0,
    num_threads: int = 2,
) -> Path:
    del pitch  # Piper speed is supported; pitch transformation is intentionally disabled.
    if platform != "android":
        raise RuntimeError("Downloaded Sherpa voices currently run on Android")

    chunks = split_sherpa_text(text)
    if not chunks:
        raise ValueError("Text is empty")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"
    script_file = session_dir / "script.txt"
    script_file.write_text(text, encoding="utf-8")

    previous = load_generation_session(session_dir) if resume else None
    completed = set()
    if previous and previous.get("engine") == "sherpa" and previous.get("model_id") == model_id:
        completed = {
            int(index)
            for index in previous.get("completed_chunks", [])
            if str(index).isdigit() or isinstance(index, int)
        }
    else:
        for old in session_dir.glob("chunk_*.wav"):
            old.unlink(missing_ok=True)

    chunk_paths = [session_dir / f"chunk_{index:06d}.wav" for index in range(len(chunks))]
    completed = {
        index
        for index in completed
        if index < len(chunk_paths) and verify_wav_file(chunk_paths[index])
    }
    processed_chars = sum(len(chunks[index]) for index in completed)
    session = {
        "engine": "sherpa",
        "status": "running",
        "script_path": str(script_file),
        "source": source,
        "source_file_name": source_file_name,
        "model_id": model_id,
        "model_dir": str(model_dir),
        "voice": f"sherpa:{model_id}",
        "language": language,
        "rate": int(rate),
        "pitch": 0,
        "volume": int(volume),
        "pause_setting": int(sentence_pause_ms),
        "workers": 1,
        "speaker_id": int(speaker_id),
        "num_threads": int(num_threads),
        "final_output_path": str(output_path),
        "temp_chunk_paths": [path.name for path in chunk_paths],
        "completed_chunks": sorted(completed),
        "processed_chars": processed_chars,
        "total_chars": len(text),
        "failed_chunks": int((previous or {}).get("failed_chunks", 0)),
        "retry_status": "",
    }
    _atomic_json(session_file, session)

    from android_activity import get_bm_activity

    activity = get_bm_activity()
    started = time.monotonic()
    try:
        speed = max(0.5, min(2.0, 1.0 + int(rate) / 100.0))
        for index, piece in enumerate(chunks):
            _wait_while_paused(pause_event, cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            if index not in completed:
                path = chunk_paths[index]
                path.unlink(missing_ok=True)
                try:
                    ok = bool(
                        activity.synthesizeSherpaToWave(
                            str(Path(model_dir).resolve()),
                            max(1, min(6, int(num_threads))),
                            piece,
                            int(speaker_id),
                            float(speed),
                            str(path),
                        )
                    )
                    if not ok or not verify_wav_file(path):
                        raise RuntimeError("Sherpa produced an invalid WAV chunk")
                except Exception:
                    session["failed_chunks"] = int(session.get("failed_chunks", 0)) + 1
                    session["status"] = "failed"
                    session["retry_status"] = f"Chunk {index + 1} failed"
                    _atomic_json(session_file, session)
                    raise
                completed.add(index)
                processed_chars += len(piece)
                session["completed_chunks"] = sorted(completed)
                session["processed_chars"] = processed_chars
                session["retry_status"] = ""
                _atomic_json(session_file, session)

            elapsed = max(0.1, time.monotonic() - started)
            done = len(completed)
            remaining = max(0, len(chunks) - done)
            eta = int((elapsed / max(1, done)) * remaining)
            if progress:
                progress(
                    {
                        "processed_chars": processed_chars,
                        "total_chars": len(text),
                        "done": done,
                        "total": len(chunks),
                        "percent": int(done * 100 / len(chunks)),
                        "eta_seconds": eta,
                        "failed_chunks": int(session.get("failed_chunks", 0)),
                        "retry_status": session.get("retry_status", ""),
                        "workers": 1,
                    }
                )
        session["status"] = "merging"
        _atomic_json(session_file, session)
        _merge_wav_chunks(
            chunk_paths,
            output_path,
            sentence_pause_ms=sentence_pause_ms,
            volume_percent=volume,
        )
    except CancelledError:
        session["status"] = "paused" if pause_event is not None and pause_event.is_set() else "stopped"
        _atomic_json(session_file, session)
        raise
    except MergeError:
        session["status"] = "merge_failed"
        _atomic_json(session_file, session)
        raise
    finally:
        try:
            activity.releaseSherpa()
        except Exception:
            pass

    session["status"] = "complete"
    session["processed_chars"] = len(text)
    _atomic_json(session_file, session)
    return output_path
