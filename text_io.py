"""Clipboard and text-file helpers for desktop and Android."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from kivy.utils import platform


MAX_TEXT_FILE_BYTES = 16 * 1024 * 1024

def get_android_activity():
    """Return the current custom or stock Kivy Android activity."""
    if platform != "android":
        raise RuntimeError("Android activity is available only on Android.")
    from jnius import autoclass
    try:
        activity_class = autoclass("org.kivy.android.PythonActivity")
        current = activity_class.mActivity
        if current is not None:
            return current
    except Exception:
        pass
    raise RuntimeError("Android activity is unavailable.")


def coerce_android_uri(uri):
    """Recreate a URI from text so it is safe to use on worker threads."""
    if platform != "android":
        return uri
    from jnius import autoclass
    if isinstance(uri, str):
        Uri = autoclass("android.net.Uri")
        return Uri.parse(uri)
    return uri


def java_text_to_python(value) -> str:
    """Handle both PyJNIus Java CharSequence proxies and converted Python str."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return decode_text_bytes(value)
    try:
        converted = value.toString()
    except (AttributeError, TypeError):
        converted = value
    if isinstance(converted, str):
        return converted
    return str(converted)


def clipboard_items_to_text(clip, activity) -> str:
    items: list[str] = []
    for index in range(int(clip.getItemCount())):
        item = clip.getItemAt(index)
        value = item.getText()
        if value is None:
            value = item.coerceToText(activity)
        converted = java_text_to_python(value)
        if converted:
            items.append(converted)
    return "\n".join(items)


def decode_text_bytes(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")

    if len(data) >= 4:
        odd_nulls = data[1::2].count(0)
        even_nulls = data[0::2].count(0)
        threshold = max(2, len(data) // 8)
        if odd_nulls >= threshold:
            return data.decode("utf-16-le")
        if even_nulls >= threshold:
            return data.decode("utf-16-be")

    for encoding in ("utf-8", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def read_text_path(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > MAX_TEXT_FILE_BYTES:
        raise ValueError("Text file is too large.")
    return decode_text_bytes(data)


def read_android_text_uri(uri) -> str:
    if platform != "android":
        raise RuntimeError("Android URI is available only on Android.")

    uri = coerce_android_uri(uri)
    resolver = get_android_activity().getContentResolver()
    descriptor = resolver.openFileDescriptor(uri, "r")
    if descriptor is None:
        raise OSError("Could not open the selected file.")
    file_descriptor = int(descriptor.detachFd())
    with os.fdopen(file_descriptor, "rb", closefd=True) as source:
        data = source.read(MAX_TEXT_FILE_BYTES + 1)
    if len(data) > MAX_TEXT_FILE_BYTES:
        raise ValueError("Text file is too large.")
    return decode_text_bytes(data)


def android_uri_display_name(uri) -> str:
    if platform != "android":
        return ""
    from jnius import autoclass

    uri = coerce_android_uri(uri)
    OpenableColumns = autoclass("android.provider.OpenableColumns")
    resolver = get_android_activity().getContentResolver()
    cursor = resolver.query(uri, None, None, None, None)
    if cursor is None:
        return ""
    try:
        name_index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if name_index >= 0 and cursor.moveToFirst():
            return str(cursor.getString(name_index))
    finally:
        cursor.close()
    return ""


def clipboard_text() -> str:
    return clipboard_text_details()[0]


def clipboard_text_details() -> tuple[str, str]:
    if platform == "android":
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        completed = threading.Event()
        result: dict[str, object] = {"text": "", "error": None}

        @run_on_ui_thread
        def read_android_clipboard() -> None:
            try:
                Context = autoclass("android.content.Context")
                current_activity = get_android_activity()
                manager = current_activity.getSystemService(Context.CLIPBOARD_SERVICE)
                if manager is None or not manager.hasPrimaryClip():
                    return
                clip = manager.getPrimaryClip()
                if clip is None or clip.getItemCount() == 0:
                    return
                result["text"] = clipboard_items_to_text(clip, current_activity)
            except Exception as error:
                result["error"] = error
            finally:
                completed.set()

        read_android_clipboard()
        if not completed.wait(5):
            raise TimeoutError("Android clipboard read timed out.")
        text = str(result["text"])
        if text:
            return text, "Android ClipboardManager"

        from kivy.core.clipboard import Clipboard

        fallback = Clipboard.paste()
        if isinstance(fallback, bytes):
            fallback = decode_text_bytes(fallback)
        if fallback:
            return fallback, "Kivy Clipboard fallback"
        if result["error"] is not None:
            raise result["error"]
        return "", "Android ClipboardManager"

    from kivy.core.clipboard import Clipboard

    value = Clipboard.paste()
    if isinstance(value, bytes):
        return decode_text_bytes(value), "Desktop Clipboard"
    return value or "", "Desktop Clipboard"
