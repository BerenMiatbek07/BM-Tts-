"""Thread-safe access to the live Android activity.

Every Python-facing BM method is deliberately declared on the generated
``org.kivy.android.PythonActivity``.  That class remains visible when PyJNIus
attaches a worker thread; resolving/casting the app-specific subclass does not
on every OEM runtime.
"""

from __future__ import annotations


def get_bm_activity():
    from jnius import autoclass

    base_activity = autoclass("org.kivy.android.PythonActivity")
    current = base_activity.mActivity
    if current is None:
        raise RuntimeError("Android activity is unavailable")
    return current
