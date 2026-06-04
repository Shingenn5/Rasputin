import React, { useMemo, useState } from "react";
import {
  Check,
  ChevronRight,
  Database,
  Folder,
  FolderOpen,
  HardDrive,
  Lock,
  RefreshCw,
  Shield,
} from "lucide-react";
import { displayWorkspaceName } from "../../lib/display.js";

export function WorkspacesView({
  view,
  workspace,
  workspaceRoots,
  workspaceBrowse,
  browseWorkspace,
  approvePath,
  selectWorkspace,
  loadWorkspaceRoots,
  previewMount,
  mountPlan,
}) {
  const [filter, setFilter] = useState("");
  const activeName = workspace.activeName || displayWorkspaceName(workspace.activePath);
  const activePath = workspace.absolutePath || workspace.activePath || ".";
  const entries = workspaceBrowse?.entries || [];
  const currentRoot = workspaceBrowse?.root || {};
  const currentFolder = workspaceBrowse?.displayName || displayWorkspaceName(workspaceBrowse?.path);
  const filteredEntries = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return entries;
    return entries.filter((entry) => String(entry.displayName || entry.name || "").toLowerCase().includes(query));
  }, [entries, filter]);

  return (
    <section
      className={`app-view workspaces-view ${view === "workspaces" ? "active" : ""}`}
      id="workspacesView"
      data-app-view="workspaces"
      aria-labelledby="workspacesTitle"
    >
      <header className="workspace-hero">
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

      <div className="workspace-layout">
        <aside className="workspace-side" aria-label="Approved folders">
          <section className="workspace-active-panel">
            <div className="workspace-active-icon" aria-hidden="true">
              <Shield size={22} />
            </div>
            <div>
              <span className="eyebrow">Active workspace</span>
              <h2>{activeName || "No workspace selected"}</h2>
              <p>{displayPath(activePath)}</p>
            </div>
          </section>

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
                const active = rootPath === workspace.activePath || rootId === workspace.activeId;
                const browsing = rootId === currentRoot.id || rootPath === currentRoot.path;
                const info = workspace.workspaces?.find((item) => item.id === rootId || item.root === rootPath) || {};
                const displayName = root.displayName || root.display_name || root.name || displayWorkspaceName(rootPath);
                const absolutePath = root.absolutePath || root.absolute_path || rootPath;
                const readOnly = root.readOnly ?? root.read_only;
                return (
                  <article className={`workspace-root-card ${active ? "is-active" : ""} ${browsing ? "is-browsing" : ""}`} key={rootId} data-testid="workspace-folder-card">
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
                        {info.indexed ? "Indexed" : "Not indexed"}
                      </span>
                      <button type="button" className="tiny-action" onClick={() => selectWorkspace(rootPath || rootId)}>
                        {active ? "Active" : "Use"}
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

        <div className="workspace-main" role="region" aria-label="Folder browser">
          <section className="workspace-browser" data-testid="workspace-browser">
            <div className="browser-head">
              <div>
                <span className="eyebrow">Browsing</span>
                <h2>{currentFolder || "Approved folder"}</h2>
                <div id="workspaceBreadcrumb" className="workspace-breadcrumb" aria-label="Folder breadcrumb">
                  <button type="button" onClick={() => browseWorkspace(currentRoot.id)}>
                    {currentRoot.displayName || currentRoot.name || "Approved folder"}
                  </button>
                  {workspaceBrowse?.path && workspaceBrowse.path !== currentRoot.path && (
                    <>
                      <ChevronRight size={14} aria-hidden="true" />
                      <span>{displayWorkspaceName(workspaceBrowse.path)}</span>
                    </>
                  )}
                </div>
              </div>
              <button
                className="send-text-button"
                type="button"
                onClick={() => approvePath(workspaceBrowse?.path || workspace.activePath || ".")}
              >
                Use current folder
              </button>
            </div>
            <label className="workspace-search">
              <span className="visually-hidden">Filter folders</span>
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="Filter folders"
                aria-label="Filter visible folders"
              />
            </label>

            <div id="workspaceEntries" className="workspace-entry-list" role="list">
              {filteredEntries.map((entry) => (
                <div className="workspace-entry-row" role="listitem" key={`${entry.kind}-${entry.path}`}>
                  <button
                    type="button"
                    className="workspace-entry-name"
                    onClick={() => browseWorkspace(currentRoot.id, entry.path)}
                  >
                    <Folder size={17} />
                    <span>{entry.displayName || entry.name}</span>
                  </button>
                  {entry.kind === "dir" && (
                    <button type="button" className="tiny-action" onClick={() => approvePath(entry.path)}>
                      Use
                    </button>
                  )}
                </div>
              ))}
              {!filteredEntries.length && (
                <div className="empty-panel compact">
                  <h2>{entries.length ? "No matching folders" : "No child folders"}</h2>
                  <p>{entries.length ? "Clear the filter to see every visible folder." : "This folder is selectable, but there are no visible subfolders."}</p>
                </div>
              )}
            </div>
          </section>

          <section className="workspace-section workspace-guide">
            <div className="guide-card">
              <HardDrive size={20} />
              <div>
                <h2>Folder access is explicit</h2>
                <p>Rasputin can only browse mounted and approved folders. Picking a folder here changes the active workspace for new tasks.</p>
              </div>
            </div>
            <div className="guide-card">
              <Database size={20} />
              <div>
                <h2>Indexes stay local</h2>
                <p>RAG and Graphify data are written under local data storage and never require cloud sync.</p>
              </div>
            </div>
          </section>

          <details className="advanced-block workspace-mount-panel">
            <summary>Mount a new host folder</summary>
            <form id="workspaceMountForm" className="mount-form" onSubmit={previewMount}>
              <label>
                <span>Host folder</span>
                <input id="mountHostPath" name="hostPath" placeholder={"C:\\Users\\you\\Project or /home/you/project"} />
              </label>
              <label>
                <span>Display name</span>
                <input name="name" placeholder="Project Documents" />
              </label>
              <label className="switch-line">
                <input type="checkbox" name="readOnly" defaultChecked />
                <span>Read-only mount</span>
              </label>
              <button className="secondary-action" type="submit">
                Preview mount
                <ChevronRight size={15} />
              </button>
            </form>
            <div id="workspaceMountPlan" className="mount-plan" data-testid="workspace-mount-plan" aria-live="polite">
              {mountPlan && (mountPlan.error ? (
                <p className="composer-status">{mountPlan.error}</p>
              ) : (
                <div className="mount-plan-card">
                  <strong>{mountPlan.displayName}</strong>
                  <span>{mountPlan.hostPath}</span>
                  <small>{mountPlan.readOnly ? "Read-only" : "Read/write"} / restart required</small>
                </div>
              ))}
            </div>
          </details>
        </div>
      </div>
    </section>
  );
}

function displayPath(value) {
  const text = String(value || ".").trim();
  if (!text || text === ".") return "Project Root";
  return text;
}

function breadcrumb(root, browse) {
  const rootName = root?.displayName || root?.name || "Approved folder";
  const folder = browse?.path && browse.path !== root?.path ? displayWorkspaceName(browse.path) : "";
  return folder ? `${rootName} / ${folder}` : rootName;
}
