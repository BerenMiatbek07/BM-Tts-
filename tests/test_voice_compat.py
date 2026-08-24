from offline_voice_catalog import (
    compatible_model_id,
    fallback_catalog,
    is_runtime_compatible_model,
    parse_model_id,
)


def test_fp16_models_are_mapped_and_hidden() -> None:
    model_id = "vits-piper-kk_KZ-iseke-x_low-fp16"
    model = parse_model_id(model_id)
    assert model is not None
    assert model["precision"] == "fp16"
    assert not is_runtime_compatible_model(model)
    assert compatible_model_id(model_id) == "vits-piper-kk_KZ-iseke-x_low"


def test_android_fallback_catalog_contains_no_fp16() -> None:
    models = fallback_catalog()
    assert models
    assert all(item.get("precision") != "fp16" for item in models)
    ids = {str(item["id"]) for item in models}
    assert "vits-piper-kk_KZ-iseke-x_low" in ids
    assert "vits-piper-kk_KZ-raya-x_low" in ids
    assert "vits-piper-kk_KZ-issai-high" in ids
