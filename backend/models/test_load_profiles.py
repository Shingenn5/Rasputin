import pytest

from backend.models.load_profiles import (
    LoadProfileError,
    build_command,
    resolve_load_plan,
    validate_load_profile,
)


CAPABILITIES = {
    "flags": {
        "--fit": True,
        "--fit-target": True,
        "--fit-ctx": True,
        "--split-mode": True,
        "--tensor-split": True,
        "--cpu-moe": True,
        "--n-cpu-moe": True,
    },
    "split_modes": ["none", "layer", "row", "tensor"],
}


def hardware(*devices, safety_margin_mb=0):
    return {"devices": list(devices), "safety_margin_mb": safety_margin_mb}


def gpu(device_id, free_mb, compute_capability="8.6"):
    return {"id": device_id, "free_mb": free_mb, "compute_capability": compute_capability}


def model(size_mb, **extra):
    return {"size_mb": size_mb, "context_window": 8192, **extra}


def test_automatic_prefers_a_fitting_single_gpu():
    plan = resolve_load_plan(
        {"context_length": 4096},
        hardware=gpu("0", 9000),
        model=model(6000),
        capabilities=CAPABILITIES,
    )

    assert plan.accepted
    assert plan.resolved_settings["split_mode"] == "none"
    assert [item["device_id"] for item in plan.device_allocation] == ["0"]
    assert plan.flags[plan.flags.index("--split-mode") + 1] == "none"
    assert any("single GPU" in reason for reason in plan.fit_reasons)


def test_oversized_model_uses_automatic_layer_split_and_records_adjustment():
    plan = resolve_load_plan(
        {},
        hardware={"devices": [gpu("0", 5000), gpu("1", 5000)], "safety_margin_mb": 0},
        model=model(9000),
        capabilities=CAPABILITIES,
    )

    assert plan.accepted
    assert plan.resolved_settings["split_mode"] == "layer"
    assert "--split-mode" in plan.flags and plan.flags[plan.flags.index("--split-mode") + 1] == "layer"
    assert plan.automatic_adjustments[0]["to"] == "layer"
    assert any("tensor" in warning for warning in plan.warnings)


def test_impossible_plan_is_blocked_before_command_flags_are_built():
    plan = resolve_load_plan(
        {},
        hardware={"devices": [gpu("0", 3000), gpu("1", 3000)], "safety_margin_mb": 0},
        model=model(9000),
        capabilities=CAPABILITIES,
    )

    assert plan.blocked
    assert plan.flags == ()
    assert any("no permitted GPU allocation fits" in reason for reason in plan.block_reasons)


def test_unequal_gpus_never_get_tensor_parallelism_automatically_or_explicitly():
    auto = resolve_load_plan(
        {},
        hardware={"devices": [gpu("0", 5000, "8.6"), gpu("1", 7000, "8.9")], "safety_margin_mb": 0},
        model=model(11000),
        capabilities=CAPABILITIES,
    )
    assert auto.accepted
    assert auto.resolved_settings["split_mode"] == "layer"
    assert "tensor" not in auto.resolved_settings["split_mode"]

    explicit = resolve_load_plan(
        {"split_mode": "tensor", "tensor_split": "1,1"},
        hardware={"devices": [gpu("0", 8000, "8.6"), gpu("1", 8000, "8.9")], "safety_margin_mb": 0},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert explicit.blocked
    assert any("unequal GPUs" in reason for reason in explicit.block_reasons)


def test_explicit_overrides_are_preserved_in_canonical_flag_order():
    profile = {
        "context_length": 2048,
        "gpu_layers": 24,
        "fit": "off",
        "fit_target": 7000,
        "fit_ctx": 2048,
        "split_mode": "layer",
        "tensor_split": "1,0.5",
        "main_gpu": "0",
        "kv_offload": False,
        "cache_type_k": "q8_0",
        "cache_type_v": "q4_0",
        "flash_attention": True,
        "batch_size": 512,
        "ubatch_size": 128,
        "parallel_slots": 2,
        "threads": 8,
        "threads_batch": 4,
    }
    normalized = validate_load_profile(profile, CAPABILITIES)
    assert normalized.kv_offload == "off"
    plan = resolve_load_plan(
        profile,
        hardware={"devices": [gpu("0", 9000), gpu("1", 9000)], "safety_margin_mb": 0},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert plan.accepted
    assert plan.flags == (
        "--ctx-size", "2048", "--gpu-layers", "24", "--fit", "off",
        "--fit-target", "7000", "--fit-ctx", "2048", "--split-mode", "layer",
        "--tensor-split", "1,0.5", "--main-gpu", "0", "--no-kv-offload", "true",
        "--cache-type-k", "q8_0", "--cache-type-v", "q4_0", "--flash-attn", "on",
        "--batch-size", "512", "--ubatch-size", "128", "--parallel", "2",
        "--threads", "8", "--threads-batch", "4",
    )


def test_kv_offload_and_cache_type_are_distinct_from_split_controls():
    plan = resolve_load_plan(
        {"kv_offload": True, "cache_type_k": "q8_0", "cache_type_v": "q4_0", "split_mode": "layer"},
        hardware={"devices": [gpu("0", 6000), gpu("1", 6000)], "safety_margin_mb": 0},
        model=model(9000),
        capabilities=CAPABILITIES,
    )

    assert plan.accepted
    assert "--kv-offload" in plan.flags
    assert "--cache-type-k" in plan.flags and "--cache-type-v" in plan.flags
    assert plan.resolved_settings["split_mode"] == "layer"
    assert any("KV offload" in warning for warning in plan.warnings)
    assert any("cache types" in warning for warning in plan.warnings)


def test_unsupported_and_unknown_flags_are_rejected_or_capability_gated():
    with pytest.raises(LoadProfileError, match="unsupported load-profile setting"):
        validate_load_profile({"--made-up-flag": "yes"}, CAPABILITIES)
    with pytest.raises(LoadProfileError, match="experimental"):
        validate_load_profile({"split_mode": "tensor"}, {})
    with pytest.raises(LoadProfileError, match="cache_type_k"):
        validate_load_profile({"cache_type_k": "q3_k"}, CAPABILITIES)


def test_moe_controls_are_optional_and_architecture_capability_is_checked_by_planner():
    plan = resolve_load_plan(
        {"cpu_moe": True, "n_cpu_moe": 2},
        hardware=gpu("0", 8000),
        model=model(5000, architecture="mixtral", is_moe=True),
        capabilities=CAPABILITIES,
    )
    assert plan.accepted
    assert ("--cpu-moe", "on") == plan.flags[plan.flags.index("--cpu-moe"):plan.flags.index("--cpu-moe") + 2]
    assert "--n-cpu-moe" in plan.flags


def test_command_construction_is_deterministic_and_has_no_runtime_side_effects():
    kwargs = {
        "hardware": hardware(gpu("0", 10000)),
        "model": model(5000),
        "capabilities": CAPABILITIES,
        "engine": "C:/runtime/llama-server.exe",
        "model_path": "C:/models/demo.gguf",
    }
    first = resolve_load_plan({"context_length": 4096, "threads": 8}, **kwargs)
    second = resolve_load_plan({"threads": 8, "context_length": 4096}, **kwargs)
    assert first.command == second.command
    assert list(first.command) == [
        "C:/runtime/llama-server.exe", "-m", "C:/models/demo.gguf",
        "--ctx-size", "4096", "--fit", "on", "--fit-ctx", "4096", "--split-mode", "none", "--parallel", "1", "--threads", "8",
    ]
    assert first.model_path == "C:/models/demo.gguf"
    assert build_command(first) == ["C:/runtime/llama-server.exe", "-m", "C:/models/demo.gguf", "--ctx-size", "4096", "--fit", "on", "--fit-ctx", "4096", "--split-mode", "none", "--parallel", "1", "--threads", "8"]


def test_explicit_memory_modes_keep_gpu_preferred_strict_and_cpu_only_explicit():
    normalized = validate_load_profile({"memoryMode": "cpu_only"}, CAPABILITIES)
    assert normalized.memory_mode == "cpu_only"
    assert normalized.gpu_layers == 0

    cpu_plan = resolve_load_plan(
        {"memory_mode": "cpu_only"},
        hardware={},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert cpu_plan.accepted
    assert cpu_plan.resolved_settings["gpu_layers"] == 0
    assert cpu_plan.device_allocation == (
        {"device_id": "cpu", "memory_mb": 6000.0, "capacity_mb": None, "role": "cpu"},
    )

    strict = resolve_load_plan(
        {"memory_mode": "gpu_preferred"},
        hardware={"devices": [gpu("0", 3000)], "host_memory": {"availableMb": 10000}, "safety_margin_mb": 0},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert strict.blocked
    assert not any(item["device_id"] == "cpu" for item in strict.device_allocation)


def test_hybrid_mode_emits_separate_gpu_and_host_ram_allocations():
    plan = resolve_load_plan(
        {"memory_mode": "hybrid"},
        hardware={
            "devices": [gpu("0", 3000), gpu("1", 3000)],
            "host_memory": {"availableMb": 5000, "totalMb": 16000},
            "host_memory_headroom_mb": 1000,
            "safety_margin_mb": 0,
        },
        model=model(9000),
        capabilities=CAPABILITIES,
    )

    assert plan.accepted
    assert plan.resolved_settings["memory_mode"] == "hybrid"
    assert plan.resolved_settings["gpu_memory_required_mb"] == 6000.0
    assert plan.resolved_settings["host_memory_required_mb"] == 3000.0
    assert [item["device_id"] for item in plan.device_allocation] == ["0", "1", "cpu"]
    assert plan.device_allocation[-1]["role"] == "host_ram"
    assert sum(item["memory_mb"] for item in plan.device_allocation[:2]) == 6000.0
    assert plan.device_allocation[-1]["memory_mb"] == 3000.0
    assert "--fit" in plan.flags
    assert "--split-mode" in plan.flags
    assert any("Hybrid CPU/GPU offload" in warning for warning in plan.warnings)


def test_hybrid_mode_can_use_host_ram_without_gpu_snapshot_and_respects_explicit_cpu_layers():
    host_only = resolve_load_plan(
        {"memory_mode": "hybrid"},
        hardware={"host_memory": {"availableMb": 10000}, "host_memory_headroom_mb": 1000},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert host_only.accepted
    assert host_only.resolved_settings["gpu_layers"] == 0
    assert host_only.device_allocation == (
        {"device_id": "cpu", "memory_mb": 6000.0, "capacity_mb": 9000.0, "role": "host_ram"},
    )

    explicit_cpu = resolve_load_plan(
        {"memory_mode": "hybrid", "gpu_layers": 0},
        hardware={"devices": [gpu("0", 8000)], "host_memory": {"availableMb": 10000}},
        model=model(6000),
        capabilities=CAPABILITIES,
    )
    assert explicit_cpu.accepted
    assert explicit_cpu.resolved_settings["gpu_layers"] == 0
    assert explicit_cpu.device_allocation[0]["role"] == "cpu"


def test_hybrid_mode_blocks_when_host_ram_headroom_is_insufficient():
    plan = resolve_load_plan(
        {"memory_mode": "hybrid"},
        hardware={
            "devices": [gpu("0", 3000), gpu("1", 3000)],
            "host_memory": {"availableMb": 1500},
            "host_memory_headroom_mb": 1000,
            "safety_margin_mb": 0,
        },
        model=model(9000),
        capabilities=CAPABILITIES,
    )

    assert plan.blocked
    assert any("GPU plus host-RAM capacity" in reason or "host RAM" in reason for reason in plan.block_reasons)
