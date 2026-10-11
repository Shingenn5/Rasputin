export function guidanceForWarsatReason(reason) {
  const text = String(reason || "").toLowerCase();
  if (text.includes("combined_vram_requires_explicit_opt_in") || text.includes("combined vram")) {
    return { happened: "This model needs both GPUs together, but combined-GPU placement is still protected.", next: "Open Model Settings and enable multi-GPU placement only if you want to review and approve that tradeoff. WarSat will not opt in automatically.", settings: true };
  }
  if ((text.includes("unsupported") && (text.includes("runtime") || text.includes("format") || text.includes("model"))) || (text.includes("gguf") && text.includes("vllm"))) {
    return { happened: "The selected model format is not supported by the chosen runtime.", next: "Open Model Settings or choose a compatible model/runtime pair, then generate the plan again.", settings: true };
  }
  if (text.includes("approval") || text.includes("approve")) {
    return { happened: "The launch is waiting for the required local approval.", next: "Review the plan and choose Approve when you are ready. Deployment remains locked until then." };
  }
  if (text.includes("health") || text.includes("probe") || text.includes("endpoint")) {
    return { happened: "The runtime is still being checked for a healthy model endpoint.", next: "Leave this plan open while the health check completes. If it fails, review the runtime logs and retry the deployment." };
  }
  if (text.includes("download") || text.includes("loading") || text.includes("pull")) {
    return { happened: "The model files are still downloading or loading into memory.", next: "Wait for the progress step to finish; the first launch can take longer while weights are cached." };
  }
  return null;
}

export function getWarsatGuidance({ resource, plan, deployment, lifecycle, approvalPending, downloadProgress }) {
  const reasons = [...(resource?.reasons || []), ...(plan?.warnings || []), deployment?.lastError].filter(Boolean);
  const reasonGuidance = reasons.map(guidanceForWarsatReason).find(Boolean);
  if (reasonGuidance) return reasonGuidance;
  if (approvalPending || (deployment?.approvalRequired && deployment?.approval?.status === "pending")) return guidanceForWarsatReason("approval required");
  if (downloadProgress && ["downloading", "loading"].includes(downloadProgress.status)) return guidanceForWarsatReason(downloadProgress.status);
  const lifecycleText = (lifecycle || []).filter((phase) => ["active", "pending", "queued"].includes(phase.status)).map((phase) => phase.id + " " + (phase.label || "") + " " + (phase.message || "")).join(" ");
  return lifecycleText ? guidanceForWarsatReason(lifecycleText) : null;
}
