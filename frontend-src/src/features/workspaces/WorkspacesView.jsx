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
  Activity,
  AlertTriangle
} from "lucide-react";
import { displayWorkspaceName } from "../../lib/display.js";
import { GraphEdgeCard, GraphNodeCard } from "../knowledge/GraphEvidence.jsx";
import { actionRegistry, useReliableAction } from "../../lib/actionRegistry.js";

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
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState("");
  const [knowledgeResults, setKnowledgeResults] = useState(null);
  
  // Safe Folder Management State
  const [mountStep, setMountStep] = useState(0); // 0 = closed, 1-6 = steps
  const [mountHostPath, setMountHostPath] = useState("");
  const [mountReadOnly, setMountReadOnly] = useState(true);
  const [showAdvancedMount, setShowAdvancedMount] = useState(false);
  const [mountStatus, setMountStatus] = useState("");

  // Phase 10: Button Reliability Framework State
  const [uiState, setUiState] = useState({ status: 'idle', message: '' });
  const executeAction = useReliableAction("WorkspacesView");

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

  useEffect(() => {
    setSelectedEntry(null);
    setPreview(null);
    setPreviewError("");
    setPreviewLoading(false);
    setKnowledgeResults(null);
    setKnowledgeStatus("");
  }, [workspaceBrowse?.path, currentRoot?.id]);

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

  function launchTask(type) {
    if (!setPrompt) return;
    const folderName = displayWorkspaceName(currentPath);
    const path = currentPath;
    
    switch(type) {
      case 'summarize':
        setPrompt(`Summarize the contents and purpose of the approved workspace "${folderName}" at ${path}.`, "write");
        break;
      case 'analyze':
        setPrompt(`Analyze the approved workspace "${folderName}" at ${path}. Use local files, RAG citations, and Graphify evidence to summarize what the folder contains, call out important files, and list any uncertainty.`, "analyze");
        break;
      case 'search':
        setPrompt(`Search the workspace "${folderName}" for any security vulnerabilities or API keys left in the code.`, "analyze");
        break;
      case 'graph':
        setPrompt(`Review the Graphify relationships for the workspace "${folderName}". Identify any disjoint nodes or missing documentation links.`, "research");
        break;
      case 'docs':
        setPrompt(`Generate comprehensive documentation for the workspace "${folderName}" based on its indexed files.`, "write");
        break;
      case 'review':
        setPrompt(`Perform a code review on the active workspace "${folderName}". Point out any style violations or performance issues.`, "code");
        break;
      default:
        break;
    }
  }

  // --- Guided Mount Workflow ---
  async function handleGeneratePlan(e) {
    e.preventDefault();
    if (!mountHostPath) {
      setMountStatus("Host path is required.");
      return;
    }
    try {
      await executeAction("GenerateMountPlan", mountHostPath, async () => {
        const formData = new FormData();
        formData.append("hostPath", mountHostPath);
        formData.append("name", displayWorkspaceName(mountHostPath));
        if (mountReadOnly) {
          formData.append("readOnly", "on");
        }
        await previewMount({ preventDefault: () => {}, currentTarget: formData });
        setMountStep(4);
      }, setUiState);
    } catch (error) {
      setMountStatus(error.message);
    }
  }

  async function handleSaveMountRequest() {
    if (!requestMount || !mountPlan || mountPlan.error) return;
    try {
      await executeAction("SaveMountRequest", mountPlan.containerPath || mountPlan.hostPath, async () => {
        setMountStatus("");
        await requestMount(mountPlan);
        setMountStep(5);
      }, setUiState);
    } catch (error) {
      setMountStatus(error.message);
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

  return (
    <section
      className={`w2-layout app-view workspaces-view ${view === "workspaces" ? "active" : ""}`}
      id="workspacesView"
      data-app-view="workspaces"
    >
      {/* PHASE 1: Workspace Header Summary Card */}
      <div className="w2-header-card">
        <div>
          <h1>{activeName || "No workspace selected"}</h1>
          <p>{displayPath(activePath)}</p>
        </div>
        <div className="w2-header-stats">
          {/* Button Reliability Status Readout */}
          {uiState.status !== 'idle' && (
            <div style={{ 
              padding: '8px 16px', borderRadius: '4px', fontSize: '0.875rem',
              backgroundColor: uiState.status === 'failed' ? 'var(--ras-danger)' : 
                              uiState.status === 'success' ? 'var(--ras-safe)' : 'var(--cc-surface)',
              color: '#fff', display: 'flex', alignItems: 'center', marginRight: '16px'
            }}>
              {uiState.message}
            </div>
          )}
          <div className="w2-header-stat">
            <strong>{activeReadOnly ? "Read Only" : "Read / Write"}</strong>
            <small>Access Mode</small>
          </div>
          <div className="w2-header-stat">
            <strong>{activeIndexed ? "Indexed" : "Not Indexed"}</strong>
            <small>Index Status</small>
          </div>
          <div className="w2-header-stat">
            <strong>{graphStats?.nodes > 0 ? "Built" : "Not Built"}</strong>
            <small>Graph Status</small>
          </div>
          <div className="w2-header-stat">
            <strong>{ragStats?.docs || 0}</strong>
            <small>Files Indexed</small>
          </div>
        </div>
      </div>

      {/* PHASE 1: Three Column Layout */}
      <div className="w2-main-grid">
        
        {/* Column 1: Navigation */}
        <div className="w2-column w2-column-nav">
          <div className="w2-section">
            <h2 className="w2-section-title">Navigation</h2>
            <div className="w2-breadcrumbs">
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={crumb.path || "root"}>
                  {index > 0 && <ChevronRight size={14} />}
                  <button type="button" onClick={() => browseWorkspace(currentRoot.id, crumb.path)}>
                    {crumb.label}
                  </button>
                </React.Fragment>
              ))}
            </div>
            <input 
              className="w2-input" 
              placeholder="Search files and folders..." 
              value={filter} 
              onChange={e => setFilter(e.target.value)} 
            />
          </div>

          <div className="w2-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="w2-section-title">Approved Folders</h2>
              <button className="icon-button" type="button" onClick={loadWorkspaceRoots} aria-label="Refresh roots">
                <RefreshCw size={14} />
              </button>
            </div>
            
            <div className="w2-card" style={{ gap: '8px' }}>
              {workspaceRoots.map((root) => {
                const rootPath = root.path || root.root;
                const rootId = root.id;
                const displayName = root.displayName || root.display_name || root.name || displayWorkspaceName(rootPath);
                const active = rootId === activeId || normalizePath(rootPath) === normalizePath(workspace.activePath);
                const readOnly = root.readOnly ?? root.read_only;
                return (
                  <div key={rootId} className={`w2-list-item ${active ? 'is-active' : ''}`} onClick={() => browseWorkspace(rootId)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FolderOpen size={16} />
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{displayName}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--cc-muted)' }}>{readOnly ? "Read-only" : "Read/write"}</span>
                      </div>
                    </div>
                    {!active && (
                      <button className="w2-button" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={(e) => { e.stopPropagation(); selectWorkspace(rootId || rootPath); }}>
                        Set Active
                      </button>
                    )}
                  </div>
                );
              })}
              {workspaceRoots.length === 0 && <p style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>No approved folders.</p>}
              <button className="w2-button primary" style={{ marginTop: '8px' }} onClick={() => setMountStep(1)}>
                <PlusCircle size={16} /> Add Folder Workflow
              </button>
            </div>
          </div>

          {/* PHASE 4: Safe Folder Management (Guided Add Folder Workflow) */}
          {mountStep > 0 && (
            <div className="w2-section">
              <h2 className="w2-section-title">Add Folder Workflow</h2>
              <div className="w2-card">
                {mountStep === 1 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 1 of 6</span>
                    <h3>Select Host Folder</h3>
                    <input className="w2-input" value={mountHostPath} onChange={e => setMountHostPath(e.target.value)} placeholder="e.g. C:\Projects\MyRepo" />
                    <button className="w2-button primary" onClick={() => setMountStep(2)} disabled={!mountHostPath}>Next</button>
                    <button className="w2-button" onClick={() => setMountStep(0)}>Cancel</button>
                  </div>
                )}
                {mountStep === 2 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 2 of 6</span>
                    <h3>Preview Mount</h3>
                    <p style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>Rasputin runs in Docker. We will map this folder to the container.</p>
                    <button className="w2-button primary" onClick={() => setMountStep(3)}>Next</button>
                    <button className="w2-button" onClick={() => setMountStep(1)}>Back</button>
                  </div>
                )}
                {mountStep === 3 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 3 of 6</span>
                    <h3>Choose Access Mode</h3>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.875rem' }}>
                      <input type="radio" checked={mountReadOnly} onChange={() => setMountReadOnly(true)} />
                      Read Only (Default - Recommended)
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.875rem' }}>
                      <input type="radio" checked={!mountReadOnly} onChange={() => setMountReadOnly(false)} />
                      Read / Write (Allow Agent Edits)
                    </label>
                    <button className="w2-button primary" onClick={handleGeneratePlan}>Generate Plan (Next)</button>
                    <button className="w2-button" onClick={() => setMountStep(2)}>Back</button>
                  </div>
                )}
                {mountStep === 4 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 4 of 6</span>
                    <h3>Generated Mount Plan</h3>
                    {mountPlan && !mountPlan.error ? (
                      <div style={{ fontSize: '0.875rem', backgroundColor: 'var(--cc-bg)', padding: '8px', borderRadius: '4px' }}>
                        <div><strong>Container Path:</strong> {mountPlan.containerPath}</div>
                        <div><strong>Volume:</strong> <code>{mountPlan.composeVolume}</code></div>
                      </div>
                    ) : (
                      <p style={{ color: 'var(--ras-danger)', fontSize: '0.875rem' }}>{mountPlan?.error || "Error generating plan"}</p>
                    )}
                    <button className="w2-button primary" onClick={handleSaveMountRequest} disabled={!security?.allowDockerControl || !mountPlan || mountPlan.error}>Approve & Save (Next)</button>
                    {!security?.allowDockerControl && <p style={{ fontSize: '0.75rem', color: 'var(--ras-danger)' }}>Docker control disabled in safety settings.</p>}
                    <button className="w2-button" onClick={() => setMountStep(3)}>Back</button>
                  </div>
                )}
                {mountStep === 5 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 5 of 6</span>
                    <h3>Approval Complete</h3>
                    <p style={{ fontSize: '0.875rem' }}>The request has been saved locally.</p>
                    <button className="w2-button primary" onClick={() => setMountStep(6)}>Next</button>
                  </div>
                )}
                {mountStep === 6 && (
                  <div className="w2-guided-step">
                    <span className="w2-step-indicator">Step 6 of 6</span>
                    <h3>Restart Required</h3>
                    <p style={{ fontSize: '0.875rem', color: 'var(--cc-muted)' }}>You must restart the Rasputin container with the new volume mapping for it to take effect.</p>
                    <button className="w2-button" onClick={copyMountVolume}>Copy Volume Line</button>
                    <button className="w2-button primary" onClick={() => { setMountStep(0); loadWorkspaceRoots(); }}>Done</button>
                  </div>
                )}
              </div>
            </div>
          )}
          
          <div className="w2-section">
            <button className="w2-button" onClick={() => setShowAdvancedMount(!showAdvancedMount)}>
              {showAdvancedMount ? "Hide Advanced Section" : "Show Advanced Section"}
            </button>
            {showAdvancedMount && (
              <div className="w2-card" style={{ fontSize: '0.75rem' }}>
                <strong>Advanced Folder Setup</strong>
                <p>Manual Path Entry</p>
                <form onSubmit={(e) => { e.preventDefault(); approvePath(e.target.path.value); }}>
                  <input className="w2-input" name="path" placeholder="Enter path manually..." style={{ marginBottom: '8px' }} />
                  <button type="submit" className="w2-button">Approve</button>
                </form>
                {mountPlan && (
                  <div style={{ marginTop: '8px' }}>
                    <strong>Mount JSON:</strong>
                    <pre>{JSON.stringify(mountPlan, null, 2)}</pre>
                  </div>
                )}
              </div>
            )}
          </div>

        </div>

        {/* Column 2: Explorer */}
        <div className="w2-column w2-column-explorer">
          <div className="w2-section" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <h2 className="w2-section-title">File Explorer ({currentFolder})</h2>
            <div className="w2-card" style={{ flex: 1, overflowY: 'auto', gap: '8px' }}>
              {filteredEntries.map((entry) => (
                <div key={`${entry.kind}-${entry.path}`} className={`w2-list-item ${selectedEntry?.path === entry.path ? 'is-active' : ''}`} onClick={() => openEntry(entry)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <EntryIcon entry={entry} />
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>{entry.displayName || entry.name}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--cc-muted)' }}>
                        {entry.kind === "file" ? `${entry.extension || "file"} / ${formatBytes(entry.sizeBytes)}` : entry.kind}
                      </span>
                    </div>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--cc-muted)' }}>{formatTime(entry.modifiedAt)}</span>
                </div>
              ))}
              {filteredEntries.length === 0 && (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--cc-muted)' }}>
                  {entries.length ? "No matching items." : "Folder is empty or contents are hidden."}
                </div>
              )}
            </div>
            {selectedEntry && (
              <div className="w2-card" style={{ marginTop: '16px' }}>
                <h2 className="w2-section-title">File Details</h2>
                <div style={{ fontSize: '0.875rem', display: 'grid', gridTemplateColumns: '100px 1fr', gap: '8px' }}>
                  <strong style={{ color: 'var(--cc-muted)' }}>Name</strong> <span>{selectedEntry.name}</span>
                  <strong style={{ color: 'var(--cc-muted)' }}>Path</strong> <span>{selectedEntry.path}</span>
                  <strong style={{ color: 'var(--cc-muted)' }}>Size</strong> <span>{formatBytes(selectedEntry.sizeBytes)}</span>
                </div>
                {selectedEntry.kind === 'file' && selectedEntry.previewable && (
                  <button className="w2-button primary" onClick={() => inspectEntry(selectedEntry)} disabled={previewLoading}>
                    {previewLoading ? "Loading..." : "Preview File"}
                  </button>
                )}
                {previewError && <p style={{ color: 'var(--ras-danger)', fontSize: '0.875rem' }}>{previewError}</p>}
              </div>
            )}
            {preview && (
              <div className="w2-preview-block" style={{ marginTop: '16px' }}>
                {preview.content}
              </div>
            )}
          </div>
        </div>

        {/* Column 3: Intelligence & Dashboard */}
        <div className="w2-column w2-column-intelligence">
          
          {/* PHASE 3: Active Workspace Dashboard (Health) */}
          <div className="w2-section">
            <h2 className="w2-section-title">Workspace Health</h2>
            <div className="w2-card w2-health-grid">
              <div className="w2-health-item is-good"><Check size={16}/> Folder Access</div>
              <div className={`w2-health-item ${activeIndexed ? 'is-good' : 'is-warn'}`}>
                {activeIndexed ? <Check size={16}/> : <AlertTriangle size={16}/>} RAG Index
              </div>
              <div className={`w2-health-item ${graphStats?.nodes > 0 ? 'is-good' : 'is-warn'}`}>
                {graphStats?.nodes > 0 ? <Check size={16}/> : <AlertTriangle size={16}/>} Graph DB
              </div>
              <div className="w2-health-item is-good"><Check size={16}/> Security</div>
            </div>
          </div>

          {/* PHASE 3: Active Workspace Dashboard (Activity) */}
          <div className="w2-section">
            <h2 className="w2-section-title">Recent Activity</h2>
            <div className="w2-card">
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '0.875rem' }}>
                <Activity size={16} color="var(--cc-muted)" /> <span style={{ color: 'var(--cc-muted)' }}>No recent task activity tracked yet.</span>
              </div>
            </div>
          </div>

          {/* PHASE 2: Workspace Knowledge Center */}
          <div className="w2-section">
            <h2 className="w2-section-title">Knowledge Operations</h2>
            <div className="w2-card">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <strong style={{ color: 'var(--cc-muted)' }}>RAG Indexed</strong>
                  <span>{ragStats?.docs || 0} files</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <strong style={{ color: 'var(--cc-muted)' }}>Graph Built</strong>
                  <span>{graphStats?.nodes || 0} nodes</span>
                </div>
              </div>
              
              <div className="w2-action-panel-grid" style={{ marginTop: '8px' }}>
                <button className="w2-button primary" onClick={indexCurrentFolder}>Index Workspace</button>
                <button className="w2-button" onClick={refreshKnowledgeStats}>Refresh Status</button>
              </div>

              {knowledgeStatus && <p style={{ fontSize: '0.75rem', margin: '8px 0 0 0', color: 'var(--cc-muted)' }}>{knowledgeStatus}</p>}

              <form onSubmit={searchKnowledge} style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                <input className="w2-input" value={knowledgeQuery} onChange={e => setKnowledgeQuery(e.target.value)} placeholder="Search index & graph..." />
                <button className="w2-button" type="submit">Search</button>
              </form>

              {knowledgeResults && (
                <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {ragHits.length > 0 && (
                    <div>
                      <strong style={{ fontSize: '0.875rem' }}>Local Knowledge Search</strong>
                      {ragHits.slice(0, 2).map((hit, i) => (
                        <div key={i} style={{ fontSize: '0.75rem', padding: '8px', backgroundColor: 'var(--cc-bg)', borderRadius: '4px', marginTop: '4px' }}>
                          <div style={{ fontWeight: 'bold' }}>{hit.path}</div>
                          <div>{hit.text.substring(0, 100)}...</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {graphNodes.length > 0 && (
                    <div>
                      <strong style={{ fontSize: '0.875rem' }}>Graph Search</strong>
                      {graphNodes.slice(0, 2).map(node => (
                        <div key={node.id} style={{ fontSize: '0.75rem', padding: '8px', backgroundColor: 'var(--cc-bg)', borderRadius: '4px', marginTop: '4px' }}>
                          Node: {node.id} ({node.type})
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* PHASE 5: Workspace-Aware Task Launching */}
          <div className="w2-section">
            <h2 className="w2-section-title">Launch Workspace Task</h2>
            <div className="w2-card">
              <div className="w2-action-panel-grid">
                <button className="w2-button" onClick={() => launchTask('summarize')}>Summarize</button>
                <button className="w2-button" onClick={() => launchTask('analyze')}>Analyze</button>
                <button className="w2-button" onClick={() => launchTask('search')}>Search</button>
                <button className="w2-button" onClick={() => launchTask('graph')}>Build Graph</button>
                <button className="w2-button" onClick={() => launchTask('docs')}>Generate Docs</button>
                <button className="w2-button" onClick={() => launchTask('review')}>Review Repo</button>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', margin: '8px 0 0 0', textAlign: 'center' }}>
                Tasks automatically receive full context for <strong>{currentFolder}</strong>.
              </p>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

// --- Helpers ---
function displayPath(value) {
  const text = String(value || ".").trim();
  if (!text || text === ".") return "Project Root";
  return text;
}

function EntryIcon({ entry }) {
  if (entry.kind === "file") {
    return entry.previewable ? <FileText size={16} /> : <File size={16} />;
  }
  return <Folder size={16} />;
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
