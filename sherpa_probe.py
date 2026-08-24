"""Runtime diagnostics for the Android Sherpa/Piper engine."""

from __future__ import annotations

from kivy.utils import platform


def sherpa_runtime_diagnostic() -> tuple[bool, str]:
    """Check bridge, Kotlin stdlib and Sherpa JNI without loading a model."""

    if platform != "android":
        return False, "SHERPA_RUNTIME_ERROR:not-android"
    try:
        from android_activity import get_bm_activity

        activity = get_bm_activity()
        result = str(activity.sherpaRuntimeProbe())
        return result.startswith("SHERPA_RUNTIME_OK"), result
    except Exception as error:
        return False, f"SHERPA_RUNTIME_ERROR:{type(error).__name__}:{error}"


def sherpa_engine_available() -> bool:
    return sherpa_runtime_diagnostic()[0]
