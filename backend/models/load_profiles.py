"""Pure load-profile validation and llama.cpp placement planning.

This module intentionally has no runtime, process, or hardware-probe dependencies.
The scheduler/provider supplies model facts, a current device snapshot, and the
installed llama.cpp capability probe, then receives a deterministic command plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


DOCUMENTED_FLAGS = frozenset(
    {
        "--ctx-size",
        "--gpu-layers",
        "--fit",
        "--fit-target",
        "--fit-ctx",
        "--split-mode",
        "--tensor-split",
        "--main-gpu",
        "--kv-offload",
        "--no-kv-offload",
        "--cache-type-k",
        "--cache-type-v",
        "--flash-attn",
        "--batch-size",
        "--ubatch-size",
        "--parallel",
        "--threads",
        "--threads-batch",
        "--cpu-moe",
        "--n-cpu-moe",
    }
)
_EXPERIMENTAL_FLAGS = frozenset({"--split-mode", "--tensor-split", "--cpu-moe", "--n-cpu-moe"})
_CACHE_TYPES = frozenset({"f16", "q8_0", "q4_0"})
_SPLIT_MODES = frozenset({"none", "layer", "row", "tensor"})
_PROFILE_KEYS = frozenset(
    {
        "context_length",
        "contextLength",
        "context",
        "ctx_size",
        "ctxSize",
        "gpu_layers",
        "gpuLayers",
        "n_gpu_layers",
        "fit",
        "fit_target",
        "fitTarget",
        "fit_ctx",
        "fitCtx",
        "split_mode",
        "splitMode",
        "tensor_split",
        "tensorSplit",
        "main_gpu",
        "mainGpu",
        "kv_offload",
        "kvOffload",
        "cache_type_k",
        "cacheTypeK",
        "cache_type_v",
        "cacheTypeV",
        "flash_attention",
        "flashAttention",
        "batch_size",
        "batchSize",
        "ubatch_size",
        "ubatchSize",
        "parallel_slots",
        "parallelSlots",
        "parallel",
        "threads",
        "threads_batch",
        "threadsBatch",
        "cpu_moe",
        "cpuMoe",
        "n_cpu_moe",
        "nCpuMoe",
        "extra_flags",
        "extraFlags",
        # Profile metadata is retained by the caller but does not affect flags.
        "profile_id",
        "profileId",
        "artifact_id",
        "artifactId",
        "name",
        "origin",
    }
)


class LoadProfileError(ValueError):
    """Raised when requested settings cannot be safely normalized."""

    def __init__(self, errors: str | Sequence[str]):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class RequestedLoadProfile:
    context_length: int | None = None
    gpu_layers: int | str | None = None
    fit: str = "auto"
    fit_target: int | None = None
    fit_ctx: int | None = None
    split_mode: str = "auto"
    tensor_split: str | None = None
    main_gpu: str | int | None = None
    kv_offload: str = "auto"
    cache_type_k: str | None = None
    cache_type_v: str | None = None
    flash_attention: str = "auto"
    batch_size: int | None = None
    ubatch_size: int | None = None
    parallel_slots: int = 1
    threads: int | None = None
    threads_batch: int | None = None
    cpu_moe: str = "auto"
    n_cpu_moe: int | None = None
    extra_flags: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, profile: Mapping[str, Any] | "RequestedLoadProfile") -> "RequestedLoadProfile":
        if isinstance(profile, cls):
            return profile
        if not isinstance(profile, Mapping):
            raise LoadProfileError("load profile must be a mapping")
        unknown = sorted(set(profile) - _PROFILE_KEYS)
        if unknown:
            raise LoadProfileError([f"unsupported load-profile setting: {key}" for key in unknown])

        def pick(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if key in profile:
                    return profile[key]
            return default

        return cls(
            context_length=pick("context_length", "contextLength", "context", "ctx_size", "ctxSize"),
            gpu_layers=pick("gpu_layers", "gpuLayers", "n_gpu_layers"),
            fit=pick("fit", default="auto"),
            fit_target=pick("fit_target", "fitTarget"),
            fit_ctx=pick("fit_ctx", "fitCtx"),
            split_mode=pick("split_mode", "splitMode", default="auto"),
            tensor_split=pick("tensor_split", "tensorSplit"),
            main_gpu=pick("main_gpu", "mainGpu"),
            kv_offload=pick("kv_offload", "kvOffload", default="auto"),
            cache_type_k=pick("cache_type_k", "cacheTypeK"),
            cache_type_v=pick("cache_type_v", "cacheTypeV"),
            flash_attention=pick("flash_attention", "flashAttention", default="auto"),
            batch_size=pick("batch_size", "batchSize"),
            ubatch_size=pick("ubatch_size", "ubatchSize"),
            parallel_slots=pick("parallel_slots", "parallelSlots", "parallel", default=1),
            threads=pick("threads"),
            threads_batch=pick("threads_batch", "threadsBatch"),
            cpu_moe=pick("cpu_moe", "cpuMoe", default="auto"),
            n_cpu_moe=pick("n_cpu_moe", "nCpuMoe"),
            extra_flags=pick("extra_flags", "extraFlags", default={}) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_length": self.context_length,
            "gpu_layers": self.gpu_layers,
            "fit": self.fit,
            "fit_target": self.fit_target,
            "fit_ctx": self.fit_ctx,
            "split_mode": self.split_mode,
            "tensor_split": self.tensor_split,
            "main_gpu": self.main_gpu,
            "kv_offload": self.kv_offload,
            "cache_type_k": self.cache_type_k,
            "cache_type_v": self.cache_type_v,
            "flash_attention": self.flash_attention,
            "batch_size": self.batch_size,
            "ubatch_size": self.ubatch_size,
            "parallel_slots": self.parallel_slots,
            "threads": self.threads,
            "threads_batch": self.threads_batch,
            "cpu_moe": self.cpu_moe,
            "n_cpu_moe": self.n_cpu_moe,
            "extra_flags": dict(self.extra_flags),
        }


@dataclass(frozen=True)
class ResolvedLoadPlan:
    requested_settings: dict[str, Any]
    resolved_settings: dict[str, Any]
    flags: tuple[str, ...]
    command: tuple[str, ...]
    device_allocation: tuple[dict[str, Any], ...]
    engine: str = "llama-server"
    model_path: str | None = None
    warnings: tuple[str, ...] = ()
    fit_reasons: tuple[str, ...] = ()
    block_reasons: tuple[str, ...] = ()
    automatic_adjustments: tuple[dict[str, Any], ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.block_reasons)

    @property
    def accepted(self) -> bool:
        return not self.blocked

    @property
    def reasons(self) -> tuple[str, ...]:
        return self.block_reasons or self.fit_reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_settings": self.requested_settings,
            "resolved_settings": self.resolved_settings,
            "flags": list(self.flags),
            "command": list(self.command),
            "device_allocation": list(self.device_allocation),
            "engine": self.engine,
            "model_path": self.model_path,
            "warnings": list(self.warnings),
            "fit_reasons": list(self.fit_reasons),
            "block_reasons": list(self.block_reasons),
            "automatic_adjustments": list(self.automatic_adjustments),
            "blocked": self.blocked,
            "accepted": self.accepted,
        }


def _number(value: Any, *, name: str, integer: bool = False, minimum: float = 0) -> int | float:
    try:
        parsed = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise LoadProfileError(f"{name} must be a number") from None
    if parsed < minimum or (integer and float(parsed) != float(value)):
        raise LoadProfileError(f"{name} must be at least {minimum:g}")
    return parsed


def _choice(value: Any, *, name: str, allowed: set[str], default: str) -> str:
    if value is None or value == "":
        return default
    normalized = str(value).strip().lower()
    if normalized not in allowed:
        raise LoadProfileError(f"{name} must be one of {', '.join(sorted(allowed))}")
    return normalized


def _bool_choice(value: Any, *, name: str, default: str = "auto") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "on" if value else "off"
    return _choice(value, name=name, allowed={"auto", "on", "off"}, default=default)


def _normalize_tensor_split(value: Any) -> str | None:
    if value is None or value == "":
        return None
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        raise LoadProfileError("tensor_split must be a comma-separated list of positive proportions")
    parsed = []
    for item in values:
        parsed.append(_number(item, name="tensor_split", minimum=0.0))
    if len(parsed) < 2 or sum(parsed) <= 0:
        raise LoadProfileError("tensor_split must contain at least two proportions with a positive total")
    return ",".join(f"{number:g}" for number in parsed)


def _validate_flag_support(flag: str, capabilities: Mapping[str, Any], *, experimental: bool = False) -> None:
    if flag not in DOCUMENTED_FLAGS:
        raise LoadProfileError(f"unsupported llama.cpp flag: {flag}")
    raw = capabilities.get("supported_flags", capabilities.get("flags"))
    if isinstance(raw, Mapping):
        supported = raw.get(flag)
        if supported is False or (supported is None and flag in capabilities.get("unsupported_flags", ())):
            raise LoadProfileError(f"llama.cpp capability does not support {flag}")
        if supported is None and experimental:
            raise LoadProfileError(f"llama.cpp capability probe did not confirm experimental {flag}")
    elif raw is not None:
        supported_flags = {str(item) for item in raw}
        if flag not in supported_flags:
            raise LoadProfileError(f"llama.cpp capability does not support {flag}")
    elif experimental:
        raise LoadProfileError(f"llama.cpp capability probe did not confirm experimental {flag}")


def _supports(capabilities: Mapping[str, Any], flag: str) -> bool:
    try:
        _validate_flag_support(flag, capabilities, experimental=flag in _EXPERIMENTAL_FLAGS)
        return True
    except LoadProfileError:
        return False


def validate_load_profile(
    profile: Mapping[str, Any] | RequestedLoadProfile,
    capabilities: Mapping[str, Any] | None = None,
    model: Mapping[str, Any] | None = None,
) -> RequestedLoadProfile:
    """Normalize and validate requested settings without probing the machine."""

    requested = RequestedLoadProfile.from_mapping(profile)
    capabilities = capabilities or {}
    errors: list[str] = []
    try:
        context = None if requested.context_length is None else int(_number(requested.context_length, name="context_length", integer=True, minimum=1))
    except LoadProfileError as exc:
        errors.extend(exc.errors)
        context = None
    try:
        if requested.gpu_layers is None or str(requested.gpu_layers).strip().lower() == "auto":
            gpu_layers: int | str = "auto"
        else:
            gpu_layers = int(_number(requested.gpu_layers, name="gpu_layers", integer=True, minimum=0))
    except (LoadProfileError, ValueError):
        errors.append("gpu_layers must be a non-negative integer or auto")
        gpu_layers = "auto"
    try:
        fit = _bool_choice(requested.fit, name="fit")
        kv_offload = _bool_choice(requested.kv_offload, name="kv_offload")
        flash_attention = _bool_choice(requested.flash_attention, name="flash_attention")
        cpu_moe = _bool_choice(requested.cpu_moe, name="cpu_moe")
    except LoadProfileError as exc:
        errors.extend(exc.errors)
        fit, kv_offload, flash_attention, cpu_moe = "auto", "auto", "auto", "auto"
    try:
        split_mode = _choice(requested.split_mode, name="split_mode", allowed={"auto", *_SPLIT_MODES}, default="auto")
    except LoadProfileError as exc:
        errors.extend(exc.errors)
        split_mode = "auto"
    try:
        fit_target = None if requested.fit_target is None else int(_number(requested.fit_target, name="fit_target", integer=True, minimum=1))
        fit_ctx = None if requested.fit_ctx is None else int(_number(requested.fit_ctx, name="fit_ctx", integer=True, minimum=1))
        batch_size = None if requested.batch_size is None else int(_number(requested.batch_size, name="batch_size", integer=True, minimum=1))
        ubatch_size = None if requested.ubatch_size is None else int(_number(requested.ubatch_size, name="ubatch_size", integer=True, minimum=1))
        parallel_slots = int(_number(requested.parallel_slots, name="parallel_slots", integer=True, minimum=1))
        threads = None if requested.threads is None else int(_number(requested.threads, name="threads", integer=True, minimum=1))
        threads_batch = None if requested.threads_batch is None else int(_number(requested.threads_batch, name="threads_batch", integer=True, minimum=1))
        n_cpu_moe = None if requested.n_cpu_moe is None else int(_number(requested.n_cpu_moe, name="n_cpu_moe", integer=True, minimum=0))
    except LoadProfileError as exc:
        errors.extend(exc.errors)
        fit_target = fit_ctx = batch_size = ubatch_size = threads = threads_batch = n_cpu_moe = None
        parallel_slots = 1
    try:
        tensor_split = _normalize_tensor_split(requested.tensor_split)
    except LoadProfileError as exc:
        errors.extend(exc.errors)
        tensor_split = None
    cache_k = None if requested.cache_type_k is None else str(requested.cache_type_k).strip().lower()
    cache_v = None if requested.cache_type_v is None else str(requested.cache_type_v).strip().lower()
    if cache_k and cache_k not in _CACHE_TYPES:
        errors.append(f"cache_type_k must be one of {', '.join(sorted(_CACHE_TYPES))}")
    if cache_v and cache_v not in _CACHE_TYPES:
        errors.append(f"cache_type_v must be one of {', '.join(sorted(_CACHE_TYPES))}")
    if cache_k and not _supports(capabilities, "--cache-type-k"):
        errors.append("llama.cpp capability does not support --cache-type-k")
    if cache_v and not _supports(capabilities, "--cache-type-v"):
        errors.append("llama.cpp capability does not support --cache-type-v")
    if tensor_split and split_mode not in {"auto", "layer", "row", "tensor"}:
        errors.append("tensor_split requires a GPU split mode")
    if split_mode in {"row", "tensor"} and not _supports(capabilities, "--split-mode"):
        errors.append(f"llama.cpp capability did not confirm experimental {split_mode} split mode")
    if split_mode == "tensor" and not _supports(capabilities, "--tensor-split"):
        errors.append("experimental tensor split requires an explicitly confirmed llama.cpp capability")
    if requested.extra_flags:
        if not isinstance(requested.extra_flags, Mapping):
            errors.append("extra_flags must be a mapping")
        else:
            for flag in sorted(requested.extra_flags):
                if not str(flag).startswith("--") or flag not in DOCUMENTED_FLAGS:
                    errors.append(f"unsupported llama.cpp flag: {flag}")
                elif not _supports(capabilities, str(flag)):
                    errors.append(f"llama.cpp capability does not support {flag}")
    if errors:
        raise LoadProfileError(errors)
    return RequestedLoadProfile(
        context_length=context,
        gpu_layers=gpu_layers,
        fit=fit,
        fit_target=fit_target,
        fit_ctx=fit_ctx,
        split_mode=split_mode,
        tensor_split=tensor_split,
        main_gpu=requested.main_gpu,
        kv_offload=kv_offload,
        cache_type_k=cache_k,
        cache_type_v=cache_v,
        flash_attention=flash_attention,
        batch_size=batch_size,
        ubatch_size=ubatch_size,
        parallel_slots=parallel_slots,
        threads=threads,
        threads_batch=threads_batch,
        cpu_moe=cpu_moe,
        n_cpu_moe=n_cpu_moe,
        extra_flags=dict(requested.extra_flags),
    )


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _device_id(device: Mapping[str, Any], position: int) -> str:
    return str(_first(device, "id", "device_id", "deviceId", "uuid", "index", default=position))


def _device_free_mb(device: Mapping[str, Any]) -> float | None:
    value = _first(device, "free_mb", "freeMemoryMb", "memoryFreeMb", "free_vram_mb", "freeVramMb", "free_memory_mb")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _model_memory_mb(model: Mapping[str, Any]) -> float | None:
    value = _first(model, "gpu_memory_mb", "memory_mb", "estimated_gpu_memory_mb", "estimatedMemoryMb", "size_mb", "sizeMb")
    if value is None:
        bytes_value = _first(model, "size_bytes", "sizeBytes")
        if bytes_value is not None:
            try:
                value = float(bytes_value) / (1024 * 1024)
            except (TypeError, ValueError):
                value = None
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _kv_memory_mb(model: Mapping[str, Any], context: int, parallel: int) -> float:
    direct = _first(model, "kv_cache_mb", "kvCacheMb")
    if direct is not None:
        return max(0.0, float(direct)) * parallel
    per_1k = _first(model, "kv_cache_mb_per_1k", "kvCacheMbPer1k", "kv_mb_per_1k")
    if per_1k is not None:
        return max(0.0, float(per_1k)) * context / 1024 * parallel
    per_token = _first(model, "kv_cache_mb_per_token", "kvCacheMbPerToken")
    if per_token is not None:
        return max(0.0, float(per_token)) * context * parallel
    return 0.0


def _capability_list(capabilities: Mapping[str, Any], key: str, default: set[str]) -> set[str]:
    value = capabilities.get(key)
    return {str(item).lower() for item in value} if value is not None else set(default)


def _canonical_flags(settings: Mapping[str, Any], capabilities: Mapping[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []

    def add(flag: str, value: Any, *, experimental: bool = False) -> None:
        if value is None:
            return
        _validate_flag_support(flag, capabilities, experimental=experimental)
        flags.extend([flag, str(value)])

    add("--ctx-size", settings["context_length"])
    if settings["gpu_layers"] != "auto":
        add("--gpu-layers", settings["gpu_layers"])
    if settings["fit"] != "auto":
        add("--fit", settings["fit"])
    if settings["fit_target"] is not None:
        add("--fit-target", settings["fit_target"])
    if settings["fit_ctx"] is not None:
        add("--fit-ctx", settings["fit_ctx"])
    if settings["split_mode"] != "auto":
        add("--split-mode", settings["split_mode"], experimental=settings["split_mode"] in {"row", "tensor"})
    if settings["tensor_split"]:
        add("--tensor-split", settings["tensor_split"], experimental=True)
    if settings["main_gpu"] is not None:
        add("--main-gpu", settings["main_gpu"])
    if settings["kv_offload"] in {"on", "off"}:
        add("--kv-offload" if settings["kv_offload"] == "on" else "--no-kv-offload", "true")
    if settings["cache_type_k"]:
        add("--cache-type-k", settings["cache_type_k"])
    if settings["cache_type_v"]:
        add("--cache-type-v", settings["cache_type_v"])
    if settings["flash_attention"] != "auto":
        add("--flash-attn", settings["flash_attention"])
    add("--batch-size", settings["batch_size"])
    add("--ubatch-size", settings["ubatch_size"])
    add("--parallel", settings["parallel_slots"])
    add("--threads", settings["threads"])
    add("--threads-batch", settings["threads_batch"])
    if settings["cpu_moe"] != "auto":
        add("--cpu-moe", settings["cpu_moe"], experimental=True)
    add("--n-cpu-moe", settings["n_cpu_moe"], experimental=True)
    for flag in sorted(settings.get("extra_flags") or {}):
        add(flag, settings["extra_flags"][flag], experimental=False)
    return tuple(flags)


def build_command(
    plan: ResolvedLoadPlan,
    *,
    engine: str | None = None,
    model_path: str | None = None,
    prefix: Sequence[str] = (),
) -> list[str]:
    """Build a stable argv list from a resolved plan."""

    command = [str(engine if engine is not None else plan.engine), *map(str, prefix)]
    resolved_model_path = model_path if model_path is not None else plan.model_path
    if resolved_model_path:
        command.extend(["-m", str(resolved_model_path)])
    command.extend(plan.flags)
    return command


def resolve_load_plan(
    profile: Mapping[str, Any] | RequestedLoadProfile,
    *,
    hardware: Mapping[str, Any],
    model: Mapping[str, Any],
    capabilities: Mapping[str, Any] | None = None,
    engine: str = "llama-server",
    model_path: str | None = None,
) -> ResolvedLoadPlan:
    """Resolve a validated profile against supplied snapshots, without I/O."""

    capabilities = capabilities or {}
    try:
        requested = validate_load_profile(profile, capabilities, model)
    except LoadProfileError as exc:
        raw = RequestedLoadProfile.from_mapping(profile)
        return ResolvedLoadPlan(raw.to_dict(), {}, (), (str(engine),), (), block_reasons=tuple(exc.errors))

    if hardware.get("devices") is not None or hardware.get("gpus") is not None:
        devices_raw = hardware.get("devices") or hardware.get("gpus") or []
    elif any(key in hardware for key in ("id", "device_id", "free_mb", "freeVramMb", "memoryFreeMb")):
        devices_raw = [hardware]
    else:
        devices_raw = []
    devices = []
    for position, raw_device in enumerate(devices_raw):
        if not isinstance(raw_device, Mapping):
            continue
        device = dict(raw_device)
        device["device_id"] = _device_id(device, position)
        device["free_mb"] = _device_free_mb(device)
        devices.append(device)
    devices.sort(key=lambda item: item["device_id"])
    known_devices = {item["device_id"]: item for item in devices}
    safety = _first(hardware, "safety_margin_mb", "safetyMarginMb", default=512)
    try:
        safety = max(0.0, float(safety))
    except (TypeError, ValueError):
        safety = 512.0
    model_mb = _model_memory_mb(model)
    context = requested.context_length or int(_first(model, "recommended_context", "context_window", "contextWindow", default=4096))
    model_context = _first(model, "context_window", "contextWindow", "max_context", "maxContext")
    adjustments: list[dict[str, Any]] = []
    warnings: list[str] = []
    fit_reasons: list[str] = []
    block_reasons: list[str] = []
    if model_context is not None and context > int(model_context):
        if requested.context_length is None:
            adjustments.append({"field": "context_length", "from": context, "to": int(model_context), "reason": "model context limit"})
            context = int(model_context)
        else:
            block_reasons.append(f"requested context {context} exceeds model limit {int(model_context)}")
    planning_context = requested.fit_ctx or context
    kv_mb = _kv_memory_mb(model, planning_context, requested.parallel_slots)
    overhead = float(_first(model, "runtime_overhead_mb", "runtimeOverheadMb", default=0) or 0)
    required_mb = (model_mb or 0.0) + kv_mb + max(0.0, overhead)
    if model_mb is None and requested.gpu_layers != 0:
        block_reasons.append("model GPU memory requirement is unknown")
    if (requested.cpu_moe != "auto" or requested.n_cpu_moe is not None) and not bool(_first(model, "is_moe", "isMoE", default=False)):
        block_reasons.append("MoE CPU placement controls require a MoE model")
    if not devices and requested.gpu_layers != 0:
        block_reasons.append("no GPU device snapshot was supplied")

    usable = {}
    for device in devices:
        free = device["free_mb"]
        usable[device["device_id"]] = max(0.0, (free or 0.0) - safety)
        if requested.fit_target is not None:
            usable[device["device_id"]] = min(usable[device["device_id"]], float(requested.fit_target))
    preferred = sorted(
        (device for device in devices if device["free_mb"] is not None),
        key=lambda item: (-usable[item["device_id"]], item["device_id"]),
    )
    if requested.main_gpu is not None:
        selected_id = str(requested.main_gpu)
        if selected_id not in known_devices:
            block_reasons.append(f"main GPU {selected_id} is not in the hardware snapshot")
        else:
            preferred = [known_devices[selected_id]] + [item for item in preferred if item["device_id"] != selected_id]
    single_fit = next((item for item in preferred if usable[item["device_id"]] >= required_mb), None)
    explicit_split = requested.split_mode if requested.split_mode != "auto" else None
    split_mode = explicit_split or "none"
    allocation_devices: list[Mapping[str, Any]] = []

    if requested.gpu_layers == 0:
        split_mode = "none"
        allocation_devices = []
        fit_reasons.append("explicit gpu_layers=0 selects CPU-only execution")
    elif explicit_split == "tensor":
        if not _supports(capabilities, "--split-mode") or not _supports(capabilities, "--tensor-split"):
            block_reasons.append("tensor split requires an explicitly confirmed llama.cpp capability")
        if len(devices) < 2:
            block_reasons.append("tensor split requires at least two GPUs")
        compute_keys = {str(_first(item, "compute_capability", "computeCapability", "architecture", default="unknown")) for item in devices}
        if len(compute_keys) > 1 or len({round(usable[item["device_id"]], 2) for item in devices}) > 1:
            block_reasons.append("tensor parallelism is blocked across unequal GPUs; use layer split")
        if not block_reasons:
            allocation_devices = devices
    elif explicit_split in {"layer", "row"}:
        if explicit_split == "row" and not _supports(capabilities, "--split-mode"):
            block_reasons.append("row split requires an explicitly confirmed llama.cpp capability")
        if len(devices) < 2:
            block_reasons.append(f"{explicit_split} split requires at least two GPUs")
        if not devices or sum(usable.values()) < required_mb:
            block_reasons.append(f"model requires {required_mb:g} MiB but split devices provide {sum(usable.values()):g} MiB")
        if not block_reasons:
            allocation_devices = devices
    elif single_fit is not None:
        allocation_devices = [single_fit]
        fit_reasons.append(f"model fits on single GPU {single_fit['device_id']} with {usable[single_fit['device_id']]:g} MiB usable")
    elif requested.fit != "off" and len(devices) >= 2 and sum(usable.values()) >= required_mb and _supports(capabilities, "--split-mode"):
        split_mode = "layer"
        allocation_devices = devices
        adjustments.append({"field": "split_mode", "from": requested.split_mode, "to": "layer", "reason": "no single GPU fits; aggregate layer split capacity is sufficient"})
        warnings.append("Automatic multi-GPU placement uses layer split; tensor parallelism was not selected.")
        fit_reasons.append(f"model requires {required_mb:g} MiB; layer split provides {sum(usable.values()):g} MiB usable")
    else:
        block_reasons.append(f"model requires {required_mb:g} MiB but no permitted GPU allocation fits")

    if requested.fit == "off" and requested.split_mode == "auto" and single_fit is None and not allocation_devices:
        block_reasons.append("fit=off prevents automatic placement adjustment")
    if requested.split_mode == "auto" and requested.fit == "off" and single_fit is not None:
        split_mode = "none"
    if requested.tensor_split and split_mode != "tensor":
        warnings.append("Tensor split proportions are distinct from KV-cache offload and are only applied to tensor split mode.")
    if requested.kv_offload != "auto":
        warnings.append("KV offload controls KV-cache placement; it does not control multi-GPU model splitting.")
    if requested.cache_type_k or requested.cache_type_v:
        warnings.append("K/V cache types change cache precision; they do not assign cache to individual GPUs.")
    if requested.main_gpu is not None and allocation_devices and str(requested.main_gpu) != allocation_devices[0]["device_id"]:
        warnings.append("main_gpu is a preferred device; the resolved allocation reflects the fit planner.")

    if allocation_devices and split_mode in {"layer", "row", "tensor"}:
        total_capacity = sum(usable[item["device_id"]] for item in allocation_devices)
        allocations = []
        remaining = required_mb
        for index, item in enumerate(allocation_devices):
            capacity = usable[item["device_id"]]
            amount = remaining if index == len(allocation_devices) - 1 else round(required_mb * capacity / total_capacity, 2)
            amount = min(amount, capacity)
            remaining = max(0.0, remaining - amount)
            allocations.append({"device_id": item["device_id"], "memory_mb": amount, "capacity_mb": capacity, "role": "primary" if index == 0 else "secondary"})
    elif allocation_devices:
        item = allocation_devices[0]
        allocations = [{"device_id": item["device_id"], "memory_mb": required_mb, "capacity_mb": usable[item["device_id"]], "role": "primary"}]
    else:
        allocations = [{"device_id": "cpu", "memory_mb": required_mb, "capacity_mb": None, "role": "cpu"}] if requested.gpu_layers == 0 else []

    resolved = requested.to_dict()
    resolved.update({
        "context_length": context,
        "gpu_layers": 0 if requested.gpu_layers == 0 else requested.gpu_layers,
        "fit": requested.fit if requested.fit != "auto" else ("on" if allocation_devices else "off"),
        "fit_ctx": requested.fit_ctx or context,
        "split_mode": split_mode,
        "kv_cache_mb": round(kv_mb, 2),
        "required_memory_mb": round(required_mb, 2),
    })
    try:
        flags = _canonical_flags(resolved, capabilities) if not block_reasons else ()
    except LoadProfileError as exc:
        block_reasons.extend(exc.errors)
        flags = ()
    command = tuple(build_command(ResolvedLoadPlan(requested.to_dict(), resolved, flags, (), tuple(allocations), engine=str(engine), model_path=model_path)))
    return ResolvedLoadPlan(
        requested_settings=requested.to_dict(),
        resolved_settings=resolved,
        flags=flags,
        command=command,
        device_allocation=tuple(allocations),
        engine=str(engine),
        model_path=model_path,
        warnings=tuple(dict.fromkeys(warnings)),
        fit_reasons=tuple(dict.fromkeys(fit_reasons)),
        block_reasons=tuple(dict.fromkeys(block_reasons)),
        automatic_adjustments=tuple(adjustments),
    )


resolve_load_profile = resolve_load_plan
validate_profile = validate_load_profile


__all__ = [
    "DOCUMENTED_FLAGS",
    "LoadProfileError",
    "RequestedLoadProfile",
    "ResolvedLoadPlan",
    "build_command",
    "resolve_load_plan",
    "resolve_load_profile",
    "validate_load_profile",
    "validate_profile",
]
