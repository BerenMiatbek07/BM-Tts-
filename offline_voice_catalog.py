"""Downloadable Sherpa/Piper voice catalog for BM Text to Voice.

The application exposes every ``vits-piper-*.tar.bz2`` asset published in the
official sherpa-onnx ``tts-models`` release.  A small fallback list keeps the
most useful voices visible when GitHub is unavailable.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

GITHUB_RELEASE_API = (
    "https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/tts-models"
)
DIRECT_DOWNLOAD_ROOT = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"
)
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
CATALOG_SCHEMA = 5

QUALITY_ORDER = {"x_low": 0, "low": 1, "medium": 2, "high": 3, "standard": 4}
PRECISION_ORDER = {"fp32": 0, "": 0, "fp16": 1, "int8": 2}
QUALITY_LABELS = {
    "x_low": "X-Low",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "standard": "Standard",
}

# These are also used when the official API is temporarily unavailable.
# All names follow the official tts-models release convention.
FALLBACK_MODEL_IDS = (
    # Official Kazakh assets. FP16 Piper exports are deliberately omitted:
    # sherpa-onnx's Android CPUExecutionProvider supports com.microsoft.Gelu
    # only for tensor(float), while these models contain tensor(float16).
    "vits-piper-kk_KZ-iseke-x_low",
    "vits-piper-kk_KZ-iseke-x_low-int8",
    "vits-piper-kk_KZ-issai-high",
    "vits-piper-kk_KZ-issai-high-int8",
    "vits-piper-kk_KZ-raya-x_low",
    "vits-piper-kk_KZ-raya-x_low-int8",
    "vits-piper-ru_RU-denis-medium",
    "vits-piper-ru_RU-dmitri-medium",
    "vits-piper-ru_RU-irina-medium",
    "vits-piper-ru_RU-ruslan-medium",
    "vits-piper-en_US-amy-medium",
    "vits-piper-en_US-lessac-medium",
    "vits-piper-en_US-ryan-high",
    "vits-piper-en_GB-alba-medium",
    "vits-piper-es_ES-davefx-medium",
    "vits-piper-es_ES-sharvard-medium",
    "vits-piper-de_DE-eva_k-x_low",
    "vits-piper-de_DE-thorsten-high",
    "vits-piper-fr_FR-siwis-medium",
    "vits-piper-fr_FR-upmc-medium",
    "vits-piper-pt_BR-faber-medium",
    "vits-piper-tr_TR-dfki-medium",
    "vits-piper-uk_UA-lada-x_low",
)

_MODEL_RE = re.compile(
    r"^(?P<prefix>vits-piper)-"
    r"(?P<locale>[A-Za-z]{2,3}(?:_[A-Za-z0-9]{2,4})?)-"
    r"(?P<tail>.+)$"
)
_QUALITY_SUFFIX_RE = re.compile(r"^(?P<name>.+)-(?P<quality>x_low|low|medium|high)$")
_PRECISION_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?:-(?P<precision>fp16|int8|fp32))?$")


def human_size(size: int | float | None) -> str:
    value = float(size or 0)
    if value <= 0:
        return "вЂ”"
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return "вЂ”"


def _pretty_name(name: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[_-]+", name) if part)


def parse_model_id(
    model_id: str,
    *,
    size: int = 0,
    url: str = "",
    sha256: str = "",
) -> dict[str, Any] | None:
    match = _MODEL_RE.match(model_id)
    if not match:
        return None
    locale = match.group("locale")
    language = locale.split("_", 1)[0].lower()
    tail = match.group("tail")
    precision_match = _PRECISION_SUFFIX_RE.match(tail)
    if not precision_match:
        return None
    base_tail = precision_match.group("base")
    precision = precision_match.group("precision") or ""
    quality_match = _QUALITY_SUFFIX_RE.match(base_tail)
    if quality_match:
        name = quality_match.group("name")
        quality = quality_match.group("quality")
    else:
        # A few official Piper archives (for example GLaDOS and Tjiho) do
        # not carry a low/medium/high suffix. They are still valid models.
        name = base_tail
        quality = "standard"
    archive_name = f"{model_id}.tar.bz2"
    return {
        "id": model_id,
        "engine": "sherpa",
        "language": language,
        "locale": locale,
        "name": name,
        "display_name": _pretty_name(name),
        "quality": quality,
        "quality_label": QUALITY_LABELS.get(quality, quality.title()),
        "precision": precision,
        "precision_label": precision.upper() if precision else "FP32",
        "size": int(size or 0),
        "url": url or f"{DIRECT_DOWNLOAD_ROOT}/{archive_name}",
        "archive_name": archive_name,
        "sha256": sha256 or "",
    }


def fallback_catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for model_id in FALLBACK_MODEL_IDS:
        model = parse_model_id(model_id)
        if model:
            result.append(model)
    return _sort_catalog(result)


def compatible_model_id(model_id: str) -> str:
    """Return the FP32 counterpart for an incompatible Android FP16 model."""

    value = str(model_id or "")
    return value[: -len("-fp16")] if value.endswith("-fp16") else value


def is_runtime_compatible_model(model: dict[str, Any]) -> bool:
    """Whether this Piper archive can run on the bundled Android CPU EP."""

    return str(model.get("precision") or "").lower() != "fp16"


def _sort_catalog(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    language_priority = {"kk": 0, "ru": 1, "en": 2}
    return sorted(
        (item for item in catalog if is_runtime_compatible_model(item)),
        key=lambda item: (
            language_priority.get(str(item.get("language")), 10),
            str(item.get("language", "")),
            str(item.get("locale", "")),
            str(item.get("display_name", "")),
            QUALITY_ORDER.get(str(item.get("quality", "")), 9),
            PRECISION_ORDER.get(str(item.get("precision", "")), 9),
        ),
    )


def _asset_to_model(asset: dict[str, Any]) -> dict[str, Any] | None:
    filename = str(asset.get("name") or "")
    if not filename.startswith("vits-piper-") or not filename.endswith(".tar.bz2"):
        return None
    model_id = filename[: -len(".tar.bz2")]
    digest = str(asset.get("digest") or "")
    sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    return parse_model_id(
        model_id,
        size=int(asset.get("size") or 0),
        url=str(asset.get("browser_download_url") or ""),
        sha256=sha256,
    )


def _request_json(url: str, *, timeout: tuple[int, int] = (10, 35)) -> Any:
    response = requests.get(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "BM-Text-to-Voice/5.6.2",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json(), response.headers


def fetch_official_catalog() -> list[dict[str, Any]]:
    """Fetch every official Piper archive from the paginated release assets API."""

    release, _headers = _request_json(GITHUB_RELEASE_API)
    assets_url = str(release.get("assets_url") or "")
    if not assets_url:
        raise RuntimeError("Official voice release did not provide assets_url")

    models: dict[str, dict[str, Any]] = {}
    page = 1
    while True:
        assets, _headers = _request_json(f"{assets_url}?per_page=100&page={page}")
        if not isinstance(assets, list):
            raise RuntimeError("Unexpected GitHub assets response")
        if not assets:
            break
        for asset in assets:
            model = _asset_to_model(asset)
            if model:
                models[str(model["id"])] = model
        if len(assets) < 100:
            break
        page += 1
        if page > 20:
            raise RuntimeError("Voice catalog pagination exceeded safety limit")

    # Merge known Kazakh/fallback IDs in case a transient GitHub API page omits
    # one asset. Remote metadata wins when available.
    for fallback in fallback_catalog():
        models.setdefault(str(fallback["id"]), fallback)
    if not models:
        raise RuntimeError("Official Piper catalog is empty")
    return _sort_catalog(list(models.values()))


def read_cached_catalog(cache_path: Path, *, allow_stale: bool = True) -> list[dict[str, Any]]:
    cache_path = Path(cache_path)
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if int(data.get("schema", 0)) != CATALOG_SCHEMA:
            return []
        created_at = float(data.get("created_at", 0))
        if not allow_stale and time.time() - created_at > CACHE_TTL_SECONDS:
            return []
        models = data.get("models")
        if not isinstance(models, list):
            return []
        return _sort_catalog([item for item in models if isinstance(item, dict)])
    except Exception:
        return []


def cache_is_fresh(cache_path: Path) -> bool:
    cache_path = Path(cache_path)
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return (
            int(data.get("schema", 0)) == CATALOG_SCHEMA
            and time.time() - float(data.get("created_at", 0)) <= CACHE_TTL_SECONDS
        )
    except Exception:
        return False


def write_catalog_cache(cache_path: Path, models: list[dict[str, Any]]) -> None:
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(
            {
                "schema": CATALOG_SCHEMA,
                "created_at": time.time(),
                "models": models,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temp.replace(cache_path)
