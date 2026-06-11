import React, { useMemo, useState } from "react";
import {
  Activity,
  Brain,
  ChevronLeft,
  FileText,
  Folder,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Satellite,
  Scale,
  Settings,
  Sparkles,
} from "lucide-react";
import { navItems } from "../lib/constants.js";
import { displayWorkspaceName } from "../lib/display.js";

const icons = {
  Home,
  Workspaces: Folder,
  Activity,
  Knowledge: Brain,
  Models: Sparkles,
  Warsat: Satellite,
  Archive: FileText,
  Trials: Scale,
  Settings,
};

export function Sidebar({
  collapsed,
  toggleSidebar,
  view,
  settingsSection,
  go,
  taskCount,
  runningCount,
  workspaceName,
  modelName,
  locked,
  newTask,
  mobileOpen,
  recentSessions = [],
  chatFolders = { folders: [] },
  activeChatFolder = "all",
  setActiveChatFolder,
  activeSessionId,
  resumeSession,
  createChatFolder,
  assignSessionFolder,
}) {
  const stateLabel = locked ? "Privacy locked" : "Review mode";
  const folders = chatFolders?.folders || [];
  const [sessionSearch, setSessionSearch] = useState("");
  const [sessionSort, setSessionSort] = useState("newest");
  const visibleSessions = useMemo(() => {
    const query = sessionSearch.trim().toLowerCase();
    return (recentSessions || [])
      .filter((session) => {
        if (activeChatFolder === "all") return true;
        if (activeChatFolder === "unfiled") return !session.folder;
        return session.folder === activeChatFolder;
      })
      .filter((session) => {
        if (!query) return true;
        const haystack = [
          session.title,
          session.mode,
          session.workspace,
          session.folder || "unfiled",
        ].join(" ").toLowerCase();
        return haystack.includes(query);
      })
      .sort((left, right) => sortSessions(left, right, sessionSort));
  }, [activeChatFolder, recentSessions, sessionSearch, sessionSort]);

  function openNav(item) {
    go(item.view, item.section);
  }

  return (
    <aside
      className={`app-sidebar ${collapsed ? "is-compact" : ""} ${mobileOpen ? "is-mobile-open" : ""}`}
      data-testid={collapsed ? "compact-sidebar" : "expanded-sidebar"}
      aria-label="Rasputin navigation"
    >
      <div className="sidebar-resonance" aria-hidden="true" />

      <div className="sidebar-head">
        <button className="brand-button" type="button" onClick={() => go("home")} aria-label="Go to Home">
          <span className="brand-mark" aria-hidden="true">R</span>
          <span className="sidebar-title">
            <strong>Rasputin</strong>
            <small>Local workbench</small>
          </span>
        </button>
        <button
          className="icon-button sidebar-toggle"
          data-testid="sidebar-toggle"
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={toggleSidebar}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <button className="new-task-btn" data-testid="new-task" type="button" onClick={newTask}>
        <Plus size={18} />
        <span className="nav-label">New Chat</span>
      </button>

      <nav className="sidebar-nav" aria-label="Primary">
        {navItems.map((item) => {
          const Icon = icons[item.label] || Home;
          const active = view === item.view && (item.view === "settings" || !item.section || settingsSection === item.section);
          return (
            <button
              key={`${item.view}-${item.section || item.label}`}
              className={`nav-item ${active ? "is-active" : ""}`}
              data-testid={item.testId}
              type="button"
              aria-current={active ? "page" : undefined}
              aria-label={item.label}
              title={collapsed ? item.label : undefined}
              onClick={() => openNav(item)}
            >
              <Icon size={19} />
              <span className="nav-label">{item.label}</span>
              {item.testId === "nav-activity" && taskCount > 0 && <span className="nav-count">{runningCount || taskCount}</span>}
            </button>
          );
        })}
      </nav>

      <details className="sidebar-section sidebar-recent-section" open={!collapsed}>
        <summary>
          <span className="nav-label">Recent Chats</span>
          {visibleSessions.length > 0 && <span className="sidebar-section-count">{visibleSessions.length}</span>}
        </summary>
        <div className="sidebar-recent-body">
          <div className="sidebar-folder-tools" data-testid="sidebar-library-tools">
            <label className="sidebar-search-field" htmlFor="sidebarSessionSearch">
              <Search size={14} aria-hidden="true" />
              <span className="visually-hidden">Search chats</span>
              <input
                id="sidebarSessionSearch"
                data-testid="sidebar-session-search"
                type="search"
                value={sessionSearch}
                placeholder="Search chats"
                autoComplete="off"
                onChange={(event) => setSessionSearch(event.target.value)}
              />
            </label>
            <div className="sidebar-library-controls">
              <label htmlFor="sidebarFolderFilter">
                <span>Folder</span>
                <select
                  id="sidebarFolderFilter"
                  className="sidebar-folder-filter"
                  data-testid="sidebar-folder-filter"
                  value={activeChatFolder}
                  onChange={(event) => setActiveChatFolder?.(event.target.value)}
                >
                  <option value="all">All chats</option>
                  <option value="unfiled">Unfiled</option>
                  {folders.map((folder) => (
                    <option key={folder.id} value={folder.name}>{folder.name}</option>
                  ))}
                </select>
              </label>
              <label htmlFor="sidebarSessionSort">
                <span>Sort</span>
                <select
                  id="sidebarSessionSort"
                  data-testid="sidebar-session-sort"
                  value={sessionSort}
                  onChange={(event) => setSessionSort(event.target.value)}
                >
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="az">A-Z</option>
                </select>
              </label>
            </div>
            <details className="sidebar-folder-create-shell">
              <summary data-testid="sidebar-folder-create-toggle">
                <Plus size={14} aria-hidden="true" />
                <span>New folder</span>
              </summary>
              <form className="sidebar-folder-create" data-testid="sidebar-folder-create" onSubmit={createChatFolder}>
                <label className="visually-hidden" htmlFor="sidebarFolderName">New chat folder</label>
                <input id="sidebarFolderName" name="name" type="text" placeholder="Folder name" autoComplete="off" />
                <button type="submit" aria-label="Create chat folder">Create</button>
              </form>
            </details>
          </div>
          <div className="sidebar-session-list" data-testid="sidebar-session-list">
            {visibleSessions.map((session) => {
              const active = session.id === activeSessionId;
              return (
                <div
                  key={session.id}
                  className={`sidebar-session-row ${active ? "is-active" : ""}`}
                  data-testid="sidebar-session-row"
                >
                  <button
                    className="sidebar-session"
                    type="button"
                    title={session.title}
                    aria-current={active ? "page" : undefined}
                    onClick={() => resumeSession?.(session.id)}
                  >
                    <span>{session.title || "Untitled chat"}</span>
                    <small>{session.mode || "chat"} / {displayWorkspaceName(session.workspace)}</small>
                  </button>
                  <div className="sidebar-session-actions">
                    <span className="sidebar-session-folder-badge" title={session.folder || "Unfiled"}>
                      {session.folder || "Unfiled"}
                    </span>
                    <label className="visually-hidden" htmlFor={`sessionFolder-${session.id}`}>Move chat to folder</label>
                    <select
                      id={`sessionFolder-${session.id}`}
                      className="sidebar-session-folder"
                      data-testid="sidebar-session-folder"
                      value={session.folder || ""}
                      aria-label={`Move ${session.title || "Untitled chat"} to folder`}
                      onChange={(event) => assignSessionFolder?.(session.id, event.target.value)}
                    >
                      <option value="">Move: Unfiled</option>
                      {folders.map((folder) => (
                        <option key={folder.id} value={folder.name}>Move: {folder.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
              );
            })}
            {!visibleSessions.length && (
              <button className="sidebar-session is-empty" type="button" onClick={newTask}>
                <span>No saved chats yet</span>
                <small>Start with New Chat</small>
              </button>
            )}
          </div>
        </div>
      </details>

      <div className="sidebar-context" aria-label="Current Rasputin state">
        <div className="context-line">
          <span className="status-dot" aria-hidden="true" />
          <span className="nav-label">{stateLabel}</span>
        </div>
        <button className="sidebar-chip" type="button" onClick={() => go("workspaces")}>
          <Folder size={15} />
          <span className="nav-label">{workspaceName}</span>
        </button>
        <button className="sidebar-chip" type="button" onClick={() => go("models")}>
          <Sparkles size={15} />
          <span className="nav-label">{modelName}</span>
        </button>
      </div>

      <button className="mobile-close icon-button" type="button" aria-label="Close sidebar" onClick={toggleSidebar}>
        <ChevronLeft size={18} />
      </button>
    </aside>
  );
}

function sortSessions(left, right, mode) {
  if (mode === "az") {
    return String(left.title || "Untitled chat").localeCompare(String(right.title || "Untitled chat"));
  }
  const leftTime = sessionTime(left);
  const rightTime = sessionTime(right);
  if (mode === "oldest") return leftTime - rightTime;
  return rightTime - leftTime;
}

function sessionTime(session) {
  return Number(session.updatedAt ?? session.updated_at ?? session.createdAt ?? session.created_at ?? 0);
}
