"""Render the voice-consent popup for deterministic desktop visual QA."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("BM_DESKTOP_WIDTH", "430")
os.environ.setdefault("BM_DESKTOP_HEIGHT", "860")
os.environ.setdefault("KIVY_NO_CONFIG", "1")
os.environ.setdefault("KIVY_HOME", str(Path(__file__).resolve().parent / ".kivy_qa"))

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import BMVoiceMobileApp
from kivy.clock import Clock
from kivy.core.window import Window


class ConsentRenderApp(BMVoiceMobileApp):
    def on_start(self) -> None:
        self.apply_ui_language("kk")
        Clock.schedule_once(lambda _dt: self._open_voice_clone_popup(), 0.25)
        Clock.schedule_once(self._capture, 1.0)
        Clock.schedule_once(lambda _dt: self.stop(), 1.35)

    def _capture(self, _dt=0) -> None:
        output = ROOT / "qa" / "voice_consent_ui.png"
        print(f"VOICE_CONSENT_WINDOW={Window.size} pos={Window.left},{Window.top}")
        try:
            import ctypes
            import ctypes.wintypes
            from PIL import ImageGrab

            handle = ctypes.windll.user32.GetForegroundWindow()
            rectangle = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(rectangle))
            ImageGrab.grab(
                bbox=(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom),
                all_screens=True,
            ).save(output)
        except Exception:
            Window.screenshot(name=str(output))
        print(f"VOICE_CONSENT_UI={output}")


if __name__ == "__main__":
    ConsentRenderApp().run()
