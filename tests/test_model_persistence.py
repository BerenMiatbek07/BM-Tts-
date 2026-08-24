from pathlib import Path

from offline_voice_manager import VoiceModelManager
from voice_clone_engine import REQUIRED_FILES, VOCODER_FILE, VOCODER_SIZE, VoiceCloneModelManager


def _write_sparse(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.seek(size - 1)
        output.write(b"\0")


def test_piper_install_is_recovered_after_process_kill(tmp_path: Path) -> None:
    root = tmp_path / "additional_voices" / "models"
    model_id = "vits-piper-kk_KZ-iseke-x_low"
    staging = root / f".{model_id}.installing"
    _write_sparse(staging / "iseke.onnx", 1024 * 1024)
    (staging / "tokens.txt").write_text("a 1\n", encoding="utf-8")

    manager = VoiceModelManager(tmp_path)

    assert manager.is_installed(model_id)
    assert not staging.exists()
    assert manager.model_dir(model_id).is_dir()


def test_installed_voice_survives_missing_network_catalog_metadata(tmp_path: Path) -> None:
    model_id = "vits-piper-kk_KZ-raya-x_low"
    model = tmp_path / "additional_voices" / "models" / model_id
    _write_sparse(model / "raya.onnx", 1024 * 1024)
    (model / "tokens.txt").write_text("a 1\n", encoding="utf-8")

    manager = VoiceModelManager(tmp_path)
    installed = manager.installed_catalog()

    assert [item["id"] for item in installed] == [model_id]
    assert installed[0]["language"] == "kk"


def test_clone_install_is_recovered_after_process_kill(tmp_path: Path) -> None:
    staging = tmp_path / "voice_clone_engine" / "models" / ".clone_installing"
    for name in REQUIRED_FILES:
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"model")
    (staging / "espeak-ng-data").mkdir(parents=True)
    (staging / "espeak-ng-data" / "data").write_bytes(b"ok")
    _write_sparse(staging / VOCODER_FILE, VOCODER_SIZE)

    manager = VoiceCloneModelManager(tmp_path)

    assert manager.is_installed()
    assert not staging.exists()
    assert manager.model_dir.is_dir()
