import { api, postJson } from "../api/client.js";

export function useAssistantActions(context) {
  const {
    setAssistantLoading,
    setAssistantError,
    setAssistantProfile,
    setAssistantCapabilities,
    setAssistantPlans,
    setAssistantContextCapsules,
    setSelectedTaskContextCapsuleId,
    setAssistantModelPacks,
    setAssistantHandoffs,
    setAssistantModelRequests,
    setGlobalStatus,
    setAssistantVoicePreview,
    workspace,
    setAssistantCommandPreview,
    setAssistantContextPreview,
    assistantProfileToWarsatStrengthProfile,
  } = context;

  async function loadAssistantData() {
    setAssistantLoading(true);
    setAssistantError("");
    try {
      const [nextProfile, nextCapabilities, nextPlans, nextCapsules, nextPacks, nextHandoffs, nextModelRequests] = await Promise.all([
        api("/api/assistant/profile"),
        api("/api/assistant/capabilities"),
        api("/api/assistant/plans"),
        api("/api/assistant/context-capsules"),
        api("/api/assistant/model-packs"),
        api("/api/assistant/handoffs"),
        api("/api/assistant/model-requests"),
      ]);
      setAssistantProfile(nextProfile);
      setAssistantCapabilities(nextCapabilities);
      setAssistantPlans(nextPlans || { plans: [] });
      setAssistantContextCapsules(nextCapsules || { capsules: [] });
      const approvedCapsules = (nextCapsules?.capsules || []).filter((capsule) => capsule.status === "approved");
      setSelectedTaskContextCapsuleId((current) => approvedCapsules.some((capsule) => capsule.id === current) ? current : "");
      setAssistantModelPacks(nextPacks || { packs: [] });
      setAssistantHandoffs(nextHandoffs || { handoffs: [] });
      setAssistantModelRequests(Array.isArray(nextModelRequests) ? { requests: nextModelRequests } : nextModelRequests || { requests: [] });
      return { profile: nextProfile, capabilities: nextCapabilities, plans: nextPlans, contextCapsules: nextCapsules, modelPacks: nextPacks, handoffs: nextHandoffs };
    } catch (error) {
      setAssistantError(error.message);
      throw error;
    } finally {
      setAssistantLoading(false);
    }
  }

  async function requestAssistantModel(request) {
    const payload = request?.currentTarget
      ? Object.fromEntries(new FormData(request.currentTarget).entries())
      : request || {};
    try {
      const created = await postJson("/api/assistant/model-requests", payload);
      await loadAssistantData();
      setGlobalStatus("Assistant model request created for candidate review.");
      return created;
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function prepareAssistantModelRequest(requestId, candidateId) {
    const resolvedRequestId = typeof requestId === "object" ? requestId?.id : requestId;
    const resolvedCandidateId = typeof candidateId === "object" ? candidateId?.candidateId : candidateId;
    if (!resolvedRequestId || !resolvedCandidateId) return null;
    try {
      const selectedRequest = await postJson(
        `/api/assistant/model-requests/${encodeURIComponent(resolvedRequestId)}/select`,
        { candidateId: resolvedCandidateId },
      );
      await loadAssistantData();
      const candidate = selectedRequest?.selectedCandidate
        || selectedRequest?.recommendations?.find((item) => item.candidateId === resolvedCandidateId)
        || selectedRequest?.candidate
        || selectedRequest?.selectedCandidateSnapshot;
      const planSeed = candidate?.planSeed || {};
      const protocolId = candidate?.protocolId || planSeed.protocolId;
      const profile = planSeed.strengthProfile || planSeed.profile || candidate?.profile || selectedRequest?.profile;
      if (!candidate?.catalogItem || !protocolId) {
        throw new Error("The selected Assistant model candidate has no deployable WarSat catalog plan.");
      }
      return await context.prepareCatalogModelForWarsat(candidate.catalogItem, {
        ...planSeed,
        protocolId,
        role: candidate.role || selectedRequest?.role,
        strengthProfile: assistantProfileToWarsatStrengthProfile(profile),
        assistantRequestId: resolvedRequestId,
      });
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function createAssistantPlan(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const operations = form.getAll("requestedOperations").map(String);
    try {
      await postJson("/api/assistant/plans", {
        objective: String(form.get("objective") || "").trim(),
        sessionId: String(form.get("contextSessionId") || "").trim() || undefined,
        contextQuery: String(form.get("contextQuery") || "").trim() || undefined,
        contextCapsuleId: String(form.get("contextCapsuleId") || "").trim() || undefined,
        modelPackId: String(form.get("modelPackId") || "").trim() || undefined,
        requestedOperations: operations,
      });
      await loadAssistantData();
      setGlobalStatus("Assistant plan created for review.");
      event.currentTarget.reset();
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function saveAssistantModelPack(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const roles = form.getAll("packRoles").map(String);
    const entries = (roles.length ? roles : ["main"]).map((role) => ({
      id: role.replace(/_/g, "-"),
      role,
      required: role === "main",
      capabilities: role === "speech_to_text" ? ["audio.transcribe"] : role === "text_to_speech" ? ["audio.synthesize"] : [role],
    }));
    try {
      await postJson("/api/assistant/model-packs", {
        packId: String(form.get("packId") || "").trim(),
        version: "0.1",
        entries,
      });
      await loadAssistantData();
      setGlobalStatus("Model pack saved without launching any models.");
      event.currentTarget.reset();
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function saveAssistantProfile(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const profile = await postJson("/api/assistant/profile", {
        displayName: String(form.get("displayName") || "Rasputin").trim() || "Rasputin",
        persona: {
          summary: String(form.get("personaSummary") || "").trim(),
          style: {
            tone: String(form.get("personaTone") || "dry"),
            sarcasm: String(form.get("personaSarcasm") || "light"),
            respectful: true,
          },
        },
      });
      setAssistantProfile(profile);
      setGlobalStatus("Assistant personality saved. Safety policy remains broker-only.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function reviewAssistantPlan(planId, status) {
    try {
      await postJson(`/api/assistant/plans/${encodeURIComponent(planId)}/${status === "approved" ? "approve" : "reject"}`, {});
      await loadAssistantData();
      setGlobalStatus(status === "approved" ? "Assistant plan approved for broker review." : "Assistant plan rejected.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function requestAssistantHandoff(planId, operation) {
    try {
      await postJson(`/api/assistant/plans/${encodeURIComponent(planId)}/handoffs`, { operation });
      await Promise.allSettled([loadAssistantData(), context.refreshApprovals()]);
      setGlobalStatus("Broker handoff recorded. No host action has started.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function prepareAssistantHandoff(handoffId) {
    try {
      await postJson(`/api/assistant/handoffs/${encodeURIComponent(handoffId)}/prepare`, {});
      await loadAssistantData();
      setGlobalStatus("Broker handoff prepared. No host action has started.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function dispatchAssistantHandoff(handoffId, operation) {
    try {
      await postJson(`/api/assistant/handoffs/${encodeURIComponent(handoffId)}/dispatch`, {});
      await Promise.allSettled([loadAssistantData(), context.refreshApprovals()]);
      setGlobalStatus(operation === "open_vscode"
        ? "VS Code launch dispatched for the approved workspace."
        : operation === "start_coding_task"
          ? "Governed Code task started from the approved Assistant handoff."
          : "Read-only Docker status collected. No container mutation was requested.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function previewAssistantVoice(modelPackId = "") {
    try {
      const preview = await postJson("/api/assistant/voice-preview", modelPackId ? { modelPackId } : {});
      setAssistantVoicePreview(preview);
      setGlobalStatus(preview.ready ? "Voice loop is ready for an approved local audio adapter." : "Voice loop readiness checked; resolve the listed model blockers first.");
      return preview;
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function previewAssistantCommand(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const command = String(form.get("assistantCommand") || "").trim();
    if (!command) return;
    try {
      const preview = await postJson("/api/assistant/command-preview", {
        command,
        workspacePath: workspace.activePath || ".",
      });
      setAssistantCommandPreview(preview);
      setGlobalStatus(preview.route?.status === "recognized"
        ? "Command recognized; review is required before any broker handoff."
        : "Command stayed in preview and was not executed.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function previewAssistantContext(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const preview = await postJson("/api/assistant/context-preview", {
        objective: String(form.get("contextObjective") || "").trim(),
        contextQuery: String(form.get("contextQuery") || "").trim() || undefined,
        sessionId: String(form.get("contextSessionId") || "").trim() || undefined,
        workspacePath: workspace.activePath || ".",
      });
      setAssistantContextPreview(preview);
      setGlobalStatus("Context preview refreshed; sensitive items remain excluded by default.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function createAssistantContextCapsule(contextPreview) {
    try {
      await postJson("/api/assistant/context-capsules", {
        objective: contextPreview?.query || "Shared context",
        contextQuery: contextPreview?.query || undefined,
        sessionId: contextPreview?.selectedSession?.id || undefined,
        workspacePath: contextPreview?.workspaceRef || workspace.activePath || ".",
      });
      await loadAssistantData();
      setGlobalStatus("Context capsule saved for explicit review.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  async function reviewAssistantContextCapsule(capsuleId, status) {
    try {
      await postJson(`/api/assistant/context-capsules/${encodeURIComponent(capsuleId)}/${status === "approved" ? "approve" : "reject"}`, {});
      await loadAssistantData();
      setGlobalStatus(status === "approved" ? "Context capsule approved for plan use." : "Context capsule rejected.");
    } catch (error) {
      setAssistantError(error.message);
      setGlobalStatus(error.message);
    }
  }

  return { loadAssistantData, requestAssistantModel, prepareAssistantModelRequest, createAssistantPlan, saveAssistantModelPack, saveAssistantProfile, reviewAssistantPlan, requestAssistantHandoff, prepareAssistantHandoff, dispatchAssistantHandoff, previewAssistantVoice, previewAssistantCommand, previewAssistantContext, createAssistantContextCapsule, reviewAssistantContextCapsule };
}
