export function usesNativeModels(security) {
  return Boolean(security?.native || security?.desktopOnly);
}

export function needsNativeModelDownload(model, nativeModels) {
  return Boolean(nativeModels && model?.managed && model.runtime !== "native-llamacpp");
}

export async function prepareNativeModel(item, options, { api, postJson, selectVariant }) {
  const modelRef = item.repository || item.modelId || item.id || item.model || item.name;
  const path = item.hostModelPath || item.host_model_path || item.modelPath;
  if (path && String(path).toLowerCase().endsWith(".gguf")) {
    return postJson("/api/model-registry/import-gguf", {
      path,
      role: options.role || (item.purpose === "coding" ? "coder" : "helper"),
      context: Number(options.contextWindow || item.contextWindow || 4096),
    });
  }
  if (!modelRef) throw new Error("Choose a GGUF model from Discover Models first.");
  const encoded = String(modelRef).split("/").map(encodeURIComponent).join("/");
  const detail = await api("/api/model-catalog/model/" + encoded);
  if (detail?.error) throw new Error(detail.error);
  const variant = selectVariant(detail?.variants || []);
  if (!variant || ["incompatible", "blocked", "unsupported"].includes(String(variant.compatibilityState || "").toLowerCase())) {
    throw new Error("This model has no compatible GGUF variant. Choose a GGUF version in Discover Models to load it with native llama.cpp.");
  }
  const job = await postJson("/api/models/download", { modelId: modelRef, variant });
  return { ...job, status: "downloading", modelId: modelRef };
}
