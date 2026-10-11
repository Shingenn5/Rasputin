import { api, postJson } from "../api/client.js";

import { displayWorkspaceName } from "../lib/display.js";

export function useWorkspaceActions(context) {
  const {
    setWorkspaceBrowse,
    setWorkspaceExplorer,
    workspace,
    setRagStats,
    setGraphStats,
    setWorkspace,
    loadWorkspaceRoots,
    workspaceBrowse,
    workspaceExplorer,
    setGlobalStatus,
    setMountPlan,
    setPendingMounts,
    setSecurity,
  } = context;

  async function browseWorkspace(rootId, path) {
    const browsed = await postJson("/api/workspace/browse", { rootId, path });
    setWorkspaceBrowse(browsed);
    setWorkspaceExplorer({ rootId, path: browsed.path });
  }

  async function previewWorkspaceFile(rootId, path) {
    return postJson("/api/workspace/preview-file", { rootId, path });
  }

  async function refreshKnowledgeStats(workspaceId) {
    // "RAG Indexed" is scoped to a single approved folder -- default to
    // whichever one is currently active rather than the combined total
    // across every folder, which is what made the count look frozen when
    // switching folders (it genuinely never changed).
    const scopeId = workspaceId !== undefined ? workspaceId : (workspace.activeId || workspace.active_id);
    const ragQuery = scopeId ? `?workspace_id=${encodeURIComponent(scopeId)}` : "";
    const [nextRagStats, nextGraphStats] = await Promise.all([
      api(`/api/rag/stats${ragQuery}`),
      api("/api/graph/stats"),
    ]);
    setRagStats(nextRagStats);
    setGraphStats(nextGraphStats);
    return { ragStats: nextRagStats, graphStats: nextGraphStats };
  }

  async function indexWorkspaceKnowledge(path) {
    const targetPath = path || workspace.activePath || ".";
    const ragResult = await postJson("/api/rag/ingest", { path: targetPath, label: displayWorkspaceName(targetPath) });
    const graphResult = await postJson("/api/graph/build", { path: targetPath });
    await refreshKnowledgeStats();
    setWorkspace(await api("/api/workspace"));
    await loadWorkspaceRoots(targetPath, { rootId: workspaceBrowse?.root?.id || workspaceExplorer?.rootId, path: targetPath });
    setGlobalStatus(`Knowledge indexed for ${displayWorkspaceName(targetPath)}.`);
    return { ragResult, graphResult };
  }

  async function exportWorkspaceGraphToObsidian(path) {
    const targetPath = path || workspace.activePath || ".";
    const result = await postJson("/api/graph/export-obsidian", { path: targetPath });
    await refreshKnowledgeStats();
    setWorkspace(await api("/api/workspace"));
    await loadWorkspaceRoots(targetPath, {
      rootId: workspaceBrowse?.root?.id || workspaceExplorer?.rootId,
      path: targetPath,
    });
    setGlobalStatus(`Exported ${result.nodesExported || 0} graph nodes to Obsidian.`);
    return result;
  }

  async function searchWorkspaceKnowledge(query, path) {
    const targetPath = path || workspace.activePath || ".";
    const [ragResult, graphResult] = await Promise.all([
      postJson("/api/rag/search", { query, path: targetPath, limit: 5 }),
      postJson("/api/graph/search", { query, limit: 8 }),
    ]);
    return { ragResult, graphResult };
  }

  async function approvePath(path) {
    const approved = await postJson("/api/workspace/approve", {
      path,
      name: displayWorkspaceName(path),
      readOnly: true,
    });
    const active = await postJson("/api/workspace/select", { path: approved.id || path });
    setWorkspace(active);
    await loadWorkspaceRoots(active.activePath);
  }

  async function selectWorkspace(path) {
    try {
      const active = await postJson("/api/workspace/select", { path });
      setWorkspace(active);
      // Fire-and-forget: the knowledge panel should catch up to the newly
      // active folder, but switching folders shouldn't wait on it -- this
      // path is already slow enough without adding a blocking round trip.
      refreshKnowledgeStats(active.activeId || active.active_id).catch(() => {});
      // Explicitly point at the just-activated root rather than relying on
      // loadWorkspaceRoots' default (the closure's workspaceExplorer, which
      // is still the *previous* root at this point) -- otherwise it browses
      // the old folder and overwrites the explorer back to it a moment
      // after the switch, undoing the click.
      await loadWorkspaceRoots(active.activePath, { rootId: active.activeId || active.active_id, path: undefined });
      setGlobalStatus(`Workspace set to ${active.activeName || displayWorkspaceName(active.activePath)}.`);
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function setWorkspaceTrust(workspaceId, trusted) {
    try {
      await postJson("/api/workspace/trust", { workspaceId, trusted });
      setWorkspace(await api("/api/workspace"));
      await loadWorkspaceRoots(workspace.activePath);
      setGlobalStatus(
        trusted
          ? "Trusted Dev Mode enabled. File writes and git run without per-action approval in this workspace."
          : "Trusted Dev Mode revoked for this workspace."
      );
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function setWorkspaceHostShell(workspaceId, enabled) {
    try {
      await postJson("/api/workspace/host-shell", { workspaceId, enabled });
      setWorkspace(await api("/api/workspace"));
      await loadWorkspaceRoots(workspace.activePath);
      setGlobalStatus(
        enabled ? "Host Shell enabled. The agent can run commands on your machine in this workspace." : "Host Shell disabled for this workspace."
      );
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function saveWorkspaceCommands(workspaceId, commands) {
    try {
      const result = await postJson("/api/workspace/commands", {
        workspaceId,
        test: commands.test,
        build: commands.build,
        lint: commands.lint,
      });
      // The command save is complete once its own endpoint returns. Refresh
      // the workspace snapshot in the background so a slow browse/scan cannot
      // leave the settings form stuck on "Saving...".
      api("/api/workspace").then(setWorkspace).catch(() => {});
      setGlobalStatus("Workspace validation commands saved.");
      return result;
    } catch (error) {
      setGlobalStatus(error.message);
      throw error;
    }
  }

  async function previewMount(event) {
    event.preventDefault();
    // Callers pass either a real form submit event or a synthetic
    // { currentTarget: FormData } (WorkspacesView's guided modal).
    const source = event.currentTarget;
    const form = source instanceof FormData ? source : new FormData(source);
    try {
      const plan = await postJson("/api/workspace/mount-plan", {
        hostPath: form.get("hostPath"),
        name: form.get("name") || undefined,
        readOnly: form.get("readOnly") === "on",
      });
      setMountPlan(plan);
      return plan;
    } catch (error) {
      setMountPlan({ error: error.message });
      throw error;
    }
  }

  async function requestMount(plan) {
    if (!plan?.hostPath) return null;
    try {
      const saved = await postJson("/api/workspace/mount-apply", {
        hostPath: plan.hostPath,
        name: plan.displayName || undefined,
        readOnly: !!plan.readOnly,
      });
      setMountPlan({ ...saved, saved: true });
      setGlobalStatus(saved.registered
        ? `Project opened: ${saved.displayName || saved.hostPath}.`
        : saved.composeWritten
          ? `Mount saved and written to ${saved.composeFile}. Restart Rasputin to pick up ${saved.displayName || "the folder"}.`
          : "Mount request saved. Restart Rasputin with the generated volume before browsing that folder.");
      loadPendingMounts().catch(() => {});
      return saved;
    } catch (error) {
      setMountPlan({ ...plan, applyError: error.message });
      setGlobalStatus(error.message);
      throw error;
    }
  }

  async function loadPendingMounts() {
    // Legacy mount requests are unavailable on native hosts. This may also
    // run before bootstrap finishes; an empty panel is the safe fallback.
    try {
      const payload = await api("/api/workspace/mount-requests");
      setPendingMounts(payload.requests || []);
      return payload;
    } catch {
      setPendingMounts([]);
      return { requests: [] };
    }
  }

  async function removePendingMount(hostPath, options = {}) {
    try {
      const result = await postJson("/api/workspace/mount-requests/remove", { hostPath });
      setPendingMounts(result.requests || []);
      if (!options.silent) setGlobalStatus("Pending mount removed.");
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function approvePendingMount(item) {
    if (!item?.containerPath) return;
    try {
      await approvePath(item.containerPath);
      // Don't remove the underlying mount registration here: it's the only
      // record of which host folder this container path came from, and it
      // must keep producing a Compose volume line on every future restart
      // or the now-approved workspace goes empty. loadPendingMounts() just
      // re-filters the panel -- the server already hides entries that match
      // an approved workspace, so this one naturally drops off the list.
      await loadPendingMounts();
      setGlobalStatus(`${item.displayName || displayWorkspaceName(item.hostPath)} approved as a workspace.`);
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function saveSafety(event) {
    let payload = event;
    if (event?.preventDefault) {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const keys = [
        "privacyLock", "allowFileRead", "allowFileWrite", "allowFileReorganize", "allowShellExecution",
        "allowWebSearch", "allowDockerControl", "allowModelTests", "allowModelRegistryEdit", "allowRemoteModels",
        "approvalRequiredFileWrite", "approvalRequiredFileMove", "approvalRequiredWebSearch", "auditEnabled",
      ];
      payload = Object.fromEntries(keys.map((key) => [key, form.get(key) === "on"]));
      payload.webSearchMaxChars = Number(form.get("webSearchMaxChars") || 180);
    }
    setSecurity(await postJson("/api/security", payload));
    setGlobalStatus("Safety settings saved.");
  }

  return { browseWorkspace, previewWorkspaceFile, refreshKnowledgeStats, indexWorkspaceKnowledge, exportWorkspaceGraphToObsidian, searchWorkspaceKnowledge, approvePath, selectWorkspace, setWorkspaceTrust, setWorkspaceHostShell, saveWorkspaceCommands, previewMount, requestMount, loadPendingMounts, removePendingMount, approvePendingMount, saveSafety };
}
