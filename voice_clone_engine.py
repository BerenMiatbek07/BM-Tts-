"""Verified local ZipVoice model and reference profile management.

The consent verifier and the synthesis model are intentionally separate.  A
verified live recording is retained only after the two-factor owner check has
passed and becomes the exact-text prompt used by ZipVoice.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from pathlib import Path
from typing import Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


MODEL_ARCHIVE = "sherpa-onnx-zipvoice-distill-int8-zh-en-emilia.tar.bz2"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
    + MODEL_ARCHIVE
)
MODEL_API_URL = (
    "https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/327320447"
)
MODEL_SIZE = 109_162_785
MODEL_SHA256 = "77219c8b40f4ee8d73a7f902305ff6c1128ef9b54461c41b4ca6ed890b6c2803"

VOCODER_FILE = "vocos_24khz.onnx"
VOCODER_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/"
    + VOCODER_FILE
)
VOCODER_API_URL = (
    "https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/assets/284752173"
)
VOCODER_SIZE = 54_157_409
VOCODER_SHA256 = "bcb3b970e384161c4d634f0bb9e999ff1c471b34c9bc0b1049a5014065ed3cc0"

REQUIRED_FILES = (
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "tokens.txt",
    "lexicon.txt",
)


class VoiceCloneModelError(RuntimeError):
    pass


class VoiceCloneModelCancelled(Exception):
    pass


ProgressCallback = Callable[[dict[str, object]], None]


def _sha256(path: Path, cancel_event=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            if cancel_event is not None and cancel_event.is_set():
                raise VoiceCloneModelCancelled()
            digest.update(block)
    return digest.hexdigest()


def _session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


class VoiceCloneModelManager:
    def __init__(self, user_data_dir: str | Path):
        self.root = Path(user_data_dir) / "voice_clone_engine"
        self.downloads = self.root / "downloads"
        self.models = self.root / "models"
        self.model_dir = self.models / "zipvoice-int8-zh-en"
        self.profile_dir = self.root / "profile"
        self.profile_wave = self.profile_dir / "verified_reference.wav"
        self.profile_manifest = self.profile_dir / "profile.json"
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.models.mkdir(parents=True, exist_ok=True)
        self._recover_interrupted_install()
        self._installed_state = self._model_folder_valid(self.model_dir)
        self._profile_cache_ready = False
        self._profile_cache: dict[str, object] | None = None
        self._profile_cache_fingerprint: tuple[int, int, int, int] | None = None

    def _model_folder_valid(self, folder: Path, *, full_hash: bool = False) -> bool:
        try:
            for name in REQUIRED_FILES:
                path = folder / name
                if not path.is_file() or path.stat().st_size <= 0:
                    return False
            data_dir = folder / "espeak-ng-data"
            vocoder = folder / VOCODER_FILE
            if not data_dir.is_dir() or not any(data_dir.iterdir()):
                return False
            if not vocoder.is_file() or vocoder.stat().st_size != VOCODER_SIZE:
                return False
            if full_hash and _sha256(vocoder) != VOCODER_SHA256:
                return False
            return True
        except OSError:
            return False

    def _recover_interrupted_install(self) -> None:
        """Keep a completed 156 MB clone model across process termination."""

        staging = self.models / ".clone_installing"
        if self._model_folder_valid(self.model_dir):
            shutil.rmtree(staging, ignore_errors=True)
            return
        if self._model_folder_valid(staging):
            shutil.rmtree(self.model_dir, ignore_errors=True)
            os.replace(staging, self.model_dir)

    def runtime_paths(self) -> dict[str, str]:
        if not self.is_installed():
            raise VoiceCloneModelError("clone_model_missing")
        profile = self.load_profile()
        if not profile:
            raise VoiceCloneModelError("clone_profile_missing")
        return {
            "model_dir": str(self.model_dir),
            "reference_wave": str(self.profile_wave),
            "reference_text": str(profile["reference_text"]),
            "language": str(profile.get("language") or "en"),
        }

    def is_installed(self, *, full_hash: bool = False) -> bool:
        if full_hash:
            self._installed_state = self._model_folder_valid(
                self.model_dir, full_hash=True
            )
        elif not self._installed_state and self.model_dir.is_dir():
            # Also supports tests, restores and files copied in by an Android
            # update after this manager instance was created.
            self._installed_state = self._model_folder_valid(self.model_dir)
        return self._installed_state

    def has_profile(self) -> bool:
        return bool(self.load_profile())

    def resumable_percent(self) -> int:
        """Return partial download progress saved in app-private storage."""
        if self.is_installed():
            return 100
        archive = self.downloads / (MODEL_ARCHIVE + ".part")
        vocoder = self.downloads / (VOCODER_FILE + ".part")
        model_done = min(MODEL_SIZE, archive.stat().st_size) if archive.is_file() else 0
        vocoder_done = min(VOCODER_SIZE, vocoder.stat().st_size) if vocoder.is_file() else 0
        return min(94, int((model_done + vocoder_done) * 94 / (MODEL_SIZE + VOCODER_SIZE)))

    def load_profile(self) -> dict[str, object] | None:
        fingerprint = self._profile_fingerprint()
        if self._profile_cache_ready and fingerprint == self._profile_cache_fingerprint:
            return dict(self._profile_cache) if self._profile_cache else None
        try:
            data = json.loads(self.profile_manifest.read_text(encoding="utf-8"))
            if (
                not self.profile_wave.is_file()
                or self.profile_wave.stat().st_size <= 44
                or not str(data.get("reference_text") or "").strip()
                # The bundled ZipVoice model is zh/en only. Older test builds
                # could save a Kazakh reference prompt; never reuse it because
                # its transcript cannot be parsed reliably by this model.
                or str(data.get("language") or "").lower() != "en"
                or _sha256(self.profile_wave) != str(data.get("wave_sha256") or "")
            ):
                self._profile_cache = None
            else:
                self._profile_cache = dict(data)
        except Exception:
            self._profile_cache = None
        self._profile_cache_ready = True
        self._profile_cache_fingerprint = fingerprint
        return dict(self._profile_cache) if self._profile_cache else None

    def _profile_fingerprint(self) -> tuple[int, int, int, int] | None:
        try:
            wave_stat = self.profile_wave.stat()
            manifest_stat = self.profile_manifest.stat()
            return (
                int(wave_stat.st_size),
                int(wave_stat.st_mtime_ns),
                int(manifest_stat.st_size),
                int(manifest_stat.st_mtime_ns),
            )
        except OSError:
            return None

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
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.profile_wave.with_suffix(".wav.tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, self.profile_wave)
        manifest = {
            "profile_version": 1,
            "created_at": time.time(),
            "language": str(language or "en").split("-", 1)[0],
            "reference_text": text,
            "wave_sha256": _sha256(self.profile_wave),
            "consent": dict(consent_receipt),
            "storage": "app_private",
        }
        temp_manifest = self.profile_manifest.with_suffix(".json.tmp")
        temp_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temp_manifest, self.profile_manifest)
        # Run the same language/hash validation on first use. This also keeps
        # unsupported legacy profiles from being exposed through the cache.
        self._profile_cache = None
        self._profile_cache_ready = False
        self._profile_cache_fingerprint = None
        return manifest

    def delete_profile(self) -> None:
        shutil.rmtree(self.profile_dir, ignore_errors=True)
        self._profile_cache = None
        self._profile_cache_ready = True
        self._profile_cache_fingerprint = None

    def _check_space(self) -> None:
        # Archive, extracted model, vocoder and extraction headroom.
        if shutil.disk_usage(self.root).free < 520 * 1024 * 1024:
            raise VoiceCloneModelError("clone_model_space_required")

    def install(self, *, progress: ProgressCallback | None = None, cancel_event=None) -> None:
        self._check_space()
        archive = self.downloads / (MODEL_ARCHIVE + ".part")
        vocoder = self.downloads / (VOCODER_FILE + ".part")
        total = MODEL_SIZE + VOCODER_SIZE
        self._download_sources(
            (MODEL_URL, MODEL_API_URL),
            archive,
            MODEL_SIZE,
            MODEL_SHA256,
            stage="model",
            progress=progress,
            cancel_event=cancel_event,
            offset=0,
            total=total,
        )
        self._download_sources(
            (VOCODER_URL, VOCODER_API_URL),
            vocoder,
            VOCODER_SIZE,
            VOCODER_SHA256,
            stage="vocoder",
            progress=progress,
            cancel_event=cancel_event,
            offset=MODEL_SIZE,
            total=total,
        )

        expanded = self.models / ".clone_expanded"
        staging = self.models / ".clone_installing"
        shutil.rmtree(expanded, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        expanded.mkdir(parents=True)
        try:
            if progress:
                progress({"stage": "extract", "percent": 96})
            self._extract_archive(archive, expanded)
            encoders = list(expanded.rglob("encoder.int8.onnx"))
            if len(encoders) != 1:
                raise VoiceCloneModelError("clone_archive_incomplete")
            source_root = encoders[0].parent
            for name in REQUIRED_FILES:
                if not (source_root / name).is_file():
                    raise VoiceCloneModelError("clone_archive_incomplete")
            if not (source_root / "espeak-ng-data").is_dir():
                raise VoiceCloneModelError("clone_archive_incomplete")
            source_root.replace(staging)
            shutil.copyfile(vocoder, staging / VOCODER_FILE)
            if progress:
                progress({"stage": "verify", "percent": 98})
            if self.model_dir.exists():
                shutil.rmtree(self.model_dir)
            staging.replace(self.model_dir)
            archive.unlink(missing_ok=True)
            vocoder.unlink(missing_ok=True)
            if not self.is_installed(full_hash=True):
                raise VoiceCloneModelError("clone_model_validation_failed")
            self._installed_state = True
            (self.model_dir / "bm_model.json").write_text(
                json.dumps(
                    {
                        "source": "k2-fsa/sherpa-onnx official releases",
                        "archive_sha256": MODEL_SHA256,
                        "vocoder_sha256": VOCODER_SHA256,
                        "installed_at": time.time(),
                        "languages": ["en", "zh"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            if progress:
                progress({"stage": "done", "percent": 100})
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(expanded, ignore_errors=True)

    @staticmethod
    def _extract_archive(archive: Path, destination: Path) -> None:
        try:
            from kivy.utils import platform
        except Exception:
            platform = "desktop"
        if platform == "android":
            from android_activity import get_bm_activity
            try:
                activity = get_bm_activity()
            except Exception as error:
                raise VoiceCloneModelError("clone_activity_missing") from error
            activity.extractTarBz2(str(archive), str(destination))
            return
        with tarfile.open(archive, "r:bz2") as source:
            destination_root = destination.resolve()
            for member in source.getmembers():
                target = (destination / member.name).resolve()
                if target != destination_root and destination_root not in target.parents:
                    raise VoiceCloneModelError("clone_archive_invalid")
                if member.issym() or member.islnk():
                    raise VoiceCloneModelError("clone_archive_invalid")
            source.extractall(destination)

    @classmethod
    def _download_sources(
        cls,
        urls: tuple[str, ...],
        partial: Path,
        expected_size: int,
        expected_sha256: str,
        **kwargs,
    ) -> None:
        last_error: Exception | None = None
        for url in urls:
            try:
                cls._download(url, partial, expected_size, expected_sha256, **kwargs)
                return
            except VoiceCloneModelCancelled:
                raise
            except Exception as error:
                last_error = error
        raise VoiceCloneModelError("clone_model_download_failed") from last_error

    @staticmethod
    def _download(
        url: str,
        partial: Path,
        expected_size: int,
        expected_sha256: str,
        *,
        stage: str,
        progress: ProgressCallback | None,
        cancel_event,
        offset: int,
        total: int,
    ) -> None:
        existing = partial.stat().st_size if partial.is_file() else 0
        if existing > expected_size:
            partial.unlink(missing_ok=True)
            existing = 0
        if existing == expected_size:
            if _sha256(partial, cancel_event) == expected_sha256:
                if progress:
                    progress({"stage": stage, "percent": min(94, int((offset + expected_size) * 94 / total))})
                return
            partial.unlink(missing_ok=True)
            existing = 0
        headers = {
            "User-Agent": "BM-Voice-Studio/5.6.2",
            "Accept-Encoding": "identity",
            "Accept": "application/octet-stream",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if existing:
            headers["Range"] = f"bytes={existing}-"
        session = _session()
        try:
            with session.get(url, headers=headers, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                append = response.status_code == 206 and existing > 0
                if append and not str(response.headers.get("Content-Range") or "").startswith(
                    f"bytes {existing}-"
                ):
                    raise VoiceCloneModelError("clone_resume_invalid")
                if not append:
                    existing = 0
                downloaded = existing
                with partial.open("ab" if append else "wb") as output:
                    for block in response.iter_content(256 * 1024):
                        if cancel_event is not None and cancel_event.is_set():
                            raise VoiceCloneModelCancelled()
                        if not block:
                            continue
                        output.write(block)
                        downloaded += len(block)
                        if progress:
                            progress(
                                {
                                    "stage": stage,
                                    "downloaded": offset + downloaded,
                                    "total": total,
                                    "percent": min(94, int((offset + downloaded) * 94 / total)),
                                }
                            )
                    output.flush()
                    os.fsync(output.fileno())
        except (VoiceCloneModelCancelled, VoiceCloneModelError):
            raise
        except Exception as error:
            raise VoiceCloneModelError("clone_model_download_failed") from error
        finally:
            session.close()
        if partial.stat().st_size != expected_size:
            raise VoiceCloneModelError("clone_model_size_failed")
        if _sha256(partial, cancel_event) != expected_sha256:
            partial.unlink(missing_ok=True)
            raise VoiceCloneModelError("clone_model_hash_failed")
