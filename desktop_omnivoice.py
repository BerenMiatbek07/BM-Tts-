"""Personal-use OmniVoice runtime for native Kazakh voice cloning on Windows."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from sherpa_generation import verify_wav_file
from voice_clone_engine import VoiceCloneModelCancelled, VoiceCloneModelError, _sha256


REPO_ID = "k2-fsa/OmniVoice"
REPO_REVISION = "c5fdb5ccb189668d56333f77ba2629f4cd7535f4"
REQUIRED_MODEL_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "audio_tokenizer/config.json",
    "audio_tokenizer/model.safetensors",
)


class DesktopOmniVoiceModelManager:
    """Keeps the large personal-use model outside the EXE across restarts."""

    def __init__(self, user_data_dir: str | Path):
        self.root = Path(user_data_dir) / "omnivoice_personal"
        self.model_dir = self.root / "model"
        self.profile_dir = self.root / "profile"
        self.profile_wave = self.profile_dir / "verified_reference.wav"
        self.profile_manifest = self.profile_dir / "profile.json"
        self.root.mkdir(parents=True, exist_ok=True)

    def is_installed(self, *, full_hash: bool = False) -> bool:
        del full_hash
        try:
            return all(
                (self.model_dir / name).is_file()
                and (self.model_dir / name).stat().st_size > 0
                for name in REQUIRED_MODEL_FILES
            )
        except OSError:
            return False

    def resumable_percent(self) -> int:
        return 100 if self.is_installed() else 0

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
        text = str(reference_text or "").strip()
        if not source.is_file() or source.stat().st_size <= 44 or not text:
            raise VoiceCloneModelError("clone_profile_invalid")
        lang = str(language or "kk").split("-", 1)[0].lower()
        if lang not in {"kk", "en", "ru"}:
            lang = "kk"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.profile_wave.with_suffix(".wav.tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, self.profile_wave)
        self.profile_wave.with_suffix(".omnivoice.pt").unlink(missing_ok=True)
        data = {
            "profile_version": 3,
            "engine": "omnivoice-personal",
            "created_at": time.time(),
            "language": lang,
            "reference_text": text,
            "wave_sha256": _sha256(self.profile_wave),
            "consent": dict(consent_receipt),
            "storage": "app_private_persistent",
        }
        temp_manifest = self.profile_manifest.with_suffix(".json.tmp")
        temp_manifest.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp_manifest, self.profile_manifest)
        return data

    def delete_profile(self) -> None:
        shutil.rmtree(self.profile_dir, ignore_errors=True)

    def runtime_paths(self) -> dict[str, str]:
        if not self.is_installed():
            raise VoiceCloneModelError("clone_model_missing")
        profile = self.load_profile()
        if not profile:
            raise VoiceCloneModelError("clone_profile_missing")
        return {
            "engine": "omnivoice-personal",
            "model_dir": str(self.model_dir),
            "reference_wave": str(self.profile_wave),
            "reference_text": str(profile["reference_text"]),
            "language": str(profile.get("language") or "kk"),
        }

    def install(self, *, progress=None, cancel_event=None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise VoiceCloneModelCancelled()
        if shutil.disk_usage(self.root).free < 6 * 1024 * 1024 * 1024:
            raise VoiceCloneModelError("clone_model_space_required")
        if progress:
            progress({"stage": "download", "percent": 1})
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=REPO_ID,
                revision=REPO_REVISION,
                local_dir=str(self.model_dir),
                allow_patterns=[
                    "*.json",
                    "*.jinja",
                    "*.safetensors",
                    "audio_tokenizer/*",
                ],
                max_workers=4,
            )
        except Exception as error:
            raise VoiceCloneModelError("clone_model_download_failed") from error
        if cancel_event is not None and cancel_event.is_set():
            raise VoiceCloneModelCancelled()
        if progress:
            progress({"stage": "verify", "percent": 98})
        if not self.is_installed():
            raise VoiceCloneModelError("clone_model_validation_failed")
        (self.model_dir / "bm_model.json").write_text(
            json.dumps(
                {
                    "repo": REPO_ID,
                    "revision": REPO_REVISION,
                    "mode": "personal_noncommercial",
                    "installed_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if progress:
            progress({"stage": "done", "percent": 100})


class DesktopOmniVoiceEngine:
    def __init__(self, model_dir: str | Path):
        import torch
        from omnivoice import OmniVoice

        self.torch = torch
        if torch.cuda.is_available():
            self.device = "cuda:0"
            self.dtype = torch.float16
        else:
            self.device = "cpu"
            self.dtype = torch.float32
        self.model = OmniVoice.from_pretrained(
            str(Path(model_dir)), device_map=self.device, dtype=self.dtype
        )
        self._prompt_key: tuple[str, int, int, str] | None = None
        self._prompt = None

    def _voice_prompt(self, reference_wave: Path, reference_text: str):
        from omnivoice import VoiceClonePrompt

        stat = reference_wave.stat()
        key = (
            str(reference_wave.resolve()),
            stat.st_size,
            stat.st_mtime_ns,
            reference_text,
        )
        if self._prompt_key != key or self._prompt is None:
            cache = reference_wave.with_suffix(".omnivoice.pt")
            if cache.is_file() and cache.stat().st_mtime_ns >= stat.st_mtime_ns:
                self._prompt = VoiceClonePrompt.load(str(cache))
            else:
                self._prompt = self.model.create_voice_clone_prompt(
                    ref_audio=str(reference_wave), ref_text=reference_text
                )
                temporary = cache.with_suffix(".pt.tmp")
                self._prompt.save(str(temporary))
                os.replace(temporary, cache)
            self._prompt_key = key
        return self._prompt

    def synthesize(
        self,
        *,
        text: str,
        reference_wave: str | Path,
        reference_text: str,
        language: str,
        rate: int,
        volume: int,
        output_path: str | Path,
    ) -> Path:
        import numpy as np
        import soundfile as sf

        language_code = str(language or "kk").split("-", 1)[0].lower()
        if language_code not in {"kk", "ru", "en"}:
            language_code = "kk"
        speed = max(0.5, min(2.0, 1.0 + int(rate) / 100.0))
        prompt = self._voice_prompt(Path(reference_wave), reference_text)
        parts = self.model.generate(
            text=text,
            language=language_code,
            voice_clone_prompt=prompt,
            num_step=16,
            speed=speed,
        )
        audio = np.concatenate([np.asarray(part, dtype=np.float32) for part in parts])
        gain = max(0.0, 1.0 + int(volume) / 100.0)
        audio = np.clip(audio * gain, -1.0, 1.0)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        sf.write(str(output), audio, 24_000, subtype="PCM_16")
        if not verify_wav_file(output):
            raise RuntimeError("OmniVoice produced an invalid WAV file")
        return output


_ENGINE: DesktopOmniVoiceEngine | None = None
_ENGINE_DIR = ""


def get_desktop_omnivoice_engine(model_dir: str | Path) -> DesktopOmniVoiceEngine:
    global _ENGINE, _ENGINE_DIR
    key = str(Path(model_dir).resolve())
    if _ENGINE is None or _ENGINE_DIR != key:
        _ENGINE = DesktopOmniVoiceEngine(key)
        _ENGINE_DIR = key
    return _ENGINE
