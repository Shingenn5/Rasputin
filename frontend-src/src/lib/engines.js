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
