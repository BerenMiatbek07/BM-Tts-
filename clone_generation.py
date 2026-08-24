"""Chunked, resumable WAV generation for the verified local clone profile."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from kivy.utils import platform

from edge_service import CancelledError
from generation import MergeError, load_generation_session
from sherpa_generation import (
    _atomic_json,
    _merge_wav_chunks,
    _wait_while_paused,
    split_sherpa_text,
    verify_wav_file,
)


MAX_CLONE_CHARS = 420


def split_clone_text(text: str) -> list[str]:
    return split_sherpa_text(text, limit=MAX_CLONE_CHARS)


def estimate_clone_chunks(text: str) -> int:
    return max(1, len(split_clone_text(text)))


def retry_clone_merge_session(session_dir: Path) -> Path:
    session = load_generation_session(session_dir)
    if not session or session.get("engine") != "clone":
        raise MergeError("No resumable voice-clone merge session")
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


def generate_clone_wav(
    *,
    text: str,
    model_dir: Path,
    reference_wave: Path,
    reference_text: str,
    language: str,
    rate: int,
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
    num_threads: int = 2,
) -> Path:
    chunks = split_clone_text(text)
    if not chunks:
        raise ValueError("Text is empty")

    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"
    script_file = session_dir / "script.txt"
    script_file.write_text(text, encoding="utf-8")
    previous = load_generation_session(session_dir) if resume else None
    completed: set[int] = set()
    if previous and previous.get("engine") == "clone":
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
        "engine": "clone",
        "base_engine": "clone",
        "status": "running",
        "script_path": str(script_file),
        "source": source,
        "source_file_name": source_file_name,
        "model_dir": str(model_dir),
        "reference_wave": str(reference_wave),
        "voice": "clone:verified",
        "language": language,
        "rate": int(rate),
        "pitch": 0,
        "volume": int(volume),
        "pause_setting": int(sentence_pause_ms),
        "workers": 1,
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

    activity = None
    desktop_engine = None
    if platform == "android":
        from jnius import autoclass, cast

        base_activity = autoclass("org.kivy.android.PythonActivity")
        activity = cast("org.bmtts.bmtextspeech.BmPythonActivity", base_activity.mActivity)
        if activity is None:
            raise RuntimeError("Android activity is unavailable")
    else:
        from desktop_omnivoice import get_desktop_omnivoice_engine

        desktop_engine = get_desktop_omnivoice_engine(model_dir)
    started = time.monotonic()
    speed = max(0.5, min(2.0, 1.0 + int(rate) / 100.0))
    try:
        for index, piece in enumerate(chunks):
            _wait_while_paused(pause_event, cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            if index not in completed:
                path = chunk_paths[index]
                path.unlink(missing_ok=True)
                try:
                    if activity is not None:
                        ok = bool(
                            activity.synthesizeZipVoiceToWave(
                                str(Path(model_dir).resolve()),
                                max(1, min(4, int(num_threads))),
                                piece,
                                str(Path(reference_wave).resolve()),
                                reference_text,
                                float(speed),
                                str(path),
                            )
                        )
                    else:
                        desktop_engine.synthesize(
                            text=piece,
                            reference_wave=reference_wave,
                            reference_text=reference_text,
                            language=language,
                            rate=rate,
                            volume=volume,
                            output_path=path,
                        )
                        ok = True
                    if not ok or not verify_wav_file(path):
                        raise RuntimeError("Voice clone produced an invalid WAV chunk")
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
            if progress:
                progress(
                    {
                        "processed_chars": processed_chars,
                        "total_chars": len(text),
                        "done": done,
                        "total": len(chunks),
                        "percent": int(done * 100 / len(chunks)),
                        "eta_seconds": int(elapsed / max(1, done) * remaining),
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
        if activity is not None:
            try:
                activity.releaseZipVoice()
            except Exception:
                pass

    session["status"] = "complete"
    session["processed_chars"] = len(text)
    _atomic_json(session_file, session)
    return output_path
