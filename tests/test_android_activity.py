from __future__ import annotations

import sys
import types

from android_activity import get_bm_activity


def test_live_base_activity_is_returned_without_worker_thread_cast(monkeypatch):
    current = object()
    base = types.SimpleNamespace(mActivity=current)

    def autoclass(name):
        assert name == "org.kivy.android.PythonActivity"
        return base

    monkeypatch.setitem(
        sys.modules,
        "jnius",
        types.SimpleNamespace(autoclass=autoclass),
    )

    assert get_bm_activity() is current
