import React, { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronRight,
  Copy,
  Database,
  Eye,
  File,
  FileText,
  Folder,
  FolderOpen,
  HardDrive,
  Info,
  Lock,
  PlusCircle,
  RefreshCw,
  Shield,
} from "lucide-react";
import { displayWorkspaceName } from "../../lib/display.js";
import { GraphEdgeCard, GraphNodeCard } from "../knowledge/GraphEvidence.jsx";

export function WorkspacesView({
  view,
  workspace,
  workspaceRoots,
  workspaceBrowse,
  browseWorkspace,
  previewWorkspaceFile,
  approvePath,
  selectWorkspace,
  loadWorkspaceRoots,
  previewMount,
  requestMount,
  mountPlan,
  security,
  ragStats,
  graphStats,
  indexWorkspaceKnowledge,
  searchWorkspaceKnowledge,
  refreshKnowledgeStats,
  setPrompt,
}) {
  const [filter, setFilter] = useState("");
  const [quickAddError, setQuickAddError] = useState("");
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState("");
  const [knowledgeResults, setKnowledgeResults] = useState(null);
  const [mountStatus, setMountStatus] = useState("");
  const activeName = workspace.activeName || displayWorkspaceName(workspace.activePath);
  const activePath = workspace.absolutePath || workspace.activePath || ".";
  const activeId = workspace.activeId || workspace.active_id;
  const activeWorkspaceInfo = workspace.workspaces?.find((item) => item.id === activeId || item.root === workspace.activePath) || {};
  const activeReadOnly = activeWorkspaceInfo.readOnly ?? activeWorkspaceInfo.read_only;
  const activeIndexed = activeWorkspaceInfo.indexed;
  const entries = workspaceBrowse?.entries || [];
  const currentRoot = workspaceBrowse?.root || {};
  const currentFolder = workspaceBrowse?.displayName || displayWorkspaceName(workspaceBrowse?.path);
  const currentPath = workspaceBrowse?.path || workspace.activePath || ".";
  const filteredEntries = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return entries;
    return entries.filter((entry) => String(entry.displayName || entry.name || "").toLowerCase().includes(query));
  }, [entries, filter]);
  const breadcrumbs = useMemo(() => buildBreadcrumbs(currentRoot, workspaceBrowse?.path), [currentRoot, workspaceBrowse?.path]);
  const ragHits = knowledgeResults?.ragResult?.hits || [];
  const graphNodes = knowledgeResults?.graphResult?.nodes || [];
  const graphEdges = knowledgeResults?.graphResult?.edges || [];
  const workflowSteps = [
    {
      label: "Select",
      text: activeName || "No workspace selected",
      complete: Boolean(workspace.activePath),
    },
    {
      label: "Browse",
      text: currentFolder || "Open an approved folder",
      complete: Boolean(workspaceBrowse),
    },
    {
      label: "Preview",
      text: preview ? "Safe file preview loaded" : selectedEntry?.kind === "file" ? "File selected" : "Pick a text or code file",
      complete: Boolean(preview),
    },
    {
      label: "Index",
      text: activeIndexed ? "Workspace marked indexed" : "Run index for this folder",
      complete: Boolean(activeIndexed),
    },
    {
      label: "Search",
      text: knowledgeResults ? `${ragHits.length} RAG hits, ${graphNodes.length + graphEdges.length} graph items` : "Search after indexing",
      complete: Boolean(knowledgeResults),
    },
  ];

  useEffect(() => {
    setSelectedEntry(null);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(false);
    setKnowledgeResults(null);
    setKnowledgeStatus("");
  }, [workspaceBrowse?.path, currentRoot?.id]);

  async function addVisibleFolder(event) {
    event.preventDefault();
    setQuickAddError("");
    const form = new FormData(event.currentTarget);
    const path = String(form.get("path") || "").trim();
    if (!path) {
      setQuickAddError("Enter a folder path that Rasputin can already see.");
      return;
    }
    try {
      await approvePath(path);
      event.currentTarget.reset();
    } catch (error) {
      setQuickAddError(error.message);
    }
  }

  async function inspectEntry(entry) {
    setSelectedEntry(entry);
    setPreview(null);
    setPreviewError("");
    if (entry.kind !== "file" || !entry.previewable) return;
    try {
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

  async function indexCurrentFolder() {
    if (!indexWorkspaceKnowledge) return;
    try {
      setKnowledgeStatus("Indexing this folder...");
      const result = await indexWorkspaceKnowledge(workspaceBrowse?.path || workspace.activePath || ".");
      const docs = result.ragResult?.docsIndexed || 0;
      const chunks = result.ragResult?.chunksIndexed || 0;
      setKnowledgeStatus(`Indexed ${docs} docs into ${chunks} local chunks, then rebuilt Graphify links. Stored locally in data/rag_index.json and data/graph.json.`);
      refreshKnowledgeStats?.();
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  async function copyMountVolume() {
    if (!mountPlan?.composeVolume) return;
    try {
      await navigator.clipboard.writeText(mountPlan.composeVolume);
      setMountStatus("Volume line copied.");
    } catch {
      setMountStatus("Copy failed. Select and copy the volume line manually.");
    }
  }

  async function saveMountRequest() {
    if (!requestMount || !mountPlan || mountPlan.error) return;
    setMountStatus("");
    await requestMount(mountPlan);
  }

  async function searchKnowledge(event) {
    event.preventDefault();
    if (!knowledgeQuery.trim() || !searchWorkspaceKnowledge) return;
    try {
      setKnowledgeStatus("Searching local knowledge...");
      const result = await searchWorkspaceKnowledge(knowledgeQuery.trim(), workspaceBrowse?.path || workspace.activePath || ".");
      setKnowledgeResults(result);
      const hits = result.ragResult?.hits?.length || 0;
      const nodes = result.graphResult?.nodes?.length || 0;
      setKnowledgeStatus(`${hits} retrieval hits and ${nodes} graph nodes found.`);
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  function loadWorkspaceAnalysisPrompt() {
    if (!setPrompt) return;
    const folderName = displayWorkspaceName(currentPath);
    setPrompt(
      `Analyze the approved workspace "${folderName}". Use only local files, RAG citations, and Graphify evidence from ${currentPath}. Summarize what the folder contains, call out important files, and list any uncertainty.`,
      "analyze",
    );
  }

  return (
    <section
      className={`app-view workspaces-view ${view === "workspaces" ? "active" : ""}`}
      id="workspacesView"
      data-app-view="workspaces"
      aria-labelledby="workspacesTitle"
    >
      <header className="workspace-hero compact-workspace-hero">
        <div>
          <span className="eyebrow">Approved local folders</span>
          <h1 id="workspacesTitle">Workspaces</h1>
          <p>Choose exactly what Rasputin can see. Docker can only browse folders mounted into the wrapper, and new access starts read-only.</p>
        </div>
        <button className="secondary-action" type="button" onClick={loadWorkspaceRoots}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </header>

      <div className="workspace-layout explorer-layout">
        <aside className="workspace-side" aria-label="Approved folders">
          <section className="workspace-active-panel" aria-describedby="activeWorkspaceHelp">
            <div className="workspace-active-icon" aria-hidden="true">
              <Shield size={22} />
            </div>
            <div className="workspace-active-body">
              <span className="eyebrow">Active workspace</span>
              <h2>{activeName || "No workspace selected"}</h2>
              <p className="workspace-active-path">{displayPath(activePath)}</p>
              <dl className="workspace-active-meta">
                <div>
                  <dt>Access</dt>
                  <dd>{activeReadOnly ? "Read-only" : "Read/write"}</dd>
                </div>
                <div>
                  <dt>Knowledge</dt>
                  <dd>{activeIndexed ? "Indexed" : "Not indexed"}</dd>
                </div>
              </dl>
              <p id="activeWorkspaceHelp" className="workspace-help-text">
                Chat, file browsing, indexing, and Graphify use this workspace unless you choose another approved folder.
              </p>
            </div>
          </section>

          <details className="workspace-section workspace-quick-add">
            <summary>Add visible folder</summary>
            <div>
              <p>Use this for folders already mounted into the Rasputin container.</p>
            </div>
            <form className="quick-folder-form" onSubmit={addVisibleFolder}>
              <label>
                <span>Folder path</span>
                <input name="path" placeholder="workspace/my-project, backend, or data/imports" />
              </label>
              <button type="submit" className="send-text-button" aria-label="Approve visible folder">
                Approve folder
              </button>
            </form>
            <p className="workspace-help-text">
              Host folders that are not mounted yet need the mount preview below. New folders default to read-only.
            </p>
            {quickAddError && <p className="composer-status" role="alert">{quickAddError}</p>}
          </details>

          <section className="workspace-section">
            <div className="section-row">
              <div>
                <h2>Approved Folders</h2>
                <p>Folders already visible to the wrapper.</p>
              </div>
            </div>
            <div id="workspaceRootList" className="workspace-root-list">
              {workspaceRoots.map((root) => {
                const rootPath = root.path || root.root;
                const rootId = root.id;
                const info = workspace.workspaces?.find((item) => item.id === rootId || item.root === rootPath) || {};
                const displayName = root.displayName || root.display_name || root.name || displayWorkspaceName(rootPath);
                const absolutePath = root.absolutePath || root.absolute_path || rootPath;
                const active = rootId === activeId || normalizePath(rootPath) === normalizePath(workspace.activePath) || normalizePath(absolutePath) === normalizePath(workspace.absolutePath);
                const browsing = rootId === currentRoot.id || normalizePath(rootPath) === normalizePath(currentRoot.path);
                const readOnly = root.readOnly ?? root.read_only;
                const indexed = info.indexed ?? root.indexed;
                return (
                  <article
                    className={`workspace-root-card ${active ? "is-active" : ""} ${browsing ? "is-browsing" : ""}`}
                    key={rootId}
                    data-testid="workspace-root-card"
                  >
                    <button type="button" className="workspace-root-main" onClick={() => browseWorkspace(rootId)}>
                      <FolderOpen size={18} />
                      <span>
                        <strong>{displayName}</strong>
                        <small>{displayPath(absolutePath)}</small>
                      </span>
                    </button>
                    <div className="workspace-root-actions">
                      <span className={`workspace-permission ${readOnly ? "is-readonly" : "is-write"}`}>
                        {readOnly ? <Lock size={13} /> : <Check size={13} />}
                        {readOnly ? "Read-only" : "Read/write"}
                      </span>
                      <span className="workspace-permission">
                        {indexed ? "Indexed" : "Not indexed"}
                      </span>
                      <button
                        type="button"
                        className={active ? "tiny-action is-active" : "tiny-action"}
                        onClick={() => selectWorkspace(rootId || rootPath)}
                        aria-label={active ? `${displayName} is the active workspace` : `Use ${displayName} as active workspace`}
                      >
                        {active ? "Active workspace" : "Use as workspace"}
                      </button>
                    </div>
                  </article>
                );
              })}
              {!workspaceRoots.length && (
                <div className="empty-panel">
                  <h2>No approved folders</h2>
                  <p>Refresh once the wrapper has mounted a workspace folder.</p>
                </div>
              )}
            </div>
          </section>
        </aside>

        <main className="workspace-main workspace-explorer-main" role="region" aria-label="Folder browser">
          <section className="workspace-browser" data-testid="workspace-browser">
            <div className="browser-head">
              <div>
                <span className="eyebrow">Browsing</span>
                <h2>{currentFolder || "Approved folder"}</h2>
                <div id="workspaceBreadcrumb" className="workspace-breadcrumb" aria-label="Folder breadcrumb">
                  {breadcrumbs.map((crumb, index) => (
                    <React.Fragment key={crumb.path || "root"}>
                      {index > 0 && <ChevronRight size={14} aria-hidden="true" />}
                      <button type="button" onClick={() => browseWorkspace(currentRoot.id, crumb.path)}>
                        {crumb.label}
                      </button>
                    </React.Fragment>
                  ))}
                </div>
              </div>
              <button
                className="send-text-button"
                type="button"
                onClick={() => approvePath(workspaceBrowse?.path || workspace.activePath || ".")}
                aria-label="Use the currently browsed folder as active workspace"
              >
                Use folder as workspace
              </button>
            </div>
            <label className="workspace-search">
              <span className="visually-hidden">Filter folder contents</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Filter folders and files"
                aria-label="Filter visible folders and files"
              />
            </label>

            <div id="workspaceEntries" className="workspace-entry-list" role="list">
              {filteredEntries.map((entry) => (
                <div
                  className={`workspace-entry-row ${selectedEntry?.path === entry.path ? "is-selected" : ""}`}
                  role="listitem"
                  key={`${entry.kind}-${entry.path}`}
                  data-testid="workspace-file-row"
                >
                  <button
                    type="button"
                    className="workspace-entry-name"
                    onClick={() => openEntry(entry)}
                  >
                    <EntryIcon entry={entry} />
                    <span>
                      <strong>{entry.displayName || entry.name}</strong>
                      <small>{entry.kind === "file" ? `${entry.extension || "file"} / ${formatBytes(entry.sizeBytes)}` : entry.kind}</small>
                    </span>
                  </button>
                  <span className="workspace-entry-meta">{formatTime(entry.modifiedAt)}</span>
                  {entry.kind === "folder" && (
                    <button
                      type="button"
                      className="tiny-action"
                      onClick={() => approvePath(entry.path)}
                      aria-label={`Use ${entry.displayName || entry.name} as workspace`}
                    >
                      Use as workspace
                    </button>
                  )}
                  {entry.kind === "file" && entry.previewable && (
                    <button type="button" className="tiny-action" onClick={() => inspectEntry(entry)}>
                      <Eye size={13} />
                      Preview
                    </button>
                  )}
                </div>
              ))}
              {!filteredEntries.length && (
                <div className="empty-panel compact">
                  <h2>{entries.length ? "No matching items" : "No visible items"}</h2>
                  <p>{entries.length ? "Clear the filter to see every visible file and folder." : "This folder is selectable, but there are no visible child items."}</p>
                </div>
              )}
            </div>
          </section>
        </main>

        <aside className="workspace-preview-panel" data-testid="workspace-preview-panel" aria-label="File preview and knowledge">
          <section className="workspace-section workspace-knowledge-flow" data-testid="workspace-knowledge-flow">
            <div className="section-row">
              <div>
                <span className="eyebrow">Local File Test Flow</span>
                <h2>Prove Rasputin can use this folder</h2>
                <p>Select a mounted folder, preview a safe file, index it locally, search evidence, then load an analyze task.</p>
              </div>
            </div>
            <ol className="knowledge-flow-list" aria-label="Workspace knowledge test steps">
              {workflowSteps.map((step) => (
                <li className={step.complete ? "is-complete" : ""} key={step.label}>
                  <span>{step.label}</span>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>
            <button
              type="button"
              className="secondary-action"
              onClick={loadWorkspaceAnalysisPrompt}
              data-testid="workspace-load-analysis-prompt"
            >
              Load analyze task
            </button>
          </section>

          <section className="workspace-section workspace-knowledge-panel" data-testid="workspace-knowledge-panel">
            <div className="section-row">
              <div>
                <span className="eyebrow">Knowledge</span>
                <h2>Index current folder</h2>
                <p>Build local retrieval and relationship data for the folder you are actually working in.</p>
              </div>
            </div>
            <div className="knowledge-explainer" role="note">
              <Info size={16} aria-hidden="true" />
              <p>
                Indexing reads supported text, code, PDF, DOCX, and XLSX files from this folder, splits them into searchable cited chunks, writes local retrieval data to <code>data/rag_index.json</code>, then refreshes Graphify relationships in <code>data/graph.json</code>. It does not send file contents to the internet.
              </p>
            </div>
            <div className="knowledge-stat-grid">
              <Metric label="Docs" value={ragStats?.docs ?? 0} />
              <Metric label="Chunks" value={ragStats?.chunks ?? 0} />
              <Metric label="Nodes" value={graphStats?.nodes ?? 0} />
              <Metric label="Edges" value={graphStats?.edges ?? 0} />
            </div>
            <div className="workspace-action-row">
              <button type="button" className="send-text-button" onClick={indexCurrentFolder} data-testid="workspace-index-folder">
                Index current folder
              </button>
              <button type="button" className="secondary-action" onClick={refreshKnowledgeStats}>
                Refresh stats
              </button>
            </div>
            <form className="knowledge-search-form" onSubmit={searchKnowledge}>
              <label>
                <span className="visually-hidden">Search local knowledge</span>
                <input
                  value={knowledgeQuery}
                  onChange={(event) => setKnowledgeQuery(event.target.value)}
                  placeholder="Search indexed files and graph links"
                />
              </label>
              <button type="submit" className="secondary-action" data-testid="workspace-knowledge-search">Search</button>
            </form>
            {knowledgeStatus && <p className="workspace-help-text" role="status">{knowledgeStatus}</p>}
            {knowledgeResults && (
              <div className="knowledge-result-stack">
                <div className="knowledge-result-group" data-testid="workspace-rag-results">
                  <h3>RAG retrieval hits</h3>
                  {ragHits.slice(0, 3).map((hit) => (
                    <article className="knowledge-result-card" key={`${hit.source}-${hit.chunk}`}>
                      <span className="knowledge-result-type">Citation</span>
                      <strong>{hit.path}</strong>
                      <small>Lines {hit.lineStart}-{hit.lineEnd}</small>
                      <p>{hit.text}</p>
                    </article>
                  ))}
                  {!ragHits.length && <p className="workspace-help-text">No retrieval hits for this query.</p>}
                </div>
                <div className="knowledge-result-group" data-testid="workspace-graph-results">
                  <h3>Graphify evidence</h3>
                  {graphNodes.slice(0, 3).map((node) => (
                    <GraphNodeCard node={node} compact key={node.id} />
                  ))}
                  {graphEdges.slice(0, 3).map((edge) => (
                    <GraphEdgeCard edge={edge} compact key={`${edge.sourceId || edge.source}-${edge.relation}-${edge.targetId || edge.target}`} />
                  ))}
                  {!graphNodes.length && !graphEdges.length && <p className="workspace-help-text">No graph relationships for this query.</p>}
                </div>
              </div>
            )}
          </section>

          <section className="workspace-section preview-section">
            <div className="section-row">
              <div>
                <span className="eyebrow">Selection</span>
                <h2>{selectedEntry ? selectedEntry.displayName || selectedEntry.name : "No file selected"}</h2>
                <p>{selectedEntry ? displayPath(selectedEntry.path) : "Pick a folder to browse or a file to preview."}</p>
              </div>
            </div>
            {selectedEntry && (
              <dl className="preview-meta-grid">
                <dt>Kind</dt><dd>{selectedEntry.kind}</dd>
                <dt>Size</dt><dd>{formatBytes(selectedEntry.sizeBytes)}</dd>
                <dt>Modified</dt><dd>{formatTime(selectedEntry.modifiedAt)}</dd>
                <dt>Access</dt><dd>{selectedEntry.readOnly ? "Read-only" : "Read/write root"}</dd>
              </dl>
            )}
            {previewLoading && <p className="workspace-help-text">Loading preview...</p>}
            {previewError && <p className="composer-status" role="alert">{previewError}</p>}
            {selectedEntry?.kind === "file" && !selectedEntry.previewable && (
              <p className="workspace-help-text">This file type is visible but not previewable in the testing build.</p>
            )}
            {preview && (
              <pre className="workspace-file-preview"><code>{preview.content}</code></pre>
            )}
          </section>

          <details className="advanced-block workspace-section workspace-guide">
            <summary>
              <span>Access and index notes</span>
              <small>Docker mounts and local knowledge storage</small>
            </summary>
            <div className="guide-card">
              <HardDrive size={20} />
              <div>
                <h2>Mounted access only</h2>
                <p>Docker must already expose a host folder before Rasputin can browse it here.</p>
              </div>
            </div>
            <div className="guide-card">
              <Database size={20} />
              <div>
                <h2>Indexes stay local</h2>
                <p>RAG and Graphify data stay under local data storage.</p>
              </div>
            </div>
          </details>

          <details className="advanced-block workspace-mount-panel">
            <summary>
              <span>Mount a new host folder</span>
              <small>Generate a Docker-safe folder mount plan</small>
            </summary>
            <div className="mount-intro" role="note">
              <HardDrive size={17} aria-hidden="true" />
              <p>
                Rasputin cannot browse arbitrary host folders from inside Docker. This creates a mount plan for the next container restart. The default is read-only so the model can inspect files without write access.
              </p>
            </div>
            <form id="workspaceMountForm" className="mount-form" onSubmit={previewMount}>
              <label>
                <span>Host folder</span>
                <input id="mountHostPath" name="hostPath" placeholder={"C:\\Users\\you\\Project or /home/you/project"} />
              </label>
              <label>
                <span>Display name</span>
                <input name="name" placeholder="Project Documents" />
              </label>
              <label className="mount-access-choice">
                <input type="checkbox" name="readOnly" defaultChecked />
                <span>
                  <strong>Read-only container mount</strong>
                  <small>Recommended. Rasputin can inspect files, but cannot write to this mount.</small>
                </span>
              </label>
              <button className="send-text-button" type="submit" aria-label="Generate a Docker mount plan">
                <PlusCircle size={15} />
                Generate mount plan
                <ChevronRight size={15} />
              </button>
            </form>
            <div id="workspaceMountPlan" className="mount-plan" data-testid="workspace-mount-plan" aria-live="polite">
              {mountPlan && (mountPlan.error ? (
                <p className="composer-status">{mountPlan.error}</p>
              ) : (
                <div className="mount-plan-card">
                  <div>
                    <strong>{mountPlan.displayName}</strong>
                    <small>{mountPlan.message || "Restart required before this folder is visible."}</small>
                  </div>
                  <dl className="mount-plan-grid">
                    <dt>Host folder</dt>
                    <dd>{mountPlan.hostPath}</dd>
                    <dt>Container path</dt>
                    <dd>{mountPlan.containerPath}</dd>
                    <dt>Volume line</dt>
                    <dd><code>{mountPlan.composeVolume}</code></dd>
                    <dt>Access</dt>
                    <dd>{mountPlan.readOnly ? "Read-only" : "Read/write"}</dd>
                  </dl>
                  <div className="mount-plan-actions">
                    <button type="button" className="secondary-action" onClick={copyMountVolume}>
                      <Copy size={15} />
                      Copy volume line
                    </button>
                    <button
                      type="button"
                      className="send-text-button"
                      onClick={saveMountRequest}
                      disabled={!security?.allowDockerControl}
                      aria-describedby="mountApplyHelp"
                    >
                      Save mount request
                    </button>
                  </div>
                  <p id="mountApplyHelp" className="workspace-help-text">
                    {security?.allowDockerControl
                      ? "Saving records this mount request locally. Rasputin still needs a restart with that volume before it can browse the folder."
                      : "Docker control is disabled, so Rasputin will not edit or restart containers. Copy the volume line into compose or enable Docker control intentionally in Safety settings."}
                  </p>
                  {mountPlan.applyError && <p className="composer-status" role="alert">{mountPlan.applyError}</p>}
                  {mountPlan.saved && <p className="workspace-help-text" role="status">Mount request saved locally in data/workspace.json.</p>}
                </div>
              ))}
              {mountStatus && <p className="workspace-help-text" role="status">{mountStatus}</p>}
            </div>
          </details>
        </aside>
      </div>
    </section>
  );
}

function displayPath(value) {
  const text = String(value || ".").trim();
  if (!text || text === ".") return "Project Root";
  return text;
}

function EntryIcon({ entry }) {
  if (entry.kind === "file") {
    return entry.previewable ? <FileText size={17} /> : <File size={17} />;
  }
  return <Folder size={17} />;
}

function Metric({ label, value }) {
  return (
    <div className="knowledge-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function buildBreadcrumbs(root, currentPath) {
  const rootLabel = root?.displayName || root?.display_name || root?.name || "Approved folder";
  const rootPath = normalizePath(root?.path || ".");
  const browsePath = normalizePath(currentPath || rootPath);
  const crumbs = [{ label: rootLabel, path: root?.path || "." }];
  if (!browsePath || browsePath === rootPath) return crumbs;
  const relative = rootPath === "." ? browsePath : browsePath.replace(`${rootPath}/`, "");
  const parts = relative.split("/").filter(Boolean);
  let current = rootPath === "." ? "" : rootPath;
  for (const part of parts) {
    current = current ? `${current}/${part}` : part;
    crumbs.push({ label: part, path: current });
  }
  return crumbs;
}

function normalizePath(value) {
  return String(value || ".").replace(/\\/g, "/").replace(/\/+$/g, "") || ".";
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (!size) return "0 B";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(value) {
  const stamp = Number(value || 0);
  if (!stamp) return "Not available";
  return new Date(stamp * 1000).toLocaleString();
}
