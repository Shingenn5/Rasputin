import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Cpu, Gauge, Layers, MemoryStick, SlidersHorizontal } from "lucide-react";
import { api } from "../../api/client.js";
import { Modal } from "../../components/Modal.jsx";
import { displayModelName } from "../../lib/display.js";

const DEFAULT_PROFILE = {
  contextLength: 8192,
  memoryMode: "gpu_preferred",
  gpuLayers: "auto",
  splitMode: "auto",
  tensorSplit: "",
  mainGpu: "",
  kvOffload: "auto",
  cacheTypeK: "",
  cacheTypeV: "",
  flashAttention: "auto",
  batchSize: 512,
  ubatchSize: 256,
  parallelSlots: 1,
  threads: "",
  threadsBatch: "",
  cpuMoe: "auto",
  nCpuMoe: "",
};

function savedProfile(modelKey) {
  try {
    const value = JSON.parse(localStorage.getItem("rasputin:model-load:" + modelKey) || "null");
    return value && typeof value === "object" ? { ...DEFAULT_PROFILE, ...value } : DEFAULT_PROFILE;
  } catch {
    return DEFAULT_PROFILE;
  }
}

function optionalNumber(value) {
  if (value === "" || value == null) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function cleanProfile(profile) {
  return {
    contextLength: optionalNumber(profile.contextLength),
    memoryMode: profile.memoryMode,
    gpuLayers: profile.gpuLayers === "auto" ? "auto" : optionalNumber(profile.gpuLayers),
    splitMode: profile.splitMode,
    tensorSplit: profile.tensorSplit || undefined,
    mainGpu: profile.mainGpu === "" ? undefined : profile.mainGpu,
    kvOffload: profile.kvOffload,
    cacheTypeK: profile.cacheTypeK || undefined,
    cacheTypeV: profile.cacheTypeV || undefined,
    flashAttention: profile.flashAttention,
    batchSize: optionalNumber(profile.batchSize),
    ubatchSize: optionalNumber(profile.ubatchSize),
    parallelSlots: optionalNumber(profile.parallelSlots) || 1,
    threads: optionalNumber(profile.threads),
    threadsBatch: optionalNumber(profile.threadsBatch),
    cpuMoe: profile.cpuMoe,
    nCpuMoe: optionalNumber(profile.nCpuMoe),
  };
}

function Field({ label, hint, children }) {
  return (
    <label className="studio-load-field">
      <span><strong>{label}</strong>{hint && <small>{hint}</small>}</span>
      {children}
    </label>
  );
}

function Select({ value, onChange, children, label }) {
  return <select className="w2-input" value={value} onChange={onChange} aria-label={label}>{children}</select>;
}

export function ModelLoadDialog({ model, models, hardware, onClose, onLoad }) {
  const [profile, setProfile] = useState(DEFAULT_PROFILE);
  const [remember, setRemember] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [runtimeStatus, setRuntimeStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");

  const modelKey = model?.key || "";
  const modelName = displayModelName(model, models);
  const cleaned = useMemo(() => cleanProfile(profile), [profile]);

  useEffect(() => {
    if (!modelKey) return;
    setLoadError("");
    const next = savedProfile(modelKey);
    setProfile(next);
    setRemember(localStorage.getItem("rasputin:model-load:remember:" + modelKey) === "1");
  }, [modelKey]);

  useEffect(() => {
    if (!model) return undefined;
    let disposed = false;
    api("/api/runtime/llamacpp/status")
      .then((status) => { if (!disposed) setRuntimeStatus(status); })
      .catch(() => { if (!disposed) setRuntimeStatus(null); });
    return () => { disposed = true; };
  }, [model]);

  useEffect(() => {
    if (!model) return undefined;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPreviewError("");
      api("/api/model-catalog/load-plan-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          profile: cleaned,
          hardware: hardware || {},
          model,
          modelPath: model.hostModelPath || model.host_model_path || model.path || model.model_path || model.modelPath,
          capabilities: runtimeStatus?.capabilities || runtimeStatus?.runtimeCapabilities || runtimeStatus?.runtime_capabilities || {},
        }),
      }).then(setPreview).catch((error) => {
        if (error?.name !== "AbortError") setPreviewError(error?.message || "Unable to preview this load profile.");
      });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [model, hardware, runtimeStatus, cleaned]);

  const set = (key) => (event) => setProfile((current) => ({ ...current, [key]: event.target.value }));
  const requiredMemoryMb = preview?.resolvedSettings?.requiredMemoryMb ?? preview?.resolved_settings?.required_memory_mb;
  const blocked = Boolean(preview?.blocked || preview?.accepted === false || previewError);

  const handleLoad = async () => {
    setLoading(true);
    setLoadError("");
    try {
      if (remember) {
        localStorage.setItem("rasputin:model-load:" + modelKey, JSON.stringify(profile));
        localStorage.setItem("rasputin:model-load:remember:" + modelKey, "1");
      } else {
        localStorage.removeItem("rasputin:model-load:remember:" + modelKey);
      }
      await onLoad(model, cleaned);
      onClose();
    } catch (error) {
      setLoadError(error?.message || "Unable to load this model. Review the settings and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={Boolean(model)} onClose={onClose} title={modelName || "Load model"} size="lg" className="studio-load-modal">
      {loadError && <p role="alert" className="models-discover-error">{loadError}</p>}
      <div className="studio-load-summary">
        <div><MemoryStick size={18} /><span><small>Estimated memory</small><strong>{Number.isFinite(requiredMemoryMb) ? `${(requiredMemoryMb / 1024).toFixed(2)} GB` : "Auto-fit"}</strong></span></div>
        <div><Gauge size={18} /><span><small>Inference engine</small><strong>llama.cpp</strong></span></div>
        <div><Layers size={18} /><span><small>Placement</small><strong>{profile.memoryMode === "cpu_only" ? "System RAM" : profile.splitMode === "layer" ? "Combined GPU pool" : "Automatic"}</strong></span></div>
      </div>

      <div className="studio-load-form">
        <Field label="Context length" hint="Maximum tokens retained per conversation">
          <input className="w2-input" type="number" min="512" step="512" value={profile.contextLength} onChange={set("contextLength")} />
        </Field>
        <Field label="Memory mode" hint="Choose automatic GPU fit, pooled RAM + VRAM, or CPU only">
          <Select value={profile.memoryMode} onChange={set("memoryMode")} label="Memory mode">
            <option value="gpu_preferred">Prefer GPU automatically</option>
            <option value="hybrid">Pool system RAM and VRAM</option>
            <option value="cpu_only">System RAM / CPU only</option>
          </Select>
        </Field>
        <Field label="GPU offload layers" hint="Auto uses the largest fitting GPU first">
          <input className="w2-input" value={profile.gpuLayers} onChange={set("gpuLayers")} inputMode="numeric" />
        </Field>
        <Field label="CPU thread pool" hint="Leave blank to let llama.cpp choose">
          <input className="w2-input" type="number" min="1" value={profile.threads} onChange={set("threads")} placeholder="Auto" />
        </Field>
        <Field label="Evaluation batch size" hint="Prompt-processing batch">
          <input className="w2-input" type="number" min="1" value={profile.batchSize} onChange={set("batchSize")} />
        </Field>
        <Field label="Physical batch size" hint="Micro-batch used by the runtime">
          <input className="w2-input" type="number" min="1" value={profile.ubatchSize} onChange={set("ubatchSize")} />
        </Field>
        <Field label="Concurrent predictions" hint="Parallel llama.cpp slots">
          <input className="w2-input" type="number" min="1" value={profile.parallelSlots} onChange={set("parallelSlots")} />
        </Field>
        <Field label="KV cache offload" hint="Move the conversation cache to GPU memory">
          <Select value={profile.kvOffload} onChange={set("kvOffload")} label="KV cache offload">
            <option value="auto">Automatic</option>
            <option value="on">On</option>
            <option value="off">Off</option>
          </Select>
        </Field>
      </div>

      <button type="button" className="studio-load-advanced-toggle" aria-expanded={advanced} onClick={() => setAdvanced((value) => !value)}>
        <SlidersHorizontal size={15} /> {advanced ? "Hide advanced settings" : "Show advanced settings"}
      </button>

      {advanced && (
        <div className="studio-load-form studio-load-form-advanced">
          <Field label="GPU split mode" hint="Layer splitting pools VRAM across compatible GPUs">
            <Select value={profile.splitMode} onChange={set("splitMode")} label="GPU split mode">
              <option value="auto">Automatic</option>
              <option value="none">Single GPU</option>
              <option value="layer">Layer split / combined VRAM</option>
              <option value="row">Row split (experimental)</option>
            </Select>
          </Field>
          <Field label="Tensor split" hint="Comma-separated weights, for example 1,1">
            <input className="w2-input" value={profile.tensorSplit} onChange={set("tensorSplit")} placeholder="Automatic" />
          </Field>
          <Field label="Main GPU" hint="Device index used for single-GPU placement">
            <input className="w2-input" value={profile.mainGpu} onChange={set("mainGpu")} placeholder="Automatic" />
          </Field>
          <Field label="Flash attention" hint="Use supported optimized attention kernels">
            <Select value={profile.flashAttention} onChange={set("flashAttention")} label="Flash attention">
              <option value="auto">Automatic</option><option value="on">On</option><option value="off">Off</option>
            </Select>
          </Field>
          <Field label="K cache quantization" hint="Lower precision reduces KV memory">
            <Select value={profile.cacheTypeK} onChange={set("cacheTypeK")} label="K cache quantization">
              <option value="">Default</option><option value="f16">F16</option><option value="q8_0">Q8_0</option><option value="q4_0">Q4_0</option>
            </Select>
          </Field>
          <Field label="V cache quantization" hint="Lower precision reduces KV memory">
            <Select value={profile.cacheTypeV} onChange={set("cacheTypeV")} label="V cache quantization">
              <option value="">Default</option><option value="f16">F16</option><option value="q8_0">Q8_0</option><option value="q4_0">Q4_0</option>
            </Select>
          </Field>
          <Field label="Batch threads" hint="Threads used for prompt processing">
            <input className="w2-input" type="number" min="1" value={profile.threadsBatch} onChange={set("threadsBatch")} placeholder="Auto" />
          </Field>
          <Field label="CPU MoE" hint="Offload mixture-of-experts tensors when supported">
            <Select value={profile.cpuMoe} onChange={set("cpuMoe")} label="CPU MoE">
              <option value="auto">Automatic</option><option value="on">On</option><option value="off">Off</option>
            </Select>
          </Field>
        </div>
      )}

      {(preview?.deviceAllocation || preview?.device_allocation)?.length > 0 && (
        <div className="studio-load-plan">
          <strong>Planned allocation</strong>
          {(preview.deviceAllocation || preview.device_allocation).map((device, index) => (
            <span key={device.deviceId || device.device_id || index}>{device.name || "GPU " + (device.deviceId ?? device.device_id ?? index)} · {Number(device.memoryMb ?? device.memory_mb ?? device.allocatedMb ?? device.allocated_mb ?? 0).toFixed(0)} MB</span>
          ))}
        </div>
      )}

      {(preview?.blockReasons || preview?.block_reasons)?.length > 0 && (
        <div className="studio-load-warning" role="alert"><AlertTriangle size={16} /><span>{(preview.blockReasons || preview.block_reasons).join(" ")}</span></div>
      )}
      {previewError && <div className="studio-load-warning" role="alert"><AlertTriangle size={16} /><span>{previewError}</span></div>}

      {loading && <p role="status" data-testid="model-warmup-status">Loading weights and running a short warm-up before the model is ready. The first load can take longer while the runtime initializes.</p>}
      <footer className="studio-load-footer">
        <label><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /> Remember settings for this model</label>
        <span />
        <button type="button" className="w2-button" onClick={onClose}>Cancel</button>
        <button type="button" className="w2-button primary" disabled={blocked || loading} onClick={handleLoad}>
          <Cpu size={15} /> {loading ? "Loading and warming up…" : "Load model"}
        </button>
      </footer>
    </Modal>
  );
}
