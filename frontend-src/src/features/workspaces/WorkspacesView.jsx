import React, { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronRight,
  Clock,
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
  ShieldAlert,
  ShieldCheck,
  ShieldPlus,
  Activity,
  AlertTriangle,
  ArrowLeft,
  X
} from "lucide-react";
import { Modal, Button, Form, Table, Spinner, Badge, Alert, Card } from "react-bootstrap";
import { postJson } from "../../api/client.js";
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
  setWorkspaceTrust,
  loadWorkspaceRoots,
  previewMount,
  requestMount,
  mountPlan,
  pendingMounts,
  removePendingMount,
  approvePendingMount,
  security,
  ragStats,
  graphStats,
  indexWorkspaceKnowledge,
  searchWorkspaceKnowledge,
  refreshKnowledgeStats,
  setPrompt,
  models,
  modeModelOverrides,
  setModeModelOverride
}) {
  const [filter, setFilter] = useState("");
  const [selectedEntry, setSelectedEntry] = useState(null);
  
  // Preview State
  const [previewMode, setPreviewMode] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Knowledge State
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState("");
  const [knowledgeResults, setKnowledgeResults] = useState(null);
  
  // Safe Folder Management State (Streamlined Modal)
  const [showAddModal, setShowAddModal] = useState(false);
  const [mountHostPath, setMountHostPath] = useState("");
  const [mountReadOnly, setMountReadOnly] = useState(true);
  const [mountStatus, setMountStatus] = useState("");
  const [isMounting, setIsMounting] = useState(false);
  const [mountSuccess, setMountSuccess] = useState(false);
  const [copied, setCopied] = useState(false);

  // Host folder picker: click through host folders instead of typing a path.
  const [hostRoots, setHostRoots] = useState([]);
  const [hostRootsMessage, setHostRootsMessage] = useState("");
  const [hostListing, setHostListing] = useState(null); // {path, parent, entries}
  const [hostBrowseLoading, setHostBrowseLoading] = useState(false);
  const [hostBrowseError, setHostBrowseError] = useState("");
  const [hostPathDraft, setHostPathDraft] = useState("");

  // Pending Mounts panel: which entry's compose line was just copied.
  const [copiedPendingPath, setCopiedPendingPath] = useState("");
  const pendingMountsList = pendingMounts || [];

  // Phase 10: Button Reliability Framework State
  const [uiState, setUiState] = useState({ status: 'idle', message: '' });
  const executeAction = useReliableAction("WorkspacesView");

  // Trusted Dev Mode State
  const [showTrustModal, setShowTrustModal] = useState(false);
  const [trustBusy, setTrustBusy] = useState(false);

  const activeName = workspace.activeName || displayWorkspaceName(workspace.activePath);
  const activePath = workspace.absolutePath || workspace.activePath || ".";
  const activeId = workspace.activeId || workspace.active_id;
  const activeWorkspaceInfo = workspace.workspaces?.find((item) => item.id === activeId || item.root === workspace.activePath) || {};
  const activeReadOnly = activeWorkspaceInfo.readOnly ?? activeWorkspaceInfo.read_only;
  const activeIndexed = activeWorkspaceInfo.indexed;
  const activeTrusted = Boolean(activeWorkspaceInfo.trusted);
  // Native mode has no container: folders are registered directly, so the
  // mount/compose/restart affordances and the docker-control grant don't apply.
  const native = Boolean(security?.native);
  
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
    setPreviewMode(false);
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

  // Approve a folder that is already visible under an approved root as its
  // own workspace. Unlike mounting, this needs no Docker restart, and the new
  // workspace gets its own access mode and Trusted Dev Mode toggle.
  async function approveSubfolder(path) {
    if (!approvePath || !path) return;
    try {
      await executeAction("ApproveSubfolder", path, async () => {
        await approvePath(path);
        await loadWorkspaceRoots();
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

  // --- Guided Mount Workflow (Streamlined Modal) ---
  const resetMountModal = () => {
    setShowAddModal(false);
    setMountHostPath("");
    setMountReadOnly(true);
    setMountStatus("");
    setMountSuccess(false);
    setIsMounting(false);
    setCopied(false);
    setHostListing(null);
    setHostBrowseError("");
    setHostBrowseLoading(false);
    setHostPathDraft("");
  };

  // Load host starting points (project folder, home, drive) when the picker opens.
  useEffect(() => {
    if (!showAddModal || (!native && !security?.allowDockerControl)) return;
    postJson("/api/workspace/host-browse", {})
      .then((data) => {
        setHostRoots(data.roots || []);
        setHostRootsMessage(data.message || "");
      })
      .catch((error) => setHostRootsMessage(error.message));
  }, [showAddModal, security?.allowDockerControl]);

  async function browseHost(path) {
    const target = String(path || "").trim();
    if (!target || hostBrowseLoading) return;
    setHostBrowseLoading(true);
    setHostBrowseError("");
    try {
      const listing = await postJson("/api/workspace/host-browse", { path: target });
      setHostListing(listing);
      setMountHostPath(listing.path);
      setHostPathDraft(listing.path);
    } catch (error) {
      setHostBrowseError(error.message);
    } finally {
      setHostBrowseLoading(false);
    }
  }

  async function handleAddFolderSubmit(e) {
    e.preventDefault();
    if (!mountHostPath) {
      setMountStatus("Host path is required.");
      return;
    }

    setIsMounting(true);
    setMountStatus("");

    try {
      await executeAction("MountFolder", mountHostPath, async () => {
        const formData = new FormData();
        formData.append("hostPath", mountHostPath);
        formData.append("name", displayWorkspaceName(mountHostPath));
        if (mountReadOnly) formData.append("readOnly", "on");

        // Linear chain: plan, then save the request exactly once. (This used
        // to hand off to a useEffect keyed on the parent's mountPlan state;
        // requestMount's own setMountPlan(...) call retriggered that same
        // effect, so every submit re-saved the same mount request in a tight
        // loop until the modal closed.)
        const plan = await previewMount({ preventDefault: () => {}, currentTarget: formData });
        if (plan?.error) throw new Error(plan.error);
        await requestMount(plan);
        await loadWorkspaceRoots();
      }, setUiState);

      setMountSuccess(true);
    } catch (error) {
      setMountStatus(error.message);
    } finally {
      setIsMounting(false);
    }
  }

  // --- Trusted Dev Mode ---
  function handleTrustToggleClick() {
    if (!activeId) return;
    if (activeTrusted) {
      revokeTrust();
    } else {
      setShowTrustModal(true);
    }
  }

  async function confirmEnableTrust() {
    if (!setWorkspaceTrust || !activeId) return;
    setTrustBusy(true);
    try {
      await setWorkspaceTrust(activeId, true);
      setShowTrustModal(false);
    } finally {
      setTrustBusy(false);
    }
  }

  async function revokeTrust() {
    if (!setWorkspaceTrust || !activeId) return;
    setTrustBusy(true);
    try {
      await setWorkspaceTrust(activeId, false);
    } finally {
      setTrustBusy(false);
    }
  }

  async function copyMountVolume() {
    if (!mountPlan?.composeVolume) return;
    try {
      await navigator.clipboard.writeText(mountPlan.composeVolume);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setMountStatus("Copy failed. Select and copy the volume line manually.");
    }
  }

  // --- Pending Mounts panel ---
  async function copyPendingVolume(item) {
    if (!item?.composeVolume) return;
    try {
      await navigator.clipboard.writeText(item.composeVolume);
      setCopiedPendingPath(item.hostPath);
      setTimeout(() => setCopiedPendingPath(""), 2000);
    } catch (error) {
      console.error("Clipboard copy failed", error);
    }
  }

  function handleApprovePendingMount(item) {
    return executeAction("ApprovePendingMount", item.hostPath, async () => {
      await approvePendingMount?.(item);
      await loadWorkspaceRoots?.();
    }, setUiState);
  }

  function handleRemovePendingMount(item) {
    return executeAction("RemovePendingMount", item.hostPath, async () => {
      await removePendingMount?.(item.hostPath);
    }, setUiState);
  }

  // Clicking an approved folder both switches to it (updates the header,
  // the highlight, and what "Index Workspace" / task launches target) and
  // loads its file listing into the explorer below. selectWorkspace already
  // re-browses the newly active root as part of loadWorkspaceRoots, so a
  // second, separate browseWorkspace() call here was pure duplicate work on
  // every click -- doubling the round trips (and doubling the folder-listing
  // cost when the root has a lot of entries) for no visible difference.
  function selectAndBrowseRoot(root) {
    const rootId = root.id;
    const rootPath = root.path || root.root;
    selectWorkspace?.(rootId || rootPath);
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
          <button
            type="button"
            className="w2-header-stat"
            style={{
              cursor: activeId ? "pointer" : "default",
              border: activeTrusted ? "1px solid var(--ras-warn, #d97706)" : "1px solid transparent",
              background: "transparent",
            }}
            onClick={handleTrustToggleClick}
            disabled={!activeId || trustBusy}
            aria-pressed={activeTrusted}
            aria-label={activeTrusted ? "Trusted Dev Mode is on for this workspace. Click to revoke." : "Trusted Dev Mode is off for this workspace. Click to enable."}
            title={activeTrusted ? "Shell, file writes, and git run without per-action approval here. Click to revoke." : "Enable to let the agent run shell, write files, and use git here without per-action approval."}
          >
            <strong style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              {activeTrusted ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
              {activeTrusted ? "On" : "Off"}
            </strong>
            <small>Trusted Dev Mode</small>
          </button>
        </div>
      </div>

      <div className="w2-main-grid">
        
        {/* Left Column: Explorer Sidebar */}
        <div className="w2-column w2-column-nav">
          
          <div className="w2-section" style={{ gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="w2-section-title">Approved Folders</h2>
              <button className="icon-button" type="button" onClick={loadWorkspaceRoots} aria-label="Refresh roots">
                <RefreshCw size={14} />
              </button>
            </div>
            {/* Bounded scroll so a long roots list can't grow the whole page. */}
            <div style={{ display: 'flex', flexDirection: 'column', maxHeight: '40vh', overflowY: 'auto' }}>
              {workspaceRoots.map((root) => {
                const rootPath = root.path || root.root;
                const rootId = root.id;
                const displayName = root.displayName || root.display_name || root.name || displayWorkspaceName(rootPath);
                const active = rootId === activeId || normalizePath(rootPath) === normalizePath(workspace.activePath);
                return (
                  <div key={rootId} className={`w2-tree-item ${active ? 'is-active' : ''}`} onClick={() => selectAndBrowseRoot(root)} style={{ fontWeight: active ? 600 : 400 }}>
                    <FolderOpen size={16} className="w2-tree-icon" />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayName}</span>
                    {root.trusted && (
                      <ShieldAlert size={13} aria-label="Trusted Dev Mode is on for this folder" title="Trusted Dev Mode is on for this folder" style={{ marginLeft: 'auto', flexShrink: 0, color: 'var(--ras-warn, #d97706)' }} />
                    )}
                  </div>
                );
              })}
              {workspaceRoots.length === 0 && <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', padding: '4px 8px' }}>No approved folders.</div>}
              <div 
                className="w2-tree-item" 
                style={{ color: 'var(--cc-primary)', marginTop: '4px' }}
                onClick={() => setShowAddModal(true)}
              >
                <PlusCircle size={16} className="w2-tree-icon" style={{ color: 'var(--cc-primary)' }} />
                <span>Add Folder</span>
              </div>
            </div>
          </div>

          {pendingMountsList.length > 0 && (
            <>
              <hr style={{ borderColor: 'var(--cc-border)', margin: '4px 0' }} />
              <div className="w2-section" style={{ gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2 className="w2-section-title">Pending Mounts</h2>
                  <Badge bg="secondary" pill>{pendingMountsList.length}</Badge>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '30vh', overflowY: 'auto' }}>
                  {pendingMountsList.map((item) => (
                    <div key={item.hostPath} className="pending-mount-item">
                      <div className="pending-mount-head">
                        <Folder size={14} className="w2-tree-icon" style={{ flexShrink: 0 }} />
                        <span className="pending-mount-name" title={item.hostPath}>
                          {item.displayName || displayWorkspaceName(item.hostPath)}
                        </span>
                        {item.readOnly ? (
                          <Lock size={12} title="Read only" style={{ flexShrink: 0, color: 'var(--cc-muted)' }} />
                        ) : (
                          <Eye size={12} title="Read / write" style={{ flexShrink: 0, color: 'var(--ras-warn, #d97706)' }} />
                        )}
                      </div>
                      <div className="pending-mount-status">
                        {item.ready ? (
                          <span className="pending-mount-badge is-ready"><Check size={11} /> Ready to approve</span>
                        ) : (
                          <span className="pending-mount-badge is-waiting"><Clock size={11} /> Restart needed</span>
                        )}
                      </div>
                      <div className="pending-mount-actions">
                        {item.ready && (
                          <button
                            type="button"
                            className="tiny-action"
                            title="Approve this folder as a workspace now"
                            onClick={() => handleApprovePendingMount(item)}
                          >
                            <ShieldPlus size={13} /> Approve
                          </button>
                        )}
                        <button
                          type="button"
                          className="tiny-action"
                          title="Copy the Docker Compose volume line"
                          onClick={() => copyPendingVolume(item)}
                        >
                          {copiedPendingPath === item.hostPath ? <Check size={13} /> : <Copy size={13} />}
                        </button>
                        <button
                          type="button"
                          className="tiny-action danger"
                          title="Remove this pending mount request"
                          onClick={() => handleRemovePendingMount(item)}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          <hr style={{ borderColor: 'var(--cc-border)', margin: '4px 0' }} />

          <div className="w2-section" style={{ flex: 1, gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="w2-section-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>EXPLORER: {currentFolder}</h2>
              {workspaceBrowse?.path && normalizePath(workspaceBrowse.path) !== normalizePath(currentRoot?.path) && (
                <button
                  className="icon-button"
                  type="button"
                  title="Approve this folder as its own workspace (separate access mode and trust)"
                  aria-label="Approve current folder as its own workspace"
                  onClick={() => approveSubfolder(workspaceBrowse.path)}
                >
                  <ShieldPlus size={14} />
                </button>
              )}
            </div>
            
            <div className="w2-breadcrumbs" style={{ fontSize: '0.75rem', padding: '0 8px' }}>
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={crumb.path || "root"}>
                  {index > 0 && <ChevronRight size={12} />}
                  <button type="button" onClick={() => browseWorkspace(currentRoot.id, crumb.path)} style={{ color: 'var(--cc-muted)' }}>
                    {crumb.label}
                  </button>
                </React.Fragment>
              ))}
            </div>
            
            <div style={{ padding: '0 8px' }}>
              <input 
                className="w2-input" 
                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                placeholder="Search..." 
                value={filter} 
                onChange={e => setFilter(e.target.value)} 
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflowY: 'auto', marginTop: '4px' }}>
              {filteredEntries.map((entry) => (
                <div 
                  key={`${entry.kind}-${entry.path}`} 
                  className={`w2-tree-item ${selectedEntry?.path === entry.path ? 'is-active' : ''}`}
                  onClick={() => openEntry(entry)}
                  title={`${entry.kind === "folder" ? "Folder" : entry.extension || "File"}\nSize: ${entry.kind === "folder" ? "--" : formatBytes(entry.sizeBytes)}\nModified: ${formatTime(entry.modifiedAt)}`}
                >
                  <EntryIcon entry={entry} className="w2-tree-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {entry.displayName || entry.name}
                  </span>
                  {entry.kind === "folder" && (
                    <button
                      type="button"
                      className="tree-approve-btn"
                      title="Approve as its own workspace (separate access mode and trust)"
                      aria-label={`Approve ${entry.displayName || entry.name} as its own workspace`}
                      onClick={(event) => {
                        event.stopPropagation();
                        approveSubfolder(entry.path);
                      }}
                    >
                      <ShieldPlus size={14} />
                    </button>
                  )}
                </div>
              ))}
              {filteredEntries.length === 0 && (
                <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', padding: '8px', textAlign: 'center' }}>
                  {entries.length ? "No matching items." : "Folder is empty."}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Editor / Dashboard */}
        <div className="w2-column w2-column-explorer" style={{ display: 'flex', flexDirection: 'column' }}>
          {previewMode ? (
            // Full-Pane Preview Mode
            <div className="w2-section" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h2 className="w2-section-title mb-0 d-flex align-items-center" style={{ textTransform: 'none', color: 'var(--cc-text)', fontSize: '1rem' }}>
                  <FileText className="me-2 text-primary" size={20} />
                  {selectedEntry?.name}
                </h2>
                <Button variant="outline-secondary" size="sm" onClick={closePreview} className="d-flex align-items-center">
                  <ArrowLeft size={16} className="me-2"/> Close Preview
                </Button>
              </div>
              
              <div className="w2-card mb-2" style={{ flexShrink: 0, padding: '8px 12px' }}>
                <div style={{ fontSize: '0.75rem', display: 'flex', gap: '24px' }}>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Path</strong><span>{selectedEntry?.path}</span></div>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Size</strong><span>{formatBytes(selectedEntry?.sizeBytes)}</span></div>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Modified</strong><span>{formatTime(selectedEntry?.modifiedAt)}</span></div>
                </div>
              </div>
              
              <div className="w2-card" style={{ flex: 1, overflowY: 'auto', padding: 0, display: 'flex', flexDirection: 'column' }}>
                {previewLoading ? (
                  <div className="d-flex justify-content-center align-items-center h-100 p-5">
                    <Spinner animation="border" variant="primary" />
                  </div>
                ) : previewError ? (
                  <div className="p-4 text-danger">{previewError}</div>
                ) : (
                  <div className="w2-preview-block" style={{ flex: 1, border: 'none', margin: 0, borderRadius: 0 }}>
                    {preview?.content}
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Empty State / Dashboard Mode. Everything must fit on one screen
            // with no scrolling: no redundant title block (the page header
            // card above already names the workspace), health as one slim
            // strip, and `margin: auto 0` centers the block when there is
            // spare height but degrades to top-aligned scroll on tiny windows.
            <div className="w2-section" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', overflowY: 'auto' }}>

              <div style={{ maxWidth: '860px', width: '100%', display: 'flex', flexDirection: 'column', gap: '12px', margin: 'auto 0' }}>

                <div className="w2-card" style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between', padding: '10px 16px', gap: '10px 16px' }}>
                  <div className="w2-health-item is-good"><Check size={16}/> Folder Access</div>
                  <div className={`w2-health-item ${activeIndexed ? 'is-good' : 'is-warn'}`}>
                    {activeIndexed ? <Check size={16}/> : <AlertTriangle size={16}/>} RAG Index
                  </div>
                  <div className={`w2-health-item ${graphStats?.nodes > 0 ? 'is-good' : 'is-warn'}`}>
                    {graphStats?.nodes > 0 ? <Check size={16}/> : <AlertTriangle size={16}/>} Graph DB
                  </div>
                  <div className="w2-health-item is-good"><Check size={16}/> Security</div>
                  <span style={{ color: 'var(--cc-muted)', fontSize: '0.75rem' }}>Select a file from the explorer to preview it.</span>
                </div>

                <div className="w2-section" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  
                  <div className="w2-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h2 className="w2-section-title">Knowledge Operations</h2>
                    
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
                    
                    <div className="w2-action-panel-grid">
                      <button className="w2-button primary" onClick={indexCurrentFolder}>Index Workspace</button>
                      <button className="w2-button" onClick={refreshKnowledgeStats}>Refresh Status</button>
                    </div>

                    {knowledgeStatus && <p style={{ fontSize: '0.75rem', margin: '4px 0 0 0', color: 'var(--cc-muted)' }}>{knowledgeStatus}</p>}

                    <form onSubmit={searchKnowledge} style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <input className="w2-input" value={knowledgeQuery} onChange={e => setKnowledgeQuery(e.target.value)} placeholder="Search index & graph..." />
                      <button className="w2-button" type="submit">Search</button>
                    </form>

                    {knowledgeResults && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px', maxHeight: '150px', overflowY: 'auto' }}>
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

                  <div className="w2-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h2 className="w2-section-title">Launch Workspace Task</h2>
                    <div className="w2-action-panel-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                      <button className="w2-button" onClick={() => launchTask('summarize')}>Summarize Directory</button>
                      <button className="w2-button" onClick={() => launchTask('analyze')}>Analyze Workspace</button>
                      <button className="w2-button" onClick={() => launchTask('search')}>Search Vulnerabilities</button>
                      <button className="w2-button" onClick={() => launchTask('graph')}>Review Dependencies</button>
                      <button className="w2-button" onClick={() => launchTask('docs')}>Generate Documentation</button>
                      <button className="w2-button" onClick={() => launchTask('review')}>Code Review</button>
                    </div>
                  </div>

                  <div className="w2-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px', gridColumn: '1 / -1' }}>
                    <h2 className="w2-section-title">Agent Capability Routing</h2>
                    <p style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', margin: 0 }}>
                      Assign specific tasks in this workspace to specific local models.
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '12px' }}>
                      {[
                        { mode: 'review', label: 'Code Reviewer' },
                        { mode: 'research', label: 'Researcher' },
                        { mode: 'write', label: 'Summarizer' },
                        { mode: 'analyze', label: 'Analyzer' }
                      ].map((item) => (
                        <div key={item.mode} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <strong style={{ fontSize: '0.75rem', color: 'var(--cc-muted)' }}>{item.label}</strong>
                          <select
                            className="w2-input"
                            style={{ fontSize: '0.875rem' }}
                            value={modeModelOverrides?.[item.mode] || ""}
                            onChange={(e) => setModeModelOverride(item.mode, e.target.value)}
                          >
                            <option value="">(Default Routing)</option>
                            {(models || []).map((m) => (
                              <option key={m.key} value={m.key}>
                                {m.name || m.key}
                              </option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>

              </div>
            </div>
          )}
        </div>
      </div>

      {/* Streamlined Add Folder Modal */}
      <Modal show={showAddModal} onHide={resetMountModal} centered size="lg">
        <Modal.Header closeButton>
          <Modal.Title className="d-flex align-items-center">
            <FolderOpen className="me-2 text-primary" size={24} />
            Approve Local Folder
          </Modal.Title>
        </Modal.Header>
        <Modal.Body className="px-4 py-4">
          {!mountSuccess ? (
            <Form onSubmit={handleAddFolderSubmit}>
              <p className="text-muted mb-4">
                {native
                  ? "Choose a folder on your machine to give Rasputin access to. It is registered directly -- no mount or restart needed."
                  : "Grant Rasputin access to a local directory. Since Rasputin runs in a Docker container, it cannot access your files unless you explicitly approve and mount them here."}
              </p>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-semibold">Pick a folder</Form.Label>
                {(native || security?.allowDockerControl) && hostRoots.length > 0 && (
                  <div className="d-flex flex-wrap gap-2 mb-2">
                    {hostRoots.map((root) => (
                      <Button
                        key={root.path}
                        type="button"
                        size="sm"
                        variant={hostListing?.path === root.path ? "primary" : "outline-secondary"}
                        disabled={hostBrowseLoading}
                        onClick={() => browseHost(root.path)}
                      >
                        <HardDrive size={14} className="me-1" /> {root.name}
                      </Button>
                    ))}
                  </div>
                )}
                <div className="d-flex gap-2 mb-2">
                  <Button
                    type="button"
                    variant="outline-secondary"
                    disabled={!hostListing?.parent || hostBrowseLoading}
                    onClick={() => browseHost(hostListing?.parent)}
                    title="Up one level"
                    aria-label="Up one level"
                  >
                    <ArrowLeft size={15} />
                  </Button>
                  <Form.Control
                    type="text"
                    value={hostPathDraft}
                    onChange={(e) => {
                      setHostPathDraft(e.target.value);
                      setMountHostPath(e.target.value);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        browseHost(hostPathDraft);
                      }
                    }}
                    placeholder="Click a starting point above, or type a path and press Enter"
                    autoFocus
                  />
                  <Button
                    type="button"
                    variant="outline-primary"
                    disabled={hostBrowseLoading || !hostPathDraft.trim()}
                    onClick={() => browseHost(hostPathDraft)}
                  >
                    Go
                  </Button>
                </div>
                <div className="border rounded" style={{ maxHeight: 240, overflowY: "auto" }} data-testid="host-folder-list">
                  {hostBrowseLoading && (
                    <div className="d-flex align-items-center gap-2 p-3 text-muted">
                      <Spinner size="sm" /> <span>Listing folders...</span>
                    </div>
                  )}
                  {!hostBrowseLoading && !hostListing && (
                    <div className="p-3 text-muted small">
                      {hostRootsMessage || "Choose a starting point above, then click folders to drill in. The folder you are viewing is the one that gets approved."}
                    </div>
                  )}
                  {!hostBrowseLoading && hostListing && hostListing.entries.length === 0 && (
                    <div className="p-3 text-muted small">No subfolders here. Approve this folder below.</div>
                  )}
                  {!hostBrowseLoading && hostListing && hostListing.entries.map((entry) => (
                    <button
                      type="button"
                      key={entry.path}
                      className="host-folder-row d-flex align-items-center gap-2 w-100 text-start border-0 bg-transparent px-3 py-2"
                      data-testid="host-folder-row"
                      onClick={() => browseHost(entry.path)}
                    >
                      <Folder size={15} className="text-primary flex-shrink-0" />
                      <span className="text-truncate">{entry.name}</span>
                      <ChevronRight size={14} className="ms-auto text-muted flex-shrink-0" />
                    </button>
                  ))}
                </div>
                {hostBrowseError && <Alert variant="danger" className="mt-2 mb-0 py-2">{hostBrowseError}</Alert>}
                {mountHostPath && (
                  <div className="mt-2 small">
                    <span className="text-muted">Folder to approve: </span>
                    <strong className="font-monospace text-break" data-testid="host-selected-path">{mountHostPath}</strong>
                  </div>
                )}
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label className="fw-semibold">Access Permissions</Form.Label>
                <Card className="border-0 bg-body-tertiary">
                  <Card.Body className="p-3">
                    <Form.Check 
                      type="radio" 
                      id="radio-readonly"
                      name="accessMode"
                      label={<><span className="fw-medium">Read Only (Recommended)</span><p className="text-muted small mb-0 mt-1">Agents can read files to answer questions and analyze code, but cannot edit files.</p></>}
                      checked={mountReadOnly}
                      onChange={() => setMountReadOnly(true)}
                      className="mb-3"
                    />
                    <Form.Check 
                      type="radio" 
                      id="radio-readwrite"
                      name="accessMode"
                      label={<><span className="fw-medium">Read / Write</span><p className="text-muted small mb-0 mt-1">Agents can write new files and modify existing code autonomously.</p></>}
                      checked={!mountReadOnly}
                      onChange={() => setMountReadOnly(false)}
                    />
                  </Card.Body>
                </Card>
              </Form.Group>

              {mountStatus && <Alert variant="danger">{mountStatus}</Alert>}

              {!native && !security?.allowDockerControl && (
                <div className="alert alert-warning d-flex align-items-center mb-0">
                  <Lock size={16} className="me-2" /> Docker control is disabled in Safety Settings. You cannot auto-mount folders.
                </div>
              )}

              <div className="d-flex justify-content-end mt-4 pt-3 border-top">
                <Button variant="light" className="me-2" onClick={resetMountModal}>Cancel</Button>
                <Button type="submit" variant="primary" disabled={isMounting || !mountHostPath || (!native && !security?.allowDockerControl)}>
                  {isMounting ? <Spinner size="sm" /> : (native ? "Approve Folder" : "Approve & Generate Mount")}
                </Button>
              </div>
            </Form>
          ) : (
            <div className="text-center py-4">
              <div className="mb-4 d-inline-flex justify-content-center align-items-center rounded-circle bg-success bg-opacity-10" style={{ width: '80px', height: '80px' }}>
                <Check size={40} className="text-success" />
              </div>
              <h4 className="fw-bold mb-3">Folder Approved Successfully!</h4>
              {native ? (
                <p className="text-muted mb-4 px-4">
                  The folder is registered and ready to use right now — no mount or restart needed.
                  You can approve any subfolder as its own workspace from the explorer (hover a
                  folder and click the shield).
                </p>
              ) : (
                <>
                  <p className="text-muted mb-4 px-4">
                    The folder has been added to your approved list. <br/>
                    <strong>Important:</strong> Because Rasputin is dockerized, you must restart the container with the newly generated volume mapping for the files to be accessible.
                  </p>

                  <div className="bg-body-tertiary p-3 rounded mb-4 text-start font-monospace small position-relative border">
                    <div className="text-muted mb-2 fw-bold font-sans">Docker Compose Volume Line:</div>
                    <div className="user-select-all text-break">{mountPlan?.composeVolume}</div>
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      className="position-absolute top-0 end-0 m-2"
                      onClick={copyMountVolume}
                    >
                      {copied ? <Check size={14}/> : <Copy size={14}/>}
                    </Button>
                  </div>

                  <p className="text-muted small px-4">
                    Tip: after the restart you can approve any subfolder of this mount as its own
                    workspace straight from the explorer — hover a folder and click the shield.
                    No extra mounts or restarts needed.
                  </p>
                </>
              )}

              <Button variant="primary" size="lg" onClick={resetMountModal} className="px-5">
                Done
              </Button>
            </div>
          )}
        </Modal.Body>
      </Modal>

      {/* Trusted Dev Mode confirm modal */}
      <Modal show={showTrustModal} onHide={() => setShowTrustModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title className="d-flex align-items-center">
            <ShieldAlert className="me-2 text-warning" size={22} />
            Enable Trusted Dev Mode
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            This grants Rasputin unattended shell execution, file writes, and local git
            operations inside <strong>{activeName || "this workspace"}</strong> — no approval
            click per action, the same way you'd use your own terminal in this folder.
          </p>
          <ul className="text-muted small" style={{ listStyle: "disc", paddingLeft: "1.25rem" }}>
            <li>Every action is still fully logged in the audit trail.</li>
            <li>Actions that leave this machine (like <code>git push</code>) still require approval.</li>
            <li>Privacy Lock and remote model routing are unaffected.</li>
            <li>You can revoke this in one click at any time.</li>
          </ul>
          <div className="d-flex justify-content-end gap-2 mt-4 pt-3 border-top">
            <Button variant="light" onClick={() => setShowTrustModal(false)} disabled={trustBusy}>Cancel</Button>
            <Button variant="warning" onClick={confirmEnableTrust} disabled={trustBusy}>
              {trustBusy ? <Spinner size="sm" /> : "Enable Trusted Dev Mode"}
            </Button>
          </div>
        </Modal.Body>
      </Modal>

    </section>
  );
}

// --- Helpers ---
function displayPath(value) {
  const text = String(value || ".").trim();
  if (!text || text === ".") return "Project Root";
  return text;
}

function EntryIcon({ entry, className }) {
  if (entry.kind === "file") {
    return entry.previewable ? <FileText size={16} className={className} /> : <File size={16} className={className} />;
  }
  return <Folder size={16} className={className} />;
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
  if (!stamp) return "--";
  return new Date(stamp * 1000).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}
