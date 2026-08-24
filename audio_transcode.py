"""Reliable compressed-audio to PCM conversion for timecode cues."""

from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

from kivy.utils import platform


def _desktop_ffmpeg() -> str | None:
    """Find FFmpeg both in development and inside a PyInstaller EXE."""
    candidates: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(Path(bundle) / "ffmpeg.exe")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ffmpeg.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffmpeg")


def _valid_wav(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 44:
            return False
        with wave.open(str(path), "rb") as source:
            return (
                source.getnchannels() > 0
                and source.getsampwidth() == 2
                and source.getframerate() > 0
                and source.getnframes() > 0
            )
    except Exception:
        return False


def mp3_to_wav(
    mp3_path: Path,
    wav_path: Path,
    *,
    android_activity=None,
) -> Path:
    """Decode an MP3 cue to 16-bit PCM WAV and validate the result."""

    mp3_path = Path(mp3_path).resolve()
    wav_path = Path(wav_path).resolve()
    if not mp3_path.is_file() or mp3_path.stat().st_size <= 0:
        raise RuntimeError("The temporary MP3 cue is missing or empty.")
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.unlink(missing_ok=True)

    if platform == "android":
        if android_activity is None:
            from android_activity import get_bm_activity

            android_activity = get_bm_activity()
        if not bool(android_activity.transcodeMp3ToWav(str(mp3_path), str(wav_path))):
            raise RuntimeError("Android could not decode the temporary MP3 cue.")
    else:
        decoded = False
        soundfile_error = ""
        try:
            import soundfile as sf

            audio, sample_rate = sf.read(str(mp3_path), dtype="float32", always_2d=True)
            if sample_rate > 0 and getattr(audio, "size", 0) > 0:
                sf.write(str(wav_path), audio, sample_rate, subtype="PCM_16")
                decoded = _valid_wav(wav_path)
        except Exception as error:
            soundfile_error = str(error)
            wav_path.unlink(missing_ok=True)

        if not decoded:
            ffmpeg = _desktop_ffmpeg()
            if not ffmpeg:
                detail = f" ({soundfile_error[-180:]})" if soundfile_error else ""
                raise RuntimeError(
                    "MP3 decode failed. Install FFmpeg or use a soundfile build with MP3 support." + detail
                )
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(mp3_path),
                    "-acodec",
                    "pcm_s16le",
                    str(wav_path),
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError((result.stderr or "MP3 decode failed.")[-400:])

    if not _valid_wav(wav_path):
        wav_path.unlink(missing_ok=True)
        raise RuntimeError("The decoded timecode WAV is invalid.")
    return wav_path
