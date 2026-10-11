import { api, postJson } from "../api/client.js";

export function useArchiveTrialActions(context) {
  const {
    setArchiveSessions,
    setArchiveStatus,
    workspace,
    setTrialsRuns,
    setSetup,
    setTrialsStatus,
    modeModelOverridesRef,
    setModeModelOverrides,
    taskMode,
    setSelectedModel,
  } = context;

  async function loadArchive() {
    const nextArchive = await api("/api/archive/sessions");
    setArchiveSessions(nextArchive);
    return nextArchive;
  }

  async function saveArchiveDraft(payload) {
    setArchiveStatus("");
    const saved = await postJson("/api/archive/sessions", payload);
    const nextArchive = await loadArchive();
    setArchiveStatus(`Saved ${saved.title}.`);
    return { saved, archive: nextArchive };
  }

  async function exportArchiveDraft(id) {
    setArchiveStatus("");
    const exported = await postJson("/api/archive/export", { id });
    setArchiveStatus(`Exported to ${exported.path}.`);
    return exported;
  }

  async function searchArchiveCitations(query) {
    const targetPath = workspace.activePath || ".";
    return postJson("/api/archive/citations", {
      query,
      path: targetPath,
      limit: 6,
    });
  }

  async function loadTrials() {
    const nextTrials = await api("/api/trials");
    setTrialsRuns(nextTrials);
    return nextTrials;
  }

  async function refreshSetupStatus() {
    const nextSetup = await api("/api/setup/status");
    setSetup(nextSetup);
    return nextSetup;
  }

  async function runTrialCompare(payload) {
    setTrialsStatus("Running blind comparison.");
    const run = await postJson("/api/trials/compare", payload);
    const nextTrials = await loadTrials();
    setTrialsStatus(`Trial ${run.id} finished.`);
    return { run, trials: nextTrials };
  }

  async function revealTrial(runId) {
    const run = await postJson(`/api/trials/${runId}/reveal`, {});
    await loadTrials();
    setTrialsStatus(`Revealed trial ${run.id}.`);
    return run;
  }

  async function saveTrialRoute(runId, outputId, mode) {
    const result = await postJson(`/api/trials/${runId}/routing`, { outputId, mode });
    const route = result.route || {};
    const routeModelKey = route.modelKey || route.model_key;
    const overrides = result.preferences?.modeModelOverrides || result.preferences?.mode_model_overrides || (
      routeModelKey ? { ...modeModelOverridesRef.current, [mode]: routeModelKey } : modeModelOverridesRef.current
    );
    modeModelOverridesRef.current = overrides;
    setModeModelOverrides(overrides);
    await postJson("/api/preferences", { modeModelOverrides: overrides });
    if (mode === taskMode && routeModelKey) {
      setSelectedModel(routeModelKey);
    }
    await loadTrials();
    setTrialsStatus(`Saved ${route.modelName || route.model_name || routeModelKey || "model route"} for ${mode}.`);
    return result;
  }

  return { loadArchive, saveArchiveDraft, exportArchiveDraft, searchArchiveCitations, loadTrials, refreshSetupStatus, runTrialCompare, revealTrial, saveTrialRoute };
}
