import { runtimeStatus } from "../../lib/display.js";
import { formatDownloadBytes } from "./downloadState.js";

export function contextWindowFor(m) {
  for (const k of ["contextWindow","context_window","maxModelLen","max_model_len"])
    if (Number.isFinite(Number(m?.[k])) && Number(m?.[k]) > 0) return Number(m[k]);
  return 0;
}

export function modelOperationalSignal(model) {
  const status = String(runtimeStatus(model) || "unknown").toLowerCase();
  if (["reachable", "healthy", "ready", "running"].includes(status)) {
    return { key: "live", label: "Live", detail: "Serving now" };
  }
  if (["unhealthy", "unreachable", "error", "failed", "blocked"].includes(status)) {
    return { key: "down", label: "Down", detail: "Needs attention" };
  }
  if (model?.artifactAvailable === false || model?.artifact_available === false) {
    return { key: "down", label: "Down", detail: "Local file missing" };
  }
  if (["loading", "starting", "warming"].includes(status)) {
    return { key: "parked", label: "Starting", detail: "Preparing model" };
  }
  return { key: "parked", label: "Parked", detail: status === "stopped" ? "Ready to load" : "Status not confirmed" };
}

export function installedModelCategory(model) {
  const blob = [model?.role, model?.purpose, model?.model, model?.name, ...(model?.capabilities || [])]
    .filter(Boolean).join(" ").toLowerCase();
  return blob.includes("embed") ? "embedding" : "llm";
}

export function installedModelPath(model) {
  return String(model?.host_model_path || model?.model_path || model?.modelPath || model?.path || "");
}

export function installedModelFile(model) {
  const path = installedModelPath(model);
  return path ? path.split(/[\\/]/).pop() : String(model?.model || model?.key || "Unknown");
}

export function installedModelPublisher(model) {
  const modelId = String(model?.model || model?.name || "");
  return String(model?.publisher || (modelId.includes("/") ? modelId.split("/")[0] : "") || model?.provider || "Local");
}

export function installedModelArchitecture(model) {
  return String(model?.architecture || model?.arch || model?.model_family || model?.family || "—");
}

export function installedModelParameters(model) {
  const declared = Number(model?.parameterCountB ?? model?.parameter_count_b);
  if (Number.isFinite(declared) && declared > 0) return `${declared}B`;
  const match = String(model?.model || model?.name || model?.key || "").match(/(?:^|[-_ ])(\d+(?:\.\d+)?)b(?:[-_ ]|$)/i);
  return match ? `${match[1]}B` : "—";
}

export function installedModelQuantization(model) {
  const declared = model?.quantization || model?.quantization_profile || model?.quantizationType;
  if (declared) return String(declared);
  const match = installedModelFile(model).match(/(?:^|[-_.])(Q\d(?:_[A-Z0-9]+)+)(?:[-_.]|$)/i);
  return match ? match[1].toUpperCase() : "—";
}

export function installedModelFormat(model) {
  if (/\.gguf$/i.test(installedModelFile(model)) || model?.runtime === "native-llamacpp") return "GGUF";
  if (String(model?.provider || "").includes("openai") || String(model?.runtime || "").includes("external")) return "API";
  return String(model?.format || "Model").toUpperCase();
}

export function installedModelSize(model) {
  const value = model?.sizeBytes ?? model?.size_bytes ?? model?.fileSize ?? model?.file_size;
  return value == null ? "—" : formatDownloadBytes(value);
}

export function catalogModelId(item) {
  return String(item?.modelId || item?.id || item?.name || "Unknown model");
}

export function catalogPublisher(item) {
  const modelId = catalogModelId(item);
  return String(item?.publisher || item?.developer || item?.author || item?.organization || item?.provider || modelId.split("/")[0] || "Community");
}

export function catalogParameterLabel(item) {
  const declared = Number(item?.parameterCountB ?? item?.parameter_count_b);
  if (Number.isFinite(declared) && declared > 0) return `${declared}B`;
  const match = catalogModelId(item).match(/(?:^|[-_ ])(\d+(?:\.\d+)?)b(?:[-_ ]|$)/i);
  return match ? `${match[1]}B` : "-";
}

export function catalogModelFormat(item) {
  if (item?.format) return String(item.format).toUpperCase();
  if ((item?.runtimeOptions || []).some((option) => option.protocolId === "llamaCppGgufServer")) return "GGUF";
  return item?.source === "huggingface" ? "HF" : "Model";
}

function compactCatalogMetric(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return "-";
  if (number >= 1e9) return (number / 1e9).toFixed(1) + "B";
  if (number >= 1e6) return (number / 1e6).toFixed(1) + "M";
  if (number >= 1e3) return (number / 1e3).toFixed(1) + "K";
  return number.toLocaleString();
}
