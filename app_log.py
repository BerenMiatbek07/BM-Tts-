"""Private diagnostic logging and clipboard helpers."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from kivy.utils import platform


_logger = logging.getLogger("bm_text_to_voice")
_log_path: Path | None = None


def configure_logging(user_data_dir: str | Path) -> Path:
    global _log_path
    logs = Path(user_data_dir) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    _log_path = logs / "error.log"
    if not _logger.handlers:
        handler = logging.FileHandler(_log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
    return _log_path


def log_event(event: str, **values) -> None:
    details = " ".join(f"{key}={value!r}" for key, value in values.items())
    _logger.info("%s | %s", event, details)


def log_exception(context: str, error: BaseException) -> None:
    _logger.error(
        "%s | %s: %s\n%s",
        context,
        type(error).__name__,
        error,
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
    )


def log_path() -> Path | None:
    return _log_path


def copy_error_log() -> bool:
    if _log_path is None or not _log_path.exists():
        return False
    text = _log_path.read_text(encoding="utf-8", errors="replace")
    if platform == "android":
        from jnius import autoclass

        ClipData = autoclass("android.content.ClipData")
        Context = autoclass("android.content.Context")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        manager = activity.getSystemService(Context.CLIPBOARD_SERVICE)
        manager.setPrimaryClip(ClipData.newPlainText("BM error log", text))
        return True

    from kivy.core.clipboard import Clipboard

    Clipboard.copy(text)
    return True
