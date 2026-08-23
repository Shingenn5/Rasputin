from __future__ import annotations

from unittest.mock import patch

from backend.models import catalog


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._payload


class FakeClient:
    response: FakeResponse | None = None
    calls: list[tuple[str, object]] = []

    def __init__(self, *args: object, **kwargs: object):
        pass

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def get(self, url: str, params: object = None) -> FakeResponse:
        type(self).calls.append((url, params))
        assert type(self).response is not None
        return type(self).response


def sibling(name: str, size: int | None = 100) -> dict[str, object]:
    return {"rfilename": name, "size": size}


def model_info(*siblings: dict[str, object], **extra: object) -> dict[str, object]:
    return {
        "id": "acme/vision-model",
        "sha": "revision-123",
        "downloads": 321,
        "likes": 12,
        "tags": ["gguf", "text-generation"],
        "config": {
            "architectures": ["LlamaForCausalLM"],
            "model_type": "llama",
            "torch_dtype": "float16",
            "max_position_embeddings": 8192,
            "chat_template": "{{ messages }}",
        },
        "siblings": list(siblings),
        **extra,
    }


def fetch_detail(payload: dict[str, object]) -> dict[str, object]:
    FakeClient.calls = []
    FakeClient.response = FakeResponse(payload)
    with patch.object(catalog.httpx, "Client", FakeClient):
        return catalog.hf_model_detail("acme/vision-model")


def test_detail_exposes_single_variant_with_exact_files_sizes_and_revision():
    result = fetch_detail(model_info(sibling("model-Q4_K_M.gguf", 1234)))

    assert result["modelId"] == "acme/vision-model"
    assert result["sha"] == "revision-123"
    assert result["revision"] == "revision-123"
    assert result["repositoryRevision"] == "revision-123"
    assert result["modelMetadata"]["contextWindow"] == 8192
    assert result["modelMetadata"]["architecture"] == "LlamaForCausalLM"

    assert len(result["variants"]) == 1
    variant = result["variants"][0]
    assert variant["repository"] == "acme/vision-model"
    assert variant["revision"] == "revision-123"
    assert variant["files"] == ["model-Q4_K_M.gguf"]
    assert variant["fileSizes"] == {"model-Q4_K_M.gguf": 1234}
    assert variant["totalBytes"] == 1234
    assert variant["quantization"] == "Q4_K_M"
    assert result["variantIssues"] == []
    assert FakeClient.calls[0][0].endswith("/acme/vision-model")


def test_detail_groups_complete_shards_and_rejects_incomplete_shards():
    complete = fetch_detail(
        model_info(
            sibling("model-Q8_0-00003-of-00003.gguf", 30),
            sibling("model-Q8_0-00001-of-00003.gguf", 10),
            sibling("model-Q8_0-00002-of-00003.gguf", 20),
        )
    )
    assert len(complete["variants"]) == 1
    assert complete["variants"][0]["files"] == [
        "model-Q8_0-00001-of-00003.gguf",
        "model-Q8_0-00002-of-00003.gguf",
        "model-Q8_0-00003-of-00003.gguf",
    ]
    assert complete["variants"][0]["totalBytes"] == 60

    incomplete = fetch_detail(
        model_info(
            sibling("model-Q4_K_M-00001-of-00003.gguf", 10),
            sibling("model-Q4_K_M-00003-of-00003.gguf", 30),
        )
    )
    assert incomplete["variants"] == []
    assert incomplete["variantIssues"][0]["kind"] == "incomplete-shard-group"
    assert "missing 1" in incomplete["variantIssues"][0]["reason"]


def test_detail_orders_multiple_quantizations_and_pairs_mmproj_variants():
    result = fetch_detail(
        model_info(
            sibling("model-Q4_K_M.gguf", 40),
            sibling("mmproj-model-f16.gguf", 25),
            sibling("model-F16.gguf", 160),
            sibling("model-Q8_0.gguf", 80),
        )
    )

    assert [(variant["quantization"], variant["multimodal"]) for variant in result["variants"]] == [
        ("F16", True),
        ("F16", False),
        ("Q8_0", True),
        ("Q8_0", False),
        ("Q4_K_M", True),
        ("Q4_K_M", False),
    ]
    multimodal = [variant for variant in result["variants"] if variant["multimodal"]]
    assert len(multimodal) == 3
    assert multimodal[0]["files"] == ["mmproj-model-f16.gguf", "model-F16.gguf"]
    assert multimodal[0]["totalBytes"] == 185
    assert multimodal[0]["fileSizes"]["mmproj-model-f16.gguf"] == 25


def test_detail_reports_explicit_no_gguf_for_non_gguf_repository():
    result = fetch_detail(
        model_info(
            sibling("config.json", 10),
            sibling("model.safetensors", 20),
            library_name="transformers",
        )
    )

    assert result["variants"] == []
    assert result["variantIssues"]
    assert result["variantIssues"][0]["kind"] == "no-gguf"
    assert result["variantIssues"][0]["nextAction"]


def test_detail_does_not_fabricate_size_or_fit_facts_when_metadata_is_missing():
    result = fetch_detail(model_info({"rfilename": "model.gguf"}))

    variant = result["variants"][0]
    assert variant["totalBytes"] is None
    assert variant["fileSizes"] == {"model.gguf": None}
    assert variant["compatibilityState"] == "unknown"
    assert any("size" in reason for reason in variant["compatibilityReasons"])
