export function blockerReasonText(reason) {
  if (typeof reason === "string") return reason.trim();
  if (reason && typeof reason === "object") {
    return [reason.message, reason.detail, reason.reason, reason.text, reason.code].find((value) => typeof value === "string" && value.trim())?.trim() || "Unknown deployment blocker";
  }
  return String(reason || "Unknown deployment blocker").trim();
}
export function blockerGuidanceForReason(reason) {
  const raw = blockerReasonText(reason);
  const text = raw.toLowerCase();
  if (!raw) return null;
  if (text.includes("docker control") || text.includes("docker_control") || text.includes("docker cli")) return { raw, happened: "Rasputin cannot control Docker from this session.", next: "Enable Docker control in Safety settings, or restart the stack with Docker-control access, then refresh the hardware snapshot." };
  if (text.includes("model folder") || text.includes("model directory") || text.includes("models directory") || text.includes("empty model") || text.includes("missing model")) return { raw, happened: "The configured model folder is missing or contains no usable model files.", next: "Choose or create the configured model folder, download/import the model weights, and refresh the catalog." };
  if (text.includes("approval") || text.includes("approve")) return text.includes("expired") || text.includes("closed") ? { raw, happened: "The deployment approval has expired or was closed.", next: "Create a fresh plan and request approval again before deploying." } : { raw, happened: "This deployment requires an explicit local approval.", next: "Review the plan and approve it when you are ready; deployment stays locked until approval is valid." };
  if (text.includes("multi-gpu") || text.includes("multi_gpu") || text.includes("combined vram") || text.includes("combined_vram")) return { raw, happened: "Using both GPUs together has not been proven safe for this model and runtime.", next: "Use llama.cpp/GGUF layer sharding for mixed cards, matching GPUs for automatic vLLM tensor parallelism, or an exact fresh vLLM certificate for this device set." };
  if (text.includes("unsupported") || text.includes("incompatible") || text.includes("runtime") || text.includes("gguf") || text.includes("format")) return { raw, happened: "The selected model format and runtime do not have a compatible deployment path.", next: "Choose a supported runtime for this model (for example llama.cpp for GGUF), or select a compatible model, then regenerate the plan." };
  if (text.includes("system ram") || text.includes("host memory") || text.includes("host_memory") || text.includes("requested ram")) return { raw, happened: "The model's system RAM demand is not available now or has not been verified against this machine.", next: "Close memory-heavy applications or choose a smaller model, then refresh the hardware check before loading." };
  if (text.includes("estimate") || text.includes("vram") || text.includes("memory") || text.includes("capacity") || text.includes("fit") || text.includes("placement") || text.includes("unproven")) return { raw, happened: "Available capacity or the model's VRAM demand is not sufficient or not verified for this placement.", next: "Refresh hardware detection, check the model's estimate against each GPU, and choose a smaller model or a measured multi-GPU plan when supported." };
  return { raw, happened: "The deployment was blocked by a backend safety or readiness check.", next: "Use the exact reason above to correct the configuration, then refresh the hardware snapshot and regenerate the plan." };
}
export function blockerGuidanceForReasons(reasons) {
  const seen = new Set();
  return (Array.isArray(reasons) ? reasons : [reasons]).map(blockerGuidanceForReason).filter((entry) => entry && !seen.has(entry.raw) && seen.add(entry.raw));
}
