"""Small persistent-state microphone recorder used by the Windows clone flow."""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path


class DesktopVoiceRecorder:
    sample_rate = 16_000
    channels = 1

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status: dict[str, object] = {"state": "idle", "duration_seconds": 0.0}

    def available(self) -> bool:
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            return int(device.get("max_input_channels", 0)) > 0
        except Exception:
            return False

    def start(self, path: str | Path, max_seconds: float = 9.5) -> dict[str, object]:
        if self._thread is not None and self._thread.is_alive():
            return {"ok": False, "error": "already_recording"}
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        self._stop.clear()
        with self._lock:
            self._status = {
                "state": "starting",
                "duration_seconds": 0.0,
                "path": str(destination),
            }

        def worker() -> None:
            started = time.monotonic()
            try:
                import sounddevice as sd

                frames: list[bytes] = []
                with sd.RawInputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    blocksize=1600,
                ) as stream:
                    with self._lock:
                        self._status["state"] = "recording"
                    while not self._stop.is_set():
                        elapsed = time.monotonic() - started
                        if elapsed >= max_seconds:
                            break
                        data, _overflowed = stream.read(1600)
                        frames.append(bytes(data))
                        with self._lock:
                            self._status["duration_seconds"] = min(elapsed, max_seconds)
                duration = min(time.monotonic() - started, max_seconds)
                with wave.open(str(destination), "wb") as output:
                    output.setnchannels(self.channels)
                    output.setsampwidth(2)
                    output.setframerate(self.sample_rate)
                    output.writeframes(b"".join(frames))
                with self._lock:
                    self._status = {
                        "state": "ready" if destination.stat().st_size > 44 else "failed",
                        "duration_seconds": duration,
                        "path": str(destination),
                    }
            except Exception as error:
                with self._lock:
                    self._status = {
                        "state": "failed",
                        "duration_seconds": time.monotonic() - started,
                        "path": str(destination),
                        "error": type(error).__name__,
                    }

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()
        return {"ok": True, "path": str(destination)}

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, object]:
        with self._lock:
            return dict(self._status)

    @staticmethod
    def delete(path: str | Path) -> None:
        Path(path).unlink(missing_ok=True)
