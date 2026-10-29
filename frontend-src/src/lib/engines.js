// Maps the Settings > Models "Default Inference Engine" choice to the Warsat
// protocol that runs it, plus display labels shared across views.
export const ENGINE_PROTOCOLS = {
  vllm: "vllmCudaOpenai",
  llamacpp: "llamaCppGgufServer",
  ollama: "ollamaOpenaiServer",
};

export const ENGINE_LABELS = {
  vllm: "vLLM",
  llamacpp: "Llama.cpp",
  ollama: "Ollama",
};

export function modelRuntimeProtocol(item, settings = {}) {
  if (item?.apiOnly) return "apiOnly";
  const options = (item?.runtimeOptions || []).map(option => option.protocolId).filter(Boolean);
  const recommended = item?.recommendedProtocol;
  const preferred = settings?.selectionMode === "manual"
    ? ENGINE_PROTOCOLS[settings.defaultEngine] || ENGINE_PROTOCOLS.llamacpp
    : ENGINE_PROTOCOLS.llamacpp;
  if (options.includes(preferred)) return preferred;
  // A model's advertised formats take precedence over the app preference.
  if (options.length) return options.includes(recommended) ? recommended : options[0];
  return recommended || preferred;
}
