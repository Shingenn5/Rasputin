import { postJson } from "../api/client.js";

export function useModelRegistryActions(context) {
  const {
    setGlobalStatus,
    loadModels,
    setSelectedModel,
  } = context;

  async function runModelAction(action, key, options = {}) {
    const resolvedKey = typeof key === "string" ? key.trim() : "";
    if (!resolvedKey) {
      const message = "Select a registered model before running this action.";
      setGlobalStatus(message);
      throw new Error(message);
    }
    try {
      const result = await postJson(`/api/model-registry/${action}`, { key: resolvedKey, ...options });
      if (result?.ok === false) {
        throw new Error(result.error?.message || result.error || result.message || "Model action failed.");
      }
      setGlobalStatus(action === "repair" && result.repaired ? "Model repaired." : `${action} finished.`);
      await loadModels();
    } catch (error) {
      setGlobalStatus(error.message);
      throw error;
    }
  }

  async function registerLocalModel(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const model = {
      key: form.get("key") || undefined,
      name: form.get("name") || form.get("model") || "Local Model",
      provider: form.get("provider") || "openai-compatible",
      role: form.get("role") || "helper",
      baseUrl: form.get("baseUrl"),
      model: form.get("model"),
      runtime: "external-local",
      contextWindow: Number(form.get("contextWindow") || 0) || undefined,
      maxTokens: Number(form.get("maxTokens") || 0) || undefined,
      enabled: true,
      managed: false,
      notes: form.get("notes") || "Connected from the Models tab.",
    };
    if (!model.baseUrl || !model.model) {
      setGlobalStatus("Enter a local endpoint and model id.");
      return null;
    }
    try {
      const saved = await postJson("/api/model-registry/upsert", model);
      await loadModels();
      setSelectedModel(saved.key);
      setGlobalStatus(`Connected ${saved.name || saved.model}. Run Test health next.`);
      event.currentTarget.reset();
      return saved;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function registerApiModel(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const provider = form.get("provider") || "openai";
    const modelId = form.get("model");
    const apiKey = form.get("apiKey");
    const apiKeyEnv = form.get("apiKeyEnv");
    const model = {
      name: form.get("name") || modelId || "API Model",
      provider,
      role: form.get("role") || "helper",
      baseUrl: form.get("baseUrl"),
      model: modelId,
      apiKey: apiKey || undefined,
      apiKeyEnv: apiKeyEnv || undefined,
      anthropicVersion: form.get("anthropicVersion") || undefined,
      runtime: "remote-api",
      contextWindow: Number(form.get("contextWindow") || 0) || undefined,
      maxTokens: Number(form.get("maxTokens") || 0) || undefined,
      enabled: true,
      managed: false,
      notes: form.get("notes") || "External API model. Requires remote models to be enabled in Safety.",
    };
    if (!model.model) {
      setGlobalStatus("Enter a provider model id.");
      return null;
    }
    if (!model.apiKey && !model.apiKeyEnv) {
      setGlobalStatus("Use an environment variable name or paste a key into the local secret store.");
      return null;
    }
    try {
      const saved = await postJson("/api/model-registry/upsert", model);
      await loadModels();
      setSelectedModel(saved.key);
      setGlobalStatus(`Registered ${saved.name || saved.model}. Run Test health after Safety allows remote models.`);
      event.currentTarget.reset();
      return saved;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function scanGguf() {
    try {
      const result = await postJson("/api/model-registry/scan-gguf", {});
      setGlobalStatus(`Added ${result.registered?.length || 0} models; ${result.existing?.length || 0} already in My Models.${result.truncated ? " Scan limit reached; scan a smaller model folder to find the rest." : ""}`);
      await loadModels();
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  return { runModelAction, registerLocalModel, registerApiModel, scanGguf };
}
