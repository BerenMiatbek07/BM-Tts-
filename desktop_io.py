"""Windows/Desktop file dialogs and MP3/WAV save helpers.

This module is intentionally free of Android imports.  Tkinter is imported
only inside the dialog functions so the Android build can keep importing the
shared app code without needing desktop GUI libraries.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _default_documents_dir() -> Path:
    for folder_name in ("Documents", "Desktop", "Downloads"):
        candidate = Path.home() / folder_name
        if candidate.exists():
            return candidate
    return Path.home()


def _default_audio_dir() -> Path:
    for folder_name in ("Music", "Downloads", "Desktop", "Documents"):
        candidate = Path.home() / folder_name
        if candidate.exists():
            return candidate
    return Path.home()


def _dialog_root():
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        root.update_idletasks()
    except Exception:
        pass
    return root


def choose_text_file_path(title: str) -> Path | None:
    from tkinter import filedialog

    root = _dialog_root()
    try:
        selected = filedialog.askopenfilename(
            parent=root,
            title=title,
            initialdir=str(_default_documents_dir()),
            filetypes=[("Text files", "*.txt *.text *.md *.srt"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None


def choose_spreadsheet_file_path(title: str) -> Path | None:
    from tkinter import filedialog

    root = _dialog_root()
    try:
        selected = filedialog.askopenfilename(
            parent=root,
            title=title,
            initialdir=str(_default_documents_dir()),
            filetypes=[("Excel / CSV files", "*.xlsx *.xlsm *.csv"), ("Excel workbooks", "*.xlsx *.xlsm"), ("CSV files", "*.csv"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None


def choose_save_audio_path(title: str, initial_filename: str) -> Path | None:
    from tkinter import filedialog

    suffix = Path(initial_filename).suffix.lower()
    if suffix not in (".mp3", ".wav"):
        suffix = ".mp3"
    label = "WAV audio" if suffix == ".wav" else "MP3 audio"
    root = _dialog_root()
    try:
        selected = filedialog.asksaveasfilename(
            parent=root,
            title=title,
            initialdir=str(_default_audio_dir()),
            initialfile=initial_filename,
            defaultextension=suffix,
            confirmoverwrite=True,
            filetypes=[(label, f"*{suffix}"), ("Audio files", "*.mp3 *.wav"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    if not selected:
        return None
    path = Path(selected)
    if path.suffix.lower() not in (".mp3", ".wav"):
        path = path.with_suffix(suffix)
    return path


def save_audio_to_path(source: Path, destination: Path) -> str:
    source = Path(source)
    destination = Path(destination)
    source_suffix = source.suffix.lower()
    if destination.suffix.lower() not in (".mp3", ".wav"):
        destination = destination.with_suffix(source_suffix or ".mp3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source.resolve() == destination.resolve():
            return str(destination)
    except Exception:
        pass
    shutil.copyfile(source, destination)
    if not destination.exists() or destination.stat().st_size <= 0:
        raise OSError("Saved audio file is empty or missing.")
    return str(destination)


def choose_save_mp3_path(title: str, initial_filename: str) -> Path | None:
    return choose_save_audio_path(title, initial_filename)


def save_mp3_to_path(source: Path, destination: Path) -> str:
    return save_audio_to_path(source, destination)
