"""Resumable Soniox web-TTS generation for BM Voice Studio."""

from __future__ import annotations

import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from edge_service import CancelledError
from generation import MergeError, load_generation_session, merge_mp3_chunks
from soniox_service import SonioxTTS, split_soniox_text


ProgressCallback = Callable[[dict], None]


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def _wait(pause_event: threading.Event | None, cancel_event: threading.Event | None) -> None:
    while pause_event is not None and pause_event.is_set():
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Generation stopped.")
        time.sleep(0.15)
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError("Generation stopped.")


def _sleep(seconds: float, pause_event, cancel_event) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        _wait(pause_event, cancel_event)
        time.sleep(min(0.15, max(0.0, end - time.monotonic())))


def estimate_soniox_chunks(text: str) -> int:
    return max(1, len(split_soniox_text(text)))


def _write_chunk(
    client: SonioxTTS,
    index: int,
    piece: str,
    path: Path,
    voice_name: str,
    language: str,
    pause_event,
    cancel_event,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 5):
        _wait(pause_event, cancel_event)
        try:
            payload = client.synthesize_chunk(piece, voice=voice_name, language=language)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            if temporary.stat().st_size <= 16:
                raise RuntimeError("Empty Soniox audio chunk")
            temporary.replace(path)
            return {"index": index, "attempts": attempt}
        except CancelledError:
            raise
        except Exception as error:
            last_error = error
            if attempt < 4:
                _sleep(min(12.0, 1.5 * (2 ** (attempt - 1))) + random.uniform(0.0, 0.5), pause_event, cancel_event)
    raise RuntimeError(f"Soniox chunk {index + 1} failed after 4 attempts: {last_error}") from last_error


def generate_soniox_mp3(
    *,
    client: SonioxTTS,
    text: str,
    voice_key: str,
    language: str,
    output_path: Path,
    session_dir: Path,
    source: str,
    source_file_name: str,
    workers: int = 2,
    progress: ProgressCallback | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = False,
) -> Path:
    pieces = split_soniox_text(text)
    if not pieces:
        raise ValueError("Text is empty")
    voice_name = voice_key.split(":", 1)[1] if voice_key.startswith("soniox:") else voice_key
    # curl_cffi/requests sessions are not guaranteed to be thread-safe.
    # The upstream pysoniox example is sequential as well, so keep one worker
    # for reliability and to reduce the chance of web-endpoint throttling.
    workers = 1

    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"
    script_file = session_dir / "script.txt"
    previous = load_generation_session(session_dir) if resume else None
    if not resume:
        for old in session_dir.glob("chunk_*.mp3"):
            old.unlink(missing_ok=True)
        script_file.write_text(text, encoding="utf-8")
    elif not script_file.exists():
        script_file.write_text(text, encoding="utf-8")

    chunk_paths = [session_dir / f"chunk_{index:06d}.mp3" for index in range(len(pieces))]
    completed = {
        index
        for index, path in enumerate(chunk_paths)
        if resume and path.is_file() and path.stat().st_size > 16
    }
    session = {
        "engine": "soniox",
        "base_engine": "soniox",
        "status": "running",
        "script_path": str(script_file),
        "source": source,
        "source_file_name": source_file_name,
        "voice": f"soniox:{voice_name}",
        "language": language,
        "rate": 0,
        "pitch": 0,
        "volume": 0,
        "pause_setting": 0,
        "workers": workers,
        "final_output_path": str(output_path),
        "temp_chunk_paths": [path.name for path in chunk_paths],
        "completed_chunks": sorted(completed),
        "processed_chars": sum(len(pieces[index]) for index in completed),
        "total_chars": len(text),
        "failed_chunks": int((previous or {}).get("failed_chunks", 0)),
        "retry_status": "",
    }
    _atomic_json(session_file, session)

    started = time.monotonic()
    pending = [index for index in range(len(pieces)) if index not in completed]
    try:
        while pending:
            _wait(pause_event, cancel_event)
            batch = pending[: workers * 2]
            pending = pending[len(batch):]
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        _write_chunk,
                        client,
                        index,
                        pieces[index],
                        chunk_paths[index],
                        voice_name,
                        language,
                        pause_event,
                        cancel_event,
                    ): index
                    for index in batch
                }
                for future in as_completed(futures):
                    index = futures[future]
                    try:
                        result = future.result()
                    except CancelledError:
                        raise
                    except Exception:
                        session["failed_chunks"] = int(session.get("failed_chunks", 0)) + 1
                        session["status"] = "failed"
                        session["retry_status"] = f"chunk {index + 1} failed"
                        _atomic_json(session_file, session)
                        raise
                    completed.add(index)
                    session["completed_chunks"] = sorted(completed)
                    session["processed_chars"] = sum(len(pieces[item]) for item in completed)
                    session["retry_status"] = (
                        f"chunk {index + 1}: retry {result['attempts'] - 1}"
                        if result["attempts"] > 1 else ""
                    )
                    _atomic_json(session_file, session)
                    if progress:
                        elapsed = max(0.01, time.monotonic() - started)
                        done = len(completed)
                        progress({
                            "processed_chars": session["processed_chars"],
                            "total_chars": len(text),
                            "done": done,
                            "total": len(pieces),
                            "percent": int(done * 100 / len(pieces)),
                            "eta_seconds": int(elapsed / max(1, done) * (len(pieces) - done)),
                            "failed_chunks": session["failed_chunks"],
                            "retry_status": session["retry_status"],
                            "workers": workers,
                        })
        session["status"] = "merging"
        _atomic_json(session_file, session)
        merge_mp3_chunks(chunk_paths, output_path)
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
    script_file.unlink(missing_ok=True)
    session["status"] = "complete"
    session["processed_chars"] = len(text)
    _atomic_json(session_file, session)
    return output_path


__all__ = ["estimate_soniox_chunks", "generate_soniox_mp3"]
