export function displayModelName(modelOrKey, models = []) {
  const model = resolveModel(modelOrKey, models);
  if (!model) return modelOrKey || "No model selected";
  if (model.provider === "mock" || model.key === "dry-run") return "Testing Mode";
  if (model.provider === "hash-vector" || model.role === "embeddings") {
    return model.model || "Local embeddings";
  }
  return model.model || discoveredModelIds(model)[0] || model.name || model.key || "Local model";
}

export function displayModelSecondary(modelOrKey, models = []) {
  const model = resolveModel(modelOrKey, models);
  if (!model) return "";
  const parts = [];
  if (model.name && model.name !== displayModelName(model, models)) parts.push(model.name);
  if (model.role) parts.push(labelize(model.role));
  if (model.provider) parts.push(model.provider);
  return parts.filter(Boolean).join(" / ");
}

export function displayWorkspaceName(value) {
  const text = String(value || "").trim();
  if (!text || text === ".") return "Project Root";
  return text.replace(/\\/g, "/").split("/").filter(Boolean).pop() || "Selected Workspace";
}

export function runtimeStatus(model) {
  // The registry refreshes runtime_status on every live container check.
  // Prefer it over the saved last-health snapshot, which may describe a
  // container that was reachable before it was subsequently stopped.
  return model?.runtimeStatus || model?.runtime_status || model?.lastHealth?.status || model?.last_health?.status || "unknown";
}

export function isUserFacingModel(model, testingMode) {
  if (!model || model.enabled === false) return false;
  if (model.key === "dry-run") return !!testingMode;
  if (model.role === "embeddings" || model.provider === "hash-vector") return false;
  return true;
}

export function isModelHealthy(model) {
  if (!model) return false;
  if (model.key === "dry-run" || ["mock", "hash-vector"].includes(model.provider)) return true;
  return runtimeStatus(model) === "reachable";
}

export function isModelRouteable(model) {
  if (!model) return false;
  if (isModelHealthy(model)) return true;
  // Remote APIs are not background-probed because doing so can spend quota.
  // Keep an untested configured API available, but hide it after a known
  // failure just like a stopped local runtime.
  return model.runtime === "remote-api" && runtimeStatus(model) === "unknown";
}

export function modelHealthLine(model, models) {
  if (!model) return "No model selected.";
  if (model.key === "dry-run") return "Testing Mode is ready.";
  const mismatch = modelMismatchLine(model);
  if (mismatch) return mismatch;
  if (isModelHealthy(model)) return `${displayModelName(model, models)} is ready.`;
  if (model.lastError) return `${displayModelName(model, models)} needs attention: ${model.lastError}`;
  return `${displayModelName(model, models)} has not passed a health check yet.`;
}

export function modelMismatchLine(model) {
  if (!model || model.provider === "mock" || model.provider === "hash-vector") return "";
  const configured = model.model;
  const available = discoveredModelIds(model);
  if (!configured || !available.length || available.includes(configured)) return "";
  const label = available.length === 1 ? "Available model" : "Available models";
  return `${configured} is not listed by the endpoint. ${label}: ${available.join(", ")}.`;
}

export function discoveredModelIds(model) {
  const direct = model?.discoveredModels || model?.discovered_models;
  const health = model?.lastHealth?.models || model?.last_health?.models;
  const values = Array.isArray(direct) && direct.length ? direct : health;
  return Array.isArray(values) ? values.filter(Boolean).map(String) : [];
}

export function resolveModel(modelOrKey, models = []) {
  if (!modelOrKey) return null;
  if (typeof modelOrKey === "object") return modelOrKey;
  return models.find((item) => item.key === modelOrKey) || models.find((item) => item.model === modelOrKey) || null;
}

export function labelize(value) {
  return String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
