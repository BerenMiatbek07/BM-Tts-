"""Resumable parallel chunk generation that produces one final MP3."""

from __future__ import annotations

import json
import random
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from edge_service import (
    CancelledError,
    EdgeRateLimitError,
    EdgeTtsError,
    _split_utf8,
    _synthesize_piece,
)


class MergeError(RuntimeError):
    pass


ProgressCallback = Callable[[dict], None]


def _atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_generation_session(session_dir: Path) -> dict | None:
    path = session_dir / "session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if data.get("status") != "complete" else None


def discard_generation_session(session_dir: Path) -> None:
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)


def _wait_while_paused(
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> None:
    while pause_event and pause_event.is_set():
        if cancel_event and cancel_event.is_set():
            raise CancelledError("Generation stopped.")
        time.sleep(0.15)
    if cancel_event and cancel_event.is_set():
        raise CancelledError("Generation stopped.")


def _sleep_interruptibly(
    seconds: float,
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _wait_while_paused(pause_event, cancel_event)
        time.sleep(min(0.15, max(0.0, deadline - time.monotonic())))


def _write_chunk(
    index: int,
    text: str,
    path: Path,
    voice: str,
    rate: int,
    pitch: int,
    volume: int,
    sentence_pause_ms: int,
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> dict:
    last_error: BaseException | None = None
    rate_limited = False
    for attempt in range(1, 5):
        _wait_while_paused(pause_event, cancel_event)
        try:
            payload = _synthesize_piece(
                text,
                voice,
                rate,
                pitch,
                volume,
                sentence_pause_ms=sentence_pause_ms,
            )
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(payload)
            if temporary.stat().st_size <= 0:
                raise OSError("Empty TTS response.")
            temporary.replace(path)
            return {
                "index": index,
                "attempts": attempt,
                "rate_limited": rate_limited,
            }
        except CancelledError:
            raise
        except Exception as error:
            last_error = error
            message = str(error).lower()
            rate_limited = rate_limited or isinstance(error, EdgeRateLimitError) or "429" in message or "rate limit" in message
            if attempt < 4:
                base_delay = 8.0 if rate_limited else 1.75 * (2 ** (attempt - 1))
                _sleep_interruptibly(
                    min(20.0, base_delay) + random.uniform(0.0, 0.8),
                    pause_event,
                    cancel_event,
                )
    detail = str(last_error).strip() if last_error else "unknown TTS error"
    raise EdgeTtsError(
        f"Speech chunk {index + 1} failed after 4 attempts: {detail}"
    ) from last_error


def verify_mp3_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    with path.open("rb") as source:
        header = source.read(3)
    return header == b"ID3" or header[:1] == b"\xff"


def merge_mp3_chunks(chunk_paths: list[Path], output_path: Path) -> None:
    if not chunk_paths or any(
        not path.exists() or path.stat().st_size <= 0 for path in chunk_paths
    ):
        raise MergeError("Not all temporary audio chunks are available.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".merge")
    try:
        with temporary.open("wb") as destination:
            for chunk_path in chunk_paths:
                with chunk_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, 256 * 1024)
            destination.flush()
        if not verify_mp3_file(temporary):
            raise MergeError("Final MP3 validation failed.")
        temporary.replace(output_path)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        if isinstance(error, MergeError):
            raise
        raise MergeError("Could not merge the temporary audio chunks.") from error


def retry_merge_session(session_dir: Path) -> Path:
    data = load_generation_session(session_dir)
    if not data:
        raise MergeError("No resumable merge session.")
    chunk_paths = [session_dir / name for name in data.get("temp_chunk_paths", [])]
    output_path = Path(data["final_output_path"])
    merge_mp3_chunks(chunk_paths, output_path)
    for path in chunk_paths:
        path.unlink(missing_ok=True)
    script_path = Path(data.get("script_path", ""))
    if script_path.is_file():
        script_path.unlink(missing_ok=True)
    data["status"] = "complete"
    _atomic_json(session_dir / "session.json", data)
    return output_path


def generate_one_mp3(
    *,
    text: str,
    voice: str,
    language: str,
    rate: int,
    pitch: int,
    volume: int,
    sentence_pause_ms: int,
    output_path: Path,
    session_dir: Path,
    source: str,
    source_file_name: str,
    workers: int,
    progress: ProgressCallback | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = False,
) -> None:
    pieces = _split_utf8(text)
    if not pieces:
        raise ValueError("Text is empty.")
    # Fast mode may start with several workers, then automatically drops to a
    # safer count if the service rate-limits or a batch fails.
    workers = max(1, min(6, int(workers)))
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"
    script_file = session_dir / "script.txt"
    if not resume:
        for old_chunk in session_dir.glob("chunk_*.mp3"):
            old_chunk.unlink(missing_ok=True)
        script_file.write_text(text, encoding="utf-8")

    chunk_paths = [
        session_dir / f"chunk_{index:06d}.mp3"
        for index in range(len(pieces))
    ]
    completed = {
        index
        for index, path in enumerate(chunk_paths)
        if resume and path.exists() and path.stat().st_size > 0
    }
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    previous = load_generation_session(session_dir) if resume else None
    session = {
        "engine": "edge",
        "status": "running",
        "total_chars": len(text),
        "processed_chars": sum(len(pieces[index]) for index in completed),
        "total_chunks": len(pieces),
        "completed_chunks": sorted(completed),
        "failed_chunks": int((previous or {}).get("failed_chunks", 0)),
        "voice": voice,
        "language": language,
        "rate": rate,
        "pitch": pitch,
        "volume": volume,
        "pause_setting": sentence_pause_ms,
        "source": source,
        "source_file_name": source_file_name,
        "created_at": (previous or {}).get("created_at", created_at),
        "temp_chunk_paths": [path.name for path in chunk_paths],
        "final_output_path": str(output_path),
        "script_path": str(script_file),
        "workers": workers,
        "retry_status": "",
    }
    _atomic_json(session_file, session)

    start = time.monotonic()
    pending = [index for index in range(len(pieces)) if index not in completed]
    current_workers = workers
    try:
        while pending:
            _wait_while_paused(pause_event, cancel_event)
            batch = pending[: current_workers * 2]
            pending = pending[len(batch) :]
            rate_limited_in_batch = False
            sequential_fallback: list[int] = []
            with ThreadPoolExecutor(max_workers=current_workers) as pool:
                futures = {
                    pool.submit(
                        _write_chunk,
                        index,
                        pieces[index],
                        chunk_paths[index],
                        voice,
                        rate,
                        pitch,
                        volume,
                        sentence_pause_ms,
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
                        session["failed_chunks"] += 1
                        if current_workers > 1:
                            sequential_fallback.append(index)
                            session["retry_status"] = (
                                f"chunk {index + 1}: sequential fallback"
                            )
                            _atomic_json(session_file, session)
                            continue
                        session["status"] = "failed"
                        session["retry_status"] = "sequential retries exhausted"
                        _atomic_json(session_file, session)
                        raise
                    completed.add(index)
                    rate_limited_in_batch = (
                        rate_limited_in_batch or result["rate_limited"]
                    )
                    session["completed_chunks"] = sorted(completed)
                    session["processed_chars"] = (
                        len(text)
                        if len(completed) == len(pieces)
                        else sum(len(pieces[item]) for item in completed)
                    )
                    session["retry_status"] = (
                        f"chunk {index + 1}: retry {result['attempts'] - 1}"
                        if result["attempts"] > 1
                        else ""
                    )
                    _atomic_json(session_file, session)
                    if progress:
                        elapsed = max(0.001, time.monotonic() - start)
                        done = len(completed)
                        progress(
                            {
                                "processed_chars": session["processed_chars"],
                                "total_chars": len(text),
                                "done": done,
                                "total": len(pieces),
                                "percent": done / len(pieces) * 100,
                                "eta_seconds": (
                                    elapsed / done * (len(pieces) - done)
                                    if done
                                    else 0
                                ),
                                "failed_chunks": session["failed_chunks"],
                                "retry_status": session["retry_status"],
                                "workers": current_workers,
                            }
                        )
            if sequential_fallback:
                pending = sequential_fallback + pending
                current_workers = 1
                session["workers"] = 1
                session["retry_status"] = "Network fallback: sequential mode"
                _atomic_json(session_file, session)
            if rate_limited_in_batch and current_workers > 1:
                current_workers -= 1
                session["workers"] = current_workers
                session["retry_status"] = "Rate limit: worker count reduced"
                _atomic_json(session_file, session)
                _sleep_interruptibly(8.0, pause_event, cancel_event)

        session["status"] = "merging"
        _atomic_json(session_file, session)
        merge_mp3_chunks(chunk_paths, output_path)
    except CancelledError:
        session["status"] = "paused" if pause_event and pause_event.is_set() else "stopped"
        _atomic_json(session_file, session)
        raise
    except MergeError:
        session["status"] = "merge_failed"
        _atomic_json(session_file, session)
        raise

    for chunk_path in chunk_paths:
        chunk_path.unlink(missing_ok=True)
    script_file.unlink(missing_ok=True)
    session["status"] = "complete"
    _atomic_json(session_file, session)
