import React from "react";
import {
  Activity,
  Brain,
  ChevronLeft,
  Folder,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Satellite,
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
  activeSessionId,
  resumeSession,
}) {
  const stateLabel = locked ? "Privacy locked" : "Review mode";
  const visibleSessions = (recentSessions || []).slice(0, 6);

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
          const active = view === item.view && (!item.section || settingsSection === item.section);
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
        <div className="sidebar-session-list">
          {visibleSessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <button
                key={session.id}
                className={`sidebar-session ${active ? "is-active" : ""}`}
                type="button"
                title={session.title}
                aria-current={active ? "page" : undefined}
                onClick={() => resumeSession?.(session.id)}
              >
                <span>{session.title || "Untitled chat"}</span>
                <small>{session.mode || "chat"} / {displayWorkspaceName(session.workspace)}</small>
              </button>
            );
          })}
          {!visibleSessions.length && (
            <button className="sidebar-session is-empty" type="button" onClick={newTask}>
              <span>No saved chats yet</span>
              <small>Start with New Chat</small>
            </button>
          )}
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
        <button className="sidebar-chip" type="button" onClick={() => go("settings", "models")}>
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
