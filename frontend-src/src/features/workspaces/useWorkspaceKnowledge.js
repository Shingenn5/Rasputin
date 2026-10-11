export function useWorkspaceKnowledge(context) {
  const {
    activeId,
    saveWorkspaceCommands,
    setCommandsBusy,
    setCommandsStatus,
    commandDraft,
    setSelectedEntry,
    setPreview,
    setPreviewError,
    setPreviewMode,
    setPreviewLoading,
    previewWorkspaceFile,
    currentRoot,
    browseWorkspace,
    indexWorkspaceKnowledge,
    executeAction,
    workspaceBrowse,
    workspace,
    setKnowledgeStatus,
    refreshKnowledgeStats,
    setUiState,
    exportWorkspaceGraphToObsidian,
    activeReadOnly,
    taskAccess,
    knowledgeQuery,
    searchWorkspaceKnowledge,
    setKnowledgeResults,
  } = context;

  async function submitWorkspaceCommands(event) {
    event.preventDefault();
    if (!activeId || !saveWorkspaceCommands) return;
    setCommandsBusy(true);
    setCommandsStatus("Saving validation commands...");
    try {
      await saveWorkspaceCommands(activeId, commandDraft);
      setCommandsStatus("Validation commands saved. Code-mode edits can now run these checks.");
    } catch (error) {
      setCommandsStatus(error.message);
    } finally {
      setCommandsBusy(false);
    }
  }

  async function inspectEntry(entry) {
    setSelectedEntry(entry);
    setPreview(null);
    setPreviewError("");
    if (entry.kind !== "file" || !entry.previewable) return;
    try {
      setPreviewMode(true);
      setPreviewLoading(true);
      setPreview(await previewWorkspaceFile(currentRoot.id, entry.path));
    } catch (error) {
      setPreviewError(error.message);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function openEntry(entry) {
    if (entry.kind === "folder" || entry.kind === "parent") {
      await browseWorkspace(currentRoot.id, entry.path);
      return;
    }
    await inspectEntry(entry);
  }

  function closePreview() {
    setPreviewMode(false);
    setPreview(null);
  }

  async function indexCurrentFolder() {
    if (!indexWorkspaceKnowledge) return;
    try {
      await executeAction("IndexWorkspace", workspaceBrowse?.path || workspace.activePath || ".", async () => {
        setKnowledgeStatus("Indexing this workspace...");
        const result = await indexWorkspaceKnowledge(workspaceBrowse?.path || workspace.activePath || ".");
        const docs = result.ragResult?.docsIndexed || 0;
        const chunks = result.ragResult?.chunksIndexed || 0;
        setKnowledgeStatus(`Indexed ${docs} docs into ${chunks} local chunks, then rebuilt Graphify links.`);
        refreshKnowledgeStats?.();
      }, setUiState);
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  async function exportCurrentGraphToObsidian() {
    if (!exportWorkspaceGraphToObsidian || activeReadOnly || !taskAccess) return;
    const path = workspaceBrowse?.path || workspace.activePath || ".";
    try {
      await executeAction("ExportGraphToObsidian", path, async () => {
        setKnowledgeStatus("Refreshing the graph and exporting Obsidian notes...");
        const result = await exportWorkspaceGraphToObsidian(path);
        setKnowledgeStatus(
          `Exported ${result.nodesExported || 0} nodes and ${result.edgesExported || 0} relationships to ${result.relativePath || "Rasputin Graph/Index.md"}.`,
        );
      }, setUiState);
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  async function searchKnowledge(event) {
    event.preventDefault();
    if (!knowledgeQuery.trim() || !searchWorkspaceKnowledge) return;
    try {
      await executeAction("SearchKnowledge", knowledgeQuery.trim(), async () => {
        setKnowledgeStatus("Searching local knowledge...");
        const result = await searchWorkspaceKnowledge(knowledgeQuery.trim(), workspaceBrowse?.path || workspace.activePath || ".");
        setKnowledgeResults(result);
        const hits = result.ragResult?.hits?.length || 0;
        const nodes = result.graphResult?.nodes?.length || 0;
        setKnowledgeStatus(`${hits} retrieval hits and ${nodes} graph nodes found.`);
      }, setUiState);
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  return { submitWorkspaceCommands, openEntry, closePreview, indexCurrentFolder, exportCurrentGraphToObsidian, searchKnowledge };
}
