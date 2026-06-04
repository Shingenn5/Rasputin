export function displayModelName(modelOrKey, models = []) {
  const model = typeof modelOrKey === "string" ? models.find((item) => item.key === modelOrKey) : modelOrKey;
  if (!model) return modelOrKey || "No model selected";
  if (model.key === "main-vllm") return "Main Local Model";
  if (model.key === "dry-run") return "Testing Mode";
  if (model.key === "local-embeddings") return "Knowledge Embeddings";
  return model.name || model.key || "Local Model";
}

export function displayWorkspaceName(value) {
  const text = String(value || "").trim();
  if (!text || text === ".") return "Project Root";
  return text.replace(/\\/g, "/").split("/").filter(Boolean).pop() || "Selected Workspace";
}

export function runtimeStatus(model) {
  return model?.lastHealth?.status || model?.runtimeStatus || "unknown";
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

export function modelHealthLine(model, models) {
  if (!model) return "No model selected.";
  if (model.key === "dry-run") return "Testing Mode is ready.";
  if (isModelHealthy(model)) return `${displayModelName(model, models)} is ready.`;
  if (model.lastError) return `${displayModelName(model, models)} needs attention: ${model.lastError}`;
  return `${displayModelName(model, models)} has not passed a health check yet.`;
}
