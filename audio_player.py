"""Platform audio playback used by the mobile review controls."""

from __future__ import annotations

from pathlib import Path

from kivy.core.audio import SoundLoader
from kivy.utils import platform


class MobileAudioPlayer:
    def __init__(self) -> None:
        self.path: Path | None = None
        self._android_player = None
        self._sound = None
        self._desktop_position = 0.0

    def load(self, path: Path) -> None:
        self.release()
        self.path = path.resolve()
        if platform == "android":
            from jnius import autoclass

            MediaPlayer = autoclass("android.media.MediaPlayer")
            self._android_player = MediaPlayer()
            self._android_player.setDataSource(str(self.path))
            self._android_player.prepare()
        else:
            self._sound = SoundLoader.load(str(self.path))
            if self._sound is None:
                raise RuntimeError("MP3 аудиосын ашу мүмкін болмады.")

    def play(self) -> None:
        if platform == "android":
            if self._android_player is None:
                raise RuntimeError("Аудио жүктелмеген.")
            if self._android_player.getCurrentPosition() >= self._android_player.getDuration() - 200:
                self._android_player.seekTo(0)
            self._android_player.start()
        else:
            if self._sound is None:
                raise RuntimeError("Аудио жүктелмеген.")
            self._sound.play()
            if self._desktop_position:
                self._sound.seek(self._desktop_position)

    def pause(self) -> None:
        if platform == "android":
            if self._android_player is not None and self._android_player.isPlaying():
                self._android_player.pause()
        elif self._sound is not None and self._sound.state == "play":
            self._desktop_position = max(0.0, self._sound.get_pos())
            self._sound.stop()

    def stop(self) -> None:
        if platform == "android":
            if self._android_player is not None:
                if self._android_player.isPlaying():
                    self._android_player.pause()
                self._android_player.seekTo(0)
        elif self._sound is not None:
            self._sound.stop()
            self._desktop_position = 0.0

    def seek_ms(self, milliseconds: int) -> None:
        target = max(0, min(int(milliseconds), self.duration_ms()))
        if platform == "android":
            if self._android_player is not None:
                self._android_player.seekTo(target)
        elif self._sound is not None:
            self._desktop_position = target / 1000
            self._sound.seek(self._desktop_position)

    def is_playing(self) -> bool:
        if platform == "android":
            return bool(self._android_player is not None and self._android_player.isPlaying())
        return bool(self._sound is not None and self._sound.state == "play")

    def position_ms(self) -> int:
        if platform == "android":
            return int(self._android_player.getCurrentPosition()) if self._android_player else 0
        if self._sound is None:
            return 0
        if self._sound.state == "play":
            return max(0, int(self._sound.get_pos() * 1000))
        return int(self._desktop_position * 1000)

    def duration_ms(self) -> int:
        if platform == "android":
            return int(self._android_player.getDuration()) if self._android_player else 0
        return max(0, int((self._sound.length if self._sound else 0) * 1000))

    def release(self) -> None:
        if self._android_player is not None:
            try:
                self._android_player.release()
            except Exception:
                pass
            self._android_player = None
        if self._sound is not None:
            try:
                self._sound.stop()
                self._sound.unload()
            except Exception:
                pass
            self._sound = None
        self.path = None
        self._desktop_position = 0.0
