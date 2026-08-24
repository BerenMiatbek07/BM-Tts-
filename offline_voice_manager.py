"""Download, verify and install additional Sherpa/Piper voice models."""

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
from kivy.utils import platform


class ModelDownloadCancelled(Exception):
    pass


class ModelInstallError(RuntimeError):
    pass


ProgressCallback = Callable[[dict], None]


def _download_session() -> requests.Session:
    """HTTPS session with bounded retries for transient GitHub/CDN errors."""
    retry = Retry(total=4, connect=4, read=3, status=4, backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True, raise_on_status=False)
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    return session


def _friendly_download_error(error: Exception) -> str:
    text = str(error).strip() or type(error).__name__
    lowered = text.lower()
    if "name or service not known" in lowered or "temporary failure in name resolution" in lowered:
        return 'DNS сервері GitHub мекенжайын таба алмады. Желі немесе жеке DNS баптауын тексеріңіз.'
    if "ssl" in lowered or "certificate" in lowered:
        return 'HTTPS/SSL қосылымы ашылмады. Телефонның күні мен уақытын тексеріңіз.'
    if "timed out" in lowered or "timeout" in lowered:
        return 'Дауыс сервері уақытында жауап бермеді. Жүктеуді қайта жалғастырыңыз.'
    if "403" in lowered:
        return 'GitHub жүктеуге уақытша тыйым салды (HTTP 403). Біраздан соң жалғастырыңыз.'
    if "404" in lowered:
        return 'Бұл дауыс архиві серверден табылмады (HTTP 404). Каталогты жаңартыңыз.'
    if "429" in lowered:
        return 'Сервер сұрау лимитін уақытша шектеді (HTTP 429). Кейін жалғастырыңыз.'
    return text[:600]


class VoiceModelManager:
    def __init__(self, user_data_dir: str | Path):
        self.root = Path(user_data_dir) / "additional_voices"
        self.models_dir = self.root / "models"
        self.downloads_dir = self.root / "downloads"
        self.catalog_cache = self.root / "official_piper_catalog.json"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._recover_interrupted_installs()
        self._installed_cache: dict[str, Path] = {}
        self._installed_size_cache: dict[str, int] = {}
        self._rebuild_installed_cache()

    @staticmethod
    def _safe_id(model_id: str) -> str:
        if not model_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in model_id):
            raise ValueError("Invalid model id")
        return model_id

    def model_dir(self, model_id: str) -> Path:
        return self.models_dir / self._safe_id(model_id)

    def metadata_path(self, model_id: str) -> Path:
        return self.model_dir(model_id) / "bm_model.json"

    def partial_path(self, model_id: str) -> Path:
        return self.downloads_dir / f"{self._safe_id(model_id)}.tar.bz2.part"

    def archive_path(self, model_id: str) -> Path:
        return self.downloads_dir / f"{self._safe_id(model_id)}.tar.bz2"

    def is_installed(self, model_id: str) -> bool:
        return self._safe_id(model_id) in self._installed_cache

    @staticmethod
    def _is_valid_model_folder(folder: Path) -> bool:
        if not folder.is_dir():
            return False
        try:
            onnx = [path for path in folder.rglob("*.onnx") if path.is_file()]
            tokens = [path for path in folder.rglob("tokens.txt") if path.is_file()]
            return bool(onnx and tokens and max(path.stat().st_size for path in onnx) >= 1024 * 1024 and max(path.stat().st_size for path in tokens) > 0)
        except OSError:
            return False

    def _recover_interrupted_installs(self) -> None:
        if not self.models_dir.is_dir(): return
        for staging in tuple(self.models_dir.iterdir()):
            if not staging.is_dir() or not staging.name.startswith("."): continue
            model_id = ""
            if staging.name.endswith(".installing"): model_id = staging.name[1:-len(".installing")]
            elif staging.name.endswith(".normalized"): model_id = staging.name[1:-len(".normalized")]
            if not model_id: continue
            try: model_id = self._safe_id(model_id)
            except ValueError: continue
            final = self.models_dir / model_id
            if self._is_valid_model_folder(final):
                shutil.rmtree(staging, ignore_errors=True); continue
            if self._is_valid_model_folder(staging):
                shutil.rmtree(final, ignore_errors=True); os.replace(staging, final)

    def _rebuild_installed_cache(self) -> None:
        self._installed_cache.clear(); self._installed_size_cache.clear()
        if not self.models_dir.is_dir(): return
        for folder in self.models_dir.iterdir():
            if folder.is_dir() and not folder.name.startswith(".") and self._is_valid_model_folder(folder):
                self._installed_cache[folder.name] = folder

    def refresh_install_state(self, model_id: str) -> bool:
        model_id = self._safe_id(model_id); folder = self.models_dir / model_id
        valid = self._is_valid_model_folder(folder)
        if valid: self._installed_cache[model_id] = folder
        else: self._installed_cache.pop(model_id, None)
        self._installed_size_cache.pop(model_id, None); return valid

    def installed_catalog(self) -> list[dict]:
        result: list[dict] = []
        for model_id in sorted(self.installed_model_ids()):
            metadata = self.model_metadata(model_id)
            if not metadata:
                try:
                    from offline_voice_catalog import parse_model_id
                    metadata = parse_model_id(model_id) or {}
                except Exception: metadata = {}
            if metadata:
                metadata = dict(metadata); metadata["id"] = model_id; result.append(metadata)
        return result

    def has_partial(self, model_id: str) -> bool:
        path = self.partial_path(model_id); return path.exists() and path.stat().st_size > 0

    def installed_size(self, model_id: str) -> int:
        model_id = self._safe_id(model_id)
        if model_id in self._installed_size_cache: return self._installed_size_cache[model_id]
        folder = self._installed_cache.get(model_id)
        if folder is None: return 0
        size = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
        self._installed_size_cache[model_id] = size; return size

    def installed_model_ids(self) -> set[str]: return set(self._installed_cache)

    def model_metadata(self, model_id: str) -> dict:
        try: return json.loads(self.metadata_path(model_id).read_text(encoding="utf-8"))
        except Exception: return {}

    def remove(self, model_id: str, *, remove_partial: bool = True) -> None:
        model_id = self._safe_id(model_id); shutil.rmtree(self.model_dir(model_id), ignore_errors=True)
        self._installed_cache.pop(model_id, None); self._installed_size_cache.pop(model_id, None)
        if remove_partial:
            self.partial_path(model_id).unlink(missing_ok=True); self.archive_path(model_id).unlink(missing_ok=True)

    @staticmethod
    def _sha256(path: Path, cancel_event=None) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while True:
                if cancel_event is not None and cancel_event.is_set(): raise ModelDownloadCancelled()
                chunk = source.read(1024 * 1024)
                if not chunk: break
                digest.update(chunk)
        return digest.hexdigest()

    def _check_free_space(self, expected_size: int, current_size: int = 0) -> None:
        free = shutil.disk_usage(self.root).free; remaining = max(0, expected_size - current_size)
        needed = int(remaining + max(expected_size * 1.6, 64 * 1024 * 1024))
        if expected_size > 0 and free < needed:
            raise ModelInstallError(f"Телефон жадында орын жеткіліксіз. Кемінде {needed // (1024 * 1024)} MB босатыңыз.")

    def download_and_install(self, model: dict, *, progress: ProgressCallback | None = None, cancel_event=None) -> Path:
        model_id = self._safe_id(str(model.get("id") or "")); url = str(model.get("url") or "")
        if not url.startswith("https://"): raise ModelInstallError('Дауыс моделінің сілтемесі жарамсыз.')
        expected_size = int(model.get("size") or 0); expected_sha = str(model.get("sha256") or "").lower().strip()
        auto_retry = int(model.get("_bm_download_attempt", 0) or 0); partial = self.partial_path(model_id); archive = self.archive_path(model_id)
        existing = partial.stat().st_size if partial.exists() else 0
        if expected_size and existing > expected_size: partial.unlink(missing_ok=True); existing = 0
        self._check_free_space(expected_size, existing)
        headers = {"User-Agent": "BM-Text-to-Voice/5.6.2", "Accept-Encoding": "identity"}
        if existing > 0: headers["Range"] = f"bytes={existing}-"
        started = time.monotonic(); downloaded = existing; session = _download_session()
        try:
            with session.get(url, headers=headers, stream=True, timeout=(15, 90)) as response:
                if response.status_code == 416 and expected_size and existing == expected_size: pass
                else:
                    response.raise_for_status(); append = response.status_code == 206 and existing > 0
                    if append:
                        content_range = str(response.headers.get("Content-Range") or "")
                        if not content_range.startswith(f"bytes {existing}-"): raise ModelInstallError('Сервер жүктеуді дұрыс жерден жалғастырмады. Қайта бастаңыз.')
                    if not append: existing = 0; downloaded = 0
                    content_length = int(response.headers.get("Content-Length") or 0); total = expected_size or (existing + content_length if content_length else 0)
                    with partial.open("ab" if append else "wb") as destination:
                        for chunk in response.iter_content(chunk_size=256 * 1024):
                            if cancel_event is not None and cancel_event.is_set(): raise ModelDownloadCancelled()
                            if not chunk: continue
                            destination.write(chunk); downloaded += len(chunk); elapsed = max(0.1, time.monotonic() - started)
                            if progress: progress({"stage": "download", "downloaded": downloaded, "total": total, "percent": int(downloaded * 100 / total) if total else 0, "bytes_per_second": int(max(0, downloaded - existing) / elapsed)})
                        destination.flush(); os.fsync(destination.fileno())
        except ModelDownloadCancelled: raise
        except Exception as error:
            if isinstance(error, ModelInstallError): raise
            if auto_retry < 5 and partial.exists() and partial.stat().st_size > 0:
                retry_model = dict(model); retry_model["_bm_download_attempt"] = auto_retry + 1; time.sleep(min(8.0, 0.8 * (auto_retry + 1)))
                return self.download_and_install(retry_model, progress=progress, cancel_event=cancel_event)
            raise ModelInstallError(f"Дауыс жүктелмеді: {_friendly_download_error(error)}") from error
        finally: session.close()
        if expected_size and partial.stat().st_size != expected_size:
            if auto_retry < 5 and partial.exists() and partial.stat().st_size > 0:
                retry_model = dict(model); retry_model["_bm_download_attempt"] = auto_retry + 1; time.sleep(min(8.0, 0.8 * (auto_retry + 1)))
                return self.download_and_install(retry_model, progress=progress, cancel_event=cancel_event)
            raise ModelInstallError(f"Жүктелген файл толық емес: {partial.stat().st_size}/{expected_size} байт.")
        if progress: progress({"stage": "verify", "percent": 100, "downloaded": partial.stat().st_size, "total": expected_size})
        if expected_sha and self._sha256(partial, cancel_event).lower() != expected_sha:
            partial.unlink(missing_ok=True); raise ModelInstallError('Дауыс архивінің SHA-256 тексерісі өтпеді.')
        partial.replace(archive); staging = self.models_dir / f".{model_id}.installing"; final = self.model_dir(model_id)
        shutil.rmtree(staging, ignore_errors=True); staging.mkdir(parents=True, exist_ok=True)
        try:
            if progress: progress({"stage": "extract", "percent": 100, "downloaded": archive.stat().st_size, "total": expected_size})
            self._extract_archive(archive, staging); model_root = self._locate_model_root(staging)
            if model_root != staging:
                normalized = self.models_dir / f".{model_id}.normalized"; shutil.rmtree(normalized, ignore_errors=True); model_root.replace(normalized); shutil.rmtree(staging, ignore_errors=True); staging = normalized
            self._validate_model(staging); metadata = dict(model)
            metadata.update({"installed_at": time.time(), "archive_sha256": self._sha256(archive, cancel_event), "installed_size": sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())})
            (staging / "bm_model.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            shutil.rmtree(final, ignore_errors=True); staging.replace(final); self.refresh_install_state(model_id)
        except ModelDownloadCancelled: shutil.rmtree(staging, ignore_errors=True); raise
        except Exception as error:
            shutil.rmtree(staging, ignore_errors=True)
            if isinstance(error, ModelInstallError): raise
            raise ModelInstallError(f"Дауыс орнатылмады: {error}") from error
        finally: archive.unlink(missing_ok=True)
        if progress: progress({"stage": "done", "percent": 100, "downloaded": expected_size, "total": expected_size})
        return final

    def _extract_archive(self, archive: Path, destination: Path) -> None:
        if platform == "android":
            bridge_errors: list[str] = []
            try:
                from android_activity import get_bm_activity
                activity = get_bm_activity(); activity.extractTarBz2(str(archive), str(destination)); return
            except Exception as error: bridge_errors.append(f"PythonActivity bridge: {error}")
            try: self._extract_archive_with_tarfile(archive, destination); return
            except Exception as error: bridge_errors.append(f"Python tarfile: {error}")
            details = " | ".join(bridge_errors[-3:])
            raise ModelInstallError('APK ішіндегі архив орнату модулі ашылмады. Қолданбаны жаңа нұсқамен қайта орнатыңыз. ' f"Техникалық мәлімет: {details}")
        self._extract_archive_with_tarfile(archive, destination)

    @staticmethod
    def _extract_archive_with_tarfile(archive: Path, destination: Path) -> None:
        with tarfile.open(archive, mode="r:bz2") as tar:
            destination_resolved = destination.resolve()
            for member in tar.getmembers():
                target = (destination / member.name).resolve()
                if destination_resolved not in target.parents and target != destination_resolved: raise ModelInstallError("Archive path traversal rejected")
                if member.issym() or member.islnk(): raise ModelInstallError("Archive links are not allowed")
            tar.extractall(destination)

    @staticmethod
    def _locate_model_root(staging: Path) -> Path:
        if any(staging.glob("*.onnx")): return staging
        candidates = [folder for folder in staging.iterdir() if folder.is_dir() and any(folder.rglob("*.onnx"))]
        if len(candidates) == 1: return candidates[0]
        return staging

    @staticmethod
    def _validate_model(folder: Path) -> None:
        onnx = list(folder.rglob("*.onnx")); tokens = list(folder.rglob("tokens.txt"))
        if not onnx or not tokens: raise ModelInstallError('Архив ішінде ONNX моделі немесе tokens.txt жоқ.')
        if max(path.stat().st_size for path in onnx) < 1024 * 1024: raise ModelInstallError('ONNX моделі тым кішкентай немесе бүлінген.')
