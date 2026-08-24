"""Save generated MP3/WAV files to the public Music collection on Android."""

from __future__ import annotations

import shutil
from pathlib import Path

from kivy.utils import platform


PUBLIC_FOLDER_NAME = "BM Text to Voice"


def _unique_path(folder: Path, filename: str) -> Path:
    suffix = Path(filename).suffix or ".mp3"
    stem = Path(filename).stem
    candidate = folder / f"{stem}{suffix}"
    number = 2
    while candidate.exists():
        candidate = folder / f"{stem}_{number}{suffix}"
        number += 1
    return candidate


def save_to_public_audio(source: Path, filename: str) -> str:
    """Copy an audio draft into Music/BM Text to Voice and return its display path."""

    source = Path(source)
    if not source.is_file() or source.stat().st_size <= 0:
        raise OSError("Generated audio file is missing or empty.")

    if platform != "android":
        folder = Path.home() / "Music" / PUBLIC_FOLDER_NAME
        folder.mkdir(parents=True, exist_ok=True)
        destination = _unique_path(folder, filename)
        shutil.copyfile(source, destination)
        if destination.stat().st_size != source.stat().st_size:
            destination.unlink(missing_ok=True)
            raise OSError("Saved audio size does not match the source file.")
        return str(destination)

    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    BuildVersion = autoclass("android.os.Build$VERSION")
    Environment = autoclass("android.os.Environment")
    MediaColumns = autoclass("android.provider.MediaStore$MediaColumns")
    ContentValues = autoclass("android.content.ContentValues")
    Integer = autoclass("java.lang.Integer")

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    suffix = source.suffix.lower() or Path(filename).suffix.lower()
    mime_type = "audio/wav" if suffix == ".wav" else "audio/mpeg" if suffix == ".mp3" else "audio/*"

    if int(BuildVersion.SDK_INT) >= 29:
        MediaStore = autoclass("android.provider.MediaStore")
        MediaAudio = autoclass("android.provider.MediaStore$Audio$Media")
        AudioColumns = autoclass("android.provider.MediaStore$Audio$AudioColumns")
        values = ContentValues()
        values.put(MediaColumns.DISPLAY_NAME, filename)
        values.put(MediaColumns.MIME_TYPE, mime_type)
        values.put(MediaColumns.RELATIVE_PATH, f"{Environment.DIRECTORY_MUSIC}/{PUBLIC_FOLDER_NAME}")
        values.put(AudioColumns.IS_MUSIC, Integer(1))
        values.put(MediaColumns.IS_PENDING, Integer(1))
        audio_collection = MediaAudio.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        uri = resolver.insert(audio_collection, values)
        if uri is None:
            raise RuntimeError("Android Music жазбасын жасау мүмкін болмады.")
        stream = None
        try:
            stream = resolver.openOutputStream(uri, "w")
            if stream is None:
                raise RuntimeError("Could not open Android Music output stream.")
            written = 0
            with source.open("rb") as input_file:
                while True:
                    chunk = input_file.read(256 * 1024)
                    if not chunk:
                        break
                    stream.write(bytearray(chunk))
                    written += len(chunk)
            stream.flush()
            if written != source.stat().st_size:
                raise OSError("Android audio copy was incomplete.")
        except Exception:
            try: resolver.delete(uri, None, None)
            except Exception: pass
            raise
        finally:
            if stream is not None:
                try: stream.close()
                except Exception: pass
        try:
            done_values = ContentValues(); done_values.put(MediaColumns.IS_PENDING, Integer(0)); resolver.update(uri, done_values, None, None)
        except Exception:
            try: resolver.delete(uri, None, None)
            except Exception: pass
            raise
        return f"Music/{PUBLIC_FOLDER_NAME}/{filename}"

    public_music = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC)
    music = Path(str(public_music.getAbsolutePath())) / PUBLIC_FOLDER_NAME
    music.mkdir(parents=True, exist_ok=True)
    destination = _unique_path(music, filename)
    shutil.copyfile(source, destination)
    if destination.stat().st_size != source.stat().st_size:
        destination.unlink(missing_ok=True)
        raise OSError("Saved audio size does not match the source file.")
    return str(destination)


def save_to_downloads(source: Path, filename: str) -> str:
    return save_to_public_audio(source, filename)
