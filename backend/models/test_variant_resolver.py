from __future__ import annotations

from backend.models.variant_resolver import (
    UNKNOWN,
    resolve_model_variants,
    resolve_model_variants_with_issues,
)


def sibling(name: str, size: int | None = 100) -> dict[str, object]:
    return {"rfilename": name, "size": size}


def model_info(*siblings: dict[str, object], **extra: object) -> dict[str, object]:
    return {"id": "acme/vision-model", "sha": "abc123", "siblings": list(siblings), **extra}


def test_resolves_single_gguf_with_exact_size_and_quantization():
    variants = resolve_model_variants(model_info(sibling("model-Q4_K_M.gguf", 1234)))

    assert len(variants) == 1
    variant = variants[0]
    assert variant.repository == "acme/vision-model"
    assert variant.revision == "abc123"
    assert variant.files == ("model-Q4_K_M.gguf",)
    assert variant.model_files == variant.files
    assert variant.total_bytes == 1234
    assert variant.quantization == "Q4_K_M"
    assert variant.bits_per_weight == 4.75
    assert variant.shard_count == 1
    assert variant.multimodal is False
    assert variant.compatibility_state == "unknown"
    assert variant.next_actions


def test_resolves_complete_shard_family_and_never_exposes_a_shard():
    variants = resolve_model_variants(
        model_info(
            sibling("model-Q8_0-00002-of-00003.gguf", 20),
            sibling("model-Q8_0-00001-of-00003.gguf", 10),
            sibling("model-Q8_0-00003-of-00003.gguf", 30),
        )
    )

    assert len(variants) == 1
    assert variants[0].files == (
        "model-Q8_0-00001-of-00003.gguf",
        "model-Q8_0-00002-of-00003.gguf",
        "model-Q8_0-00003-of-00003.gguf",
    )
    assert variants[0].total_bytes == 60
    assert variants[0].shard_count == 3


def test_pairs_mmproj_and_keeps_a_text_only_exact_file_set():
    variants = resolve_model_variants(
        model_info(
            sibling("model-Q4_K_M.gguf", 100),
            sibling("mmproj-model-f16.gguf", 25),
        )
    )

    assert len(variants) == 2
    text_only, multimodal = sorted(variants, key=lambda item: item.multimodal)
    assert text_only.files == ("model-Q4_K_M.gguf",)
    assert text_only.multimodal is False
    assert multimodal.files == ("mmproj-model-f16.gguf", "model-Q4_K_M.gguf")
    assert multimodal.mmproj == "mmproj-model-f16.gguf"
    assert multimodal.total_bytes == 125
    assert multimodal.multimodal is True


def test_resolves_multiple_quantizations_in_deterministic_precision_order():
    variants = resolve_model_variants(
        model_info(
            sibling("model-Q4_K_M.gguf", 40),
            sibling("model-Q8_0.gguf", 80),
            sibling("model-F16.gguf", 160),
        )
    )

    assert [variant.quantization for variant in variants] == ["F16", "Q8_0", "Q4_K_M"]


def test_incomplete_shard_group_is_rejected_with_actionable_issue():
    resolution = resolve_model_variants_with_issues(
        model_info(
            sibling("model-Q4_K_M-00001-of-00003.gguf", 10),
            sibling("model-Q4_K_M-00003-of-00003.gguf", 30),
        )
    )

    assert resolution.variants == ()
    assert len(resolution.issues) == 1
    assert resolution.issues[0].kind == "incomplete-shard-group"
    assert "missing 1" in resolution.issues[0].reason
    assert "every shard" in resolution.issues[0].next_action


def test_non_gguf_repository_returns_no_variants():
    resolution = resolve_model_variants_with_issues(
        model_info(sibling("config.json", 10), sibling("model.safetensors", 20))
    )

    assert resolution.variants == ()
    assert resolution.issues[0].kind == "no-gguf"


def test_duplicate_inputs_are_deduplicated_and_order_is_input_independent():
    first = resolve_model_variants(
        model_info(
            sibling("model-Q4_K_M.gguf", 100),
            sibling("mmproj-model-f16.gguf", 20),
            sibling("model-Q4_K_M.gguf", 100),
            sibling("mmproj-model-f16.gguf", 20),
        )
    )
    second = resolve_model_variants(
        model_info(
            sibling("mmproj-model-f16.gguf", 20),
            sibling("model-Q4_K_M.gguf", 100),
        )
    )

    assert [variant.as_dict() for variant in first] == [variant.as_dict() for variant in second]
    assert len(first) == 2
    assert len({variant.id for variant in first}) == 2


def test_missing_metadata_stays_unknown_instead_of_fabricating_fit_facts():
    variant = resolve_model_variants(
        {"id": "acme/unknown", "siblings": [{"rfilename": "model.gguf"}]}
    )[0]

    assert variant.revision == UNKNOWN
    assert variant.total_bytes is None
    assert variant.quantization == UNKNOWN
    assert variant.bits_per_weight is None
    assert variant.compatibility_state == "unknown"
    assert any("size" in reason for reason in variant.compatibility_reasons)
    assert any("quantization" in reason.lower() for reason in variant.compatibility_reasons)
