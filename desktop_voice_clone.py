"""Persistent OpenVoice V2 model/profile management for Windows."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from voice_clone_engine import (
    VoiceCloneModelCancelled,
    VoiceCloneModelError,
    VoiceCloneModelManager,
    _sha256,
)


MODEL_NAME = "OpenVoice V2 tone-color converter"
MODEL_URL = (
    "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/main/"
    "converter/checkpoint.pth?download=true"
)
MODEL_FILE = "checkpoint.pth"
MODEL_SIZE = 131_320_490
MODEL_SHA256 = "9652c27e92b6b2a91632590ac9962ef7ae2b712e5c5b7f4c34ec55ee2b37ab9e"
CONFIG_URL = (
    "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/main/"
    "converter/config.json?download=true"
)
CONFIG_FILE = "config.json"
CONFIG_SIZE = 838
CONFIG_SHA256 = "9dfff60350b8c63f2c664efd92a61b2516efb22671466960f0e5dfebd881fa47"

ProgressCallback = Callable[[dict[str, object]], None]


class DesktopVoiceCloneModelManager:
    """Download once and preserve the PC clone model and consent profile."""

    def __init__(self, user_data_dir: str | Path):
        self.root = Path(user_data_dir) / "voice_clone_engine_pc"
        self.downloads = self.root / "downloads"
        self.models = self.root / "models"
        self.model_dir = self.models / "openvoice-v2"
        self.profile_dir = self.root / "profile"
        self.profile_wave = self.profile_dir / "verified_reference.wav"
        self.profile_manifest = self.profile_dir / "profile.json"
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.models.mkdir(parents=True, exist_ok=True)
        self._installed_state = self._model_folder_valid(self.model_dir)

    @staticmethod
    def _model_folder_valid(folder: Path, *, full_hash: bool = False) -> bool:
        try:
            checkpoint = folder / MODEL_FILE
            config = folder / CONFIG_FILE
            if checkpoint.stat().st_size != MODEL_SIZE or config.stat().st_size != CONFIG_SIZE:
                return False
            if full_hash:
                return (
                    _sha256(checkpoint) == MODEL_SHA256
                    and _sha256(config) == CONFIG_SHA256
                )
            return True
        except OSError:
            return False

    def is_installed(self, *, full_hash: bool = False) -> bool:
        if full_hash or (not self._installed_state and self.model_dir.is_dir()):
            self._installed_state = self._model_folder_valid(
                self.model_dir, full_hash=full_hash
            )
        return self._installed_state

    def resumable_percent(self) -> int:
        if self.is_installed():
            return 100
        partial = self.downloads / f"{MODEL_FILE}.part"
        done = min(MODEL_SIZE, partial.stat().st_size) if partial.is_file() else 0
        return min(94, int(done * 94 / MODEL_SIZE))

    def load_profile(self) -> dict[str, object] | None:
        try:
            data = json.loads(self.profile_manifest.read_text(encoding="utf-8"))
            if (
                self.profile_wave.stat().st_size <= 44
                or not str(data.get("reference_text") or "").strip()
                or str(data.get("language") or "") not in {"kk", "en", "ru"}
                or _sha256(self.profile_wave) != str(data.get("wave_sha256") or "")
            ):
                return None
            return data
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def has_profile(self) -> bool:
        return self.load_profile() is not None

    def save_verified_profile(
        self,
        live_wave: str | Path,
        *,
        reference_text: str,
        language: str,
        consent_receipt: dict[str, object],
    ) -> dict[str, object]:
        source = Path(live_wave)
        if not source.is_file() or source.stat().st_size <= 44:
            raise VoiceCloneModelError("clone_profile_wave_invalid")
        text = str(reference_text or "").strip()
        if not text:
            raise VoiceCloneModelError("clone_profile_text_missing")
        lang = str(language or "kk").split("-", 1)[0].lower()
        if lang not in {"kk", "en", "ru"}:
            lang = "kk"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.profile_wave.with_suffix(".wav.tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, self.profile_wave)
        manifest = {
            "profile_version": 2,
            "engine": "openvoice-v2",
            "created_at": time.time(),
            "language": lang,
            "reference_text": text,
            "wave_sha256": _sha256(self.profile_wave),
            "consent": dict(consent_receipt),
            "storage": "app_private_persistent",
        }
        temporary_manifest = self.profile_manifest.with_suffix(".json.tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary_manifest, self.profile_manifest)
        return manifest

    def delete_profile(self) -> None:
        shutil.rmtree(self.profile_dir, ignore_errors=True)

    def runtime_paths(self) -> dict[str, str]:
        if not self.is_installed():
            raise VoiceCloneModelError("clone_model_missing")
        profile = self.load_profile()
        if not profile:
            raise VoiceCloneModelError("clone_profile_missing")
        return {
            "engine": "openvoice-v2",
            "model_dir": str(self.model_dir),
            "reference_wave": str(self.profile_wave),
            "reference_text": str(profile["reference_text"]),
            "language": str(profile.get("language") or "kk"),
        }

    def install(self, *, progress: ProgressCallback | None = None, cancel_event=None) -> None:
        if shutil.disk_usage(self.root).free < 420 * 1024 * 1024:
            raise VoiceCloneModelError("clone_model_space_required")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_part = self.downloads / f"{MODEL_FILE}.part"
        config_part = self.downloads / f"{CONFIG_FILE}.part"
        VoiceCloneModelManager._download(
            MODEL_URL,
            checkpoint_part,
            MODEL_SIZE,
            MODEL_SHA256,
            stage="model",
            progress=progress,
            cancel_event=cancel_event,
            offset=0,
            total=MODEL_SIZE + CONFIG_SIZE,
        )
        VoiceCloneModelManager._download(
            CONFIG_URL,
            config_part,
            CONFIG_SIZE,
            CONFIG_SHA256,
            stage="config",
            progress=progress,
            cancel_event=cancel_event,
            offset=MODEL_SIZE,
            total=MODEL_SIZE + CONFIG_SIZE,
        )
        if progress:
            progress({"stage": "verify", "percent": 98})
        os.replace(checkpoint_part, self.model_dir / MODEL_FILE)
        os.replace(config_part, self.model_dir / CONFIG_FILE)
        if not self._model_folder_valid(self.model_dir, full_hash=True):
            self._installed_state = False
            raise VoiceCloneModelError("clone_model_validation_failed")
        self._installed_state = True
        (self.model_dir / "bm_model.json").write_text(
            json.dumps(
                {
                    "name": MODEL_NAME,
                    "source": "myshell-ai/OpenVoiceV2",
                    "checkpoint_sha256": MODEL_SHA256,
                    "installed_at": time.time(),
                    "bm_languages": ["kk", "en", "ru"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if progress:
            progress({"stage": "done", "percent": 100})


__all__ = [
    "DesktopVoiceCloneModelManager",
    "VoiceCloneModelCancelled",
    "VoiceCloneModelError",
]
