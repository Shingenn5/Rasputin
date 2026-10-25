import { runtimeStatus, isManagedModelRunning, isModelHealthy, modelMismatchLine } from "../../lib/display.js";
import { formatDownloadBytes } from "./downloadState.js";

export function contextWindowFor(m) {
  for (const k of ["contextWindow","context_window","maxModelLen","max_model_len"])
    if (Number.isFinite(Number(m?.[k])) && Number(m?.[k]) > 0) return Number(m[k]);
  return 0;
}

export function modelOperationalSignal(model) {
  const status = String(runtimeStatus(model) || "unknown").toLowerCase();
  const native = model?.runtime === "native-llamacpp";
  const process = String(model?.containerStatus || model?.container_status || "").toLowerCase();
  const health = model?.lastHealth || model?.last_health || {};
  const failure = model?.lastLoadFailure || model?.last_load_failure;
  const technical = String(failure?.message || model?.lastError || model?.last_error || health.lastError || health.last_error || "");
  const signal = (key, label, detail, next, action) => ({ key, label, detail, next, action, technical });
  if (model?.enabled === false) return signal("parked", "Disabled", "This model is excluded from model selection.", "Enable it in connection settings to use it again.", "connection");
  if (model?.artifactAvailable === false || model?.artifact_available === false) {
    return signal("down", "File missing", "Rasputin cannot find the downloaded model at its saved location.", "Locate the GGUF file below, or import it again if it was moved.", "file");
  }
  if (["loading", "starting", "warming"].includes(status) || ["loading", "starting"].includes(process)) {
    return signal("parked", "Loading", "The model is being prepared for use.", "Wait for Ready before starting a conversation.", "wait");
  }
  if (native && !failure && (process === "stopped" || status === "stopped")) {
    return signal("parked", "Not loaded", "Saved on this PC. It is not using a model process right now.", "Load the model when you want to use it. This is a normal state.", "load");
  }
  if (modelMismatchLine(model)) return signal("down", "Model not served", "The connected app is responding, but it is not serving this model ID.", "Find available models below and choose the one you want to connect.", "connection");
  if (isModelHealthy(model)) return signal("live", "Ready", "Connected and available for a conversation.", "Start a chat, or adjust its settings below.", "chat");
  if (model?.managed && model.runtime !== "native-llamacpp") return signal("down", "GGUF needed", "This entry uses a runtime that Rasputin no longer manages.", "Choose a compatible GGUF version to run it directly in Rasputin.", "download");
  if (/out of memory|insufficient.*memory|no permitted allocation|does not fit|not enough.*memory/i.test(technical)) return signal("down", "Not enough memory", "The last load could not fit within the available memory.", "Choose a smaller context, lower-memory preset, or CPU mode in load settings.", "configure");
  if (/401|403|unauthori[sz]ed|api.?key|authentication/i.test(technical)) return signal("down", "Access denied", "The model server rejected the connection credentials.", "Update the API key below and check the connection again.", "connection");
  if (/engine.*missing|runtime.*missing|llama.server.*not found|install.required/i.test(technical)) return signal("down", "Runtime needed", "The local inference engine is not available yet.", "Retry loading so Rasputin can acquire the matching runtime.", "configure");
  if (!native && /connection refused|actively refused|10061|failed to establish/i.test(technical)) return signal("down", "Can't reach server", "No model server answered at the saved address.", "Correct the connection below, or start model serving in its owning app, then check again.", "connection");
  if (!native && /timed out|timeout/i.test(technical)) return signal("down", "Connection timed out", "The model server did not answer before the connection timed out.", "Check its address below and make sure the owning app is responding, then retry.", "connection");
  if (!native && !model?.managed) return signal("down", "App not connected", technical ? "The last connection attempt failed." : "No successful connection has been confirmed for this model.", "Check the address and model ID below. The other app must be running and serving the model.", "connection");
  if (isManagedModelRunning(model)) return signal("parked", "Connecting", "The model process is running, but it is not ready to answer yet.", "Check again shortly. If it stays here, stop it and retry loading.", "check");
  if (technical || ["unhealthy", "unreachable", "error", "failed", "blocked"].includes(status)) return signal("down", "Couldn't load", technical ? "The previous attempt did not complete successfully." : "The model is unavailable, but no failure reason was recorded.", "Review the last error below, then retry with the recommended load settings.", "configure");
  return signal("parked", native ? "Not loaded" : "Not checked", native ? "This local model has not been loaded yet." : "Availability has not been checked yet.", native ? "Load the model to start using it." : "Check the connection before starting a chat.", native ? "load" : "check");
}

export function installedModelCategory(model) {
  const blob = [model?.role, model?.purpose, model?.model, model?.name, ...(model?.capabilities || [])]
    .filter(Boolean).join(" ").toLowerCase();
  return blob.includes("embed") ? "embedding" : "llm";
}

export function installedModelPath(model) {
  return String(model?.hostModelPath || model?.host_model_path || model?.model_path || model?.modelPath || model?.path || "");
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
  if (String(model?.provider || "").includes("openai") || String(model?.runtime || "").includes("external") || !model?.managed && (model?.baseUrl || model?.base_url)) return "API";
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
