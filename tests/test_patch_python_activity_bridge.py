from pathlib import Path

from tools.patch_python_activity_bridge import METHODS, patch


def test_patcher_removes_retired_consent_apis_from_cached_activity(tmp_path: Path):
    java = tmp_path / "PythonActivity.java"
    java.write_text(
        """package org.kivy.android;
public class PythonActivity {
    public String prepareVoiceReference(String uri) {
        return "{\"ok\":false}";
    }

    public String evaluateVoiceConsent(String first, String second) {
        if (first != null) { return second; }
        return first;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
    }
}
""",
        encoding="utf-8",
    )

    patch(java)
    updated = java.read_text(encoding="utf-8")

    assert "prepareVoiceReference" not in updated
    assert "evaluateVoiceConsent" not in updated
    for method in METHODS:
        assert f" {method}(" in updated

    first = updated
    patch(java)
    assert java.read_text(encoding="utf-8") == first
