import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  BrainCircuit,
  Box,
  Clock,
  Folder,
  FolderOpen,
  Laptop,
  LockKeyhole,
  LogOut,
  MessageSquare,
  PanelLeft,
  Plus,
  Search,
  Settings,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils.js";
import { canAccessView, canRunTasks, normalizedRole, roleLabel } from "@/lib/access.js";

/* Keep the daily-driver shell intentionally small. Advanced areas remain
 * reachable through the command palette and their existing routes, while
 * these five destinations describe the normal desktop workflow. */
const NAV_GROUPS = [
  {
    label: "Work",
    items: [
      { view: "chat", label: "Chat", ariaLabel: "Chat workstation", icon: MessageSquare, testId: "nav-chat" },

      { view: "discover", label: "Discover Models", icon: Search, testId: "nav-discover" },
      { view: "models", label: "Models", icon: Box, testId: "nav-models" },
    ],
  },
];

export function DashSidebar({
  collapsed,
  toggleSidebar,
  view,
  settingsSection,
  go,
  taskCount = 0,
  runningCount = 0,
  newTask,
  locked,
  runtimeMode = "docker",
  desktopOnly = false,
  motionMode = "full",
  mobileOpen = false,
  mobileTriggerRef,
  recentSessions = [],
  emptySessionCount = 0,
  deleteSession,
  cleanupEmptySessions,
  resumeSession,
  activeSessionId,
  session,
  logout,
  workspaceRoots = [],
  activeWorkspacePath = "",
  activeWorkspaceId = "",
  onSelectProject,
  graphifyProject,
}) {
  const role = normalizedRole(session?.role);
  const taskAccess = canRunTasks(role);
  const visibleNavGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => canAccessView(role, item.view) && (!desktopOnly || item.view !== "warsat")),
  })).filter((group) => group.items.length > 0);
  const asideRef = useRef(null);
  const historyTriggerRef = useRef(null);
  const historySearchRef = useRef(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyQuery, setHistoryQuery] = useState("");
  const wasMobileOpenRef = useRef(mobileOpen);
  const reducedMotion = motionMode === "reduced";
  // Collapsed mode is a deliberate, persistent rail. It never relies on hover
  // for access; the brand control is always keyboard-reachable and reopens it.
  // Mobile always opens as a labelled drawer. Desktop follows the persisted
  // collapsed preference so the toggle changes both content and reserved space.
  const expanded = mobileOpen || !collapsed;

  useEffect(() => {
    const wasMobileOpen = wasMobileOpenRef.current;
    wasMobileOpenRef.current = mobileOpen;

    if (mobileOpen) {
      const firstAction = asideRef.current?.querySelector('[data-testid="new-task"]');
      firstAction?.focus();
    } else if (wasMobileOpen) {
      mobileTriggerRef?.current?.focus();
    }
  }, [mobileOpen, mobileTriggerRef]);

  useEffect(() => {
    if (!historyOpen) return undefined;
    historySearchRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setHistoryOpen(false);
        setHistoryQuery("");
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [historyOpen]);

  useEffect(() => {
    if (!historyOpen) historyTriggerRef.current?.focus();
  }, [historyOpen]);

  const isActive = (item) =>
    view === item.view && (item.view !== "settings" || settingsSection === item.section);
  const sessions = (recentSessions || []).slice(0, 12);
  const normalizedHistoryQuery = historyQuery.trim().toLowerCase();
  const filteredSessions = normalizedHistoryQuery
    ? sessions.filter((item) => ((item.title || "") + " " + (item.model || "") + " " + (item.workspacePath || "")).toLowerCase().includes(normalizedHistoryQuery))
    : sessions;
  const projects = (workspaceRoots || []).slice(0, 8);
  const nativeRuntime = desktopOnly || runtimeMode === "native";
  const RuntimeIcon = nativeRuntime ? Laptop : Box;

  const navBtn = (item) => {
    const Icon = item.icon;
    const active = isActive(item);
    return (
      <button
        key={item.view}
        type="button"
        data-testid={item.testId}
        aria-current={active ? "page" : undefined}
        aria-label={item.ariaLabel || item.label}
        title={!expanded ? item.label : undefined}
        onClick={() => go(item.view, item.section)}
        className={cn(
          "ras-nav-item group relative flex w-full items-center gap-3 rounded-lg px-3 py-1 text-[0.82rem] font-medium transition-colors",
          active ? "is-active text-sidebar-foreground" : "text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground",
          !expanded && "justify-center px-0",
        )}
      >
        {active && (
          <motion.span
            layoutId="nav-active"
            transition={reducedMotion ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
            className="ras-nav-active absolute inset-0 -z-10 rounded-lg"
          />
        )}
        <Icon size={18} className={cn("shrink-0", active && "text-sidebar-primary")} />
        {expanded && <span className="flex-1 truncate text-left">{item.label}</span>}
      </button>
    );
  };

  return (
    <div
      className={cn(
        "relative h-dvh shrink-0 w-0 transition-[width] duration-200 ease-out",
        collapsed ? "sm:w-[54px]" : "sm:w-[220px]",
      )}
    >
      {/* Mobile scrim — covers content behind the open sidebar overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 sm:hidden"
          onClick={toggleSidebar}
          aria-hidden="true"
        />
      )}
      <aside
        id="rasputin-sidebar"
        ref={asideRef}
        aria-label="Primary navigation"
        onKeyDown={(event) => {
          if (event.key === "Escape" && mobileOpen) {
            event.preventDefault();
            toggleSidebar();
          }
        }}
        className={cn(
          "ras-sidebar ras-desktop-rail ras-sidebar-scroll absolute inset-y-0 left-0 z-30 flex flex-col overflow-x-hidden overflow-y-auto border-r border-sidebar-border bg-sidebar px-2 py-3 text-sidebar-foreground transition-[width,transform] duration-200 ease-out",
          expanded ? "w-[220px]" : "w-[54px]",
          // Mobile-only CSS hides closed controls from tab/AT order; desktop remains persistent.
          !mobileOpen && "is-mobile-closed -translate-x-full sm:translate-x-0",
          mobileOpen ? "shadow-2xl shadow-black/50" : "",
        )}
      >
        {/* Brand */}
        <div className={cn("ras-sidebar-brand flex shrink-0 items-center gap-2.5 px-2 pb-3", !expanded && "justify-center px-0")}>
          <button
            type="button"
            data-testid="sidebar-toggle"
            onClick={toggleSidebar}
            aria-label={mobileOpen ? "Close navigation" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={mobileOpen ? "Close navigation" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="ras-brand-sigil shrink-0"
          >
            <img src="/static/rasputin-logo.png" alt="" className="ras-brand-logo" />
            <PanelLeft size={11} className="ras-brand-toggle-icon" aria-hidden="true" />
          </button>
          {expanded && (
            <div className="flex flex-col leading-tight">
              <span className="ras-sidebar-wordmark text-[1rem] font-bold tracking-tight">Rasputin</span>
              <span className="text-[0.63rem] uppercase tracking-[0.12em] text-sidebar-foreground/45">Local AI</span>
            </div>
          )}
        </div>

        {/* New chat */}
        {taskAccess ? <button
          type="button"
          data-testid="new-task"
          onClick={newTask}
          title={!expanded ? "New chat" : undefined}
          aria-label="New Chat"
          className={cn(
            "ras-new-chat mb-1 flex shrink-0 items-center gap-2.5 rounded-lg bg-sidebar-primary px-3 py-2 text-sm font-semibold text-sidebar-primary-foreground transition-colors hover:brightness-110",
            !expanded && "justify-center px-0",
          )}
        >
          <Plus size={18} className="shrink-0" />
          {expanded && <span>New Chat</span>}
        </button> : <div
          data-testid="viewer-read-only-notice"
          className={cn("mb-2 shrink-0 rounded-lg border border-sidebar-border bg-sidebar-accent/60 px-3 py-2 text-[0.68rem] text-sidebar-foreground/65", !expanded && "px-1 text-center")}
        >
          {expanded ? <><strong className="block text-sidebar-foreground/80">Read-only access</strong><span>Ask an administrator for member access to run tasks.</span></> : <LockKeyhole size={16} className="mx-auto" />}
        </div>}

        <button
          type="button"
          data-testid="open-project"
          onClick={() => go("workspaces")}
          title={!expanded ? "Open Project" : undefined}
          aria-label="Open Project"
          className={cn(
            "ras-open-project mb-2 flex shrink-0 items-center gap-2.5 rounded-lg border border-sidebar-primary/40 bg-sidebar-primary/10 px-3 py-2 text-sm font-semibold text-sidebar-primary transition-colors hover:bg-sidebar-primary/20",
            !expanded && "justify-center px-0",
          )}
        >
          <FolderOpen size={18} className="shrink-0" />
          {expanded && <span>Open Project</span>}
        </button>

        {/* Navigation participates in the sidebar's single unified scroll surface. */}
        <nav className="flex shrink-0 flex-col gap-0.5" aria-label="Workstation and assistant navigation">
          {visibleNavGroups.map((group) => (
            <div key={group.label} className="mt-1" role="group" aria-labelledby={`nav-group-${group.label.toLowerCase()}`}>
              <div
                id={`nav-group-${group.label.toLowerCase()}`}
                className={cn(
                  "px-3 pb-1 text-[0.58rem] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/35",
                  !expanded && "sr-only",
                )}
              >
                {group.label}
              </div>
              {group.items.map(navBtn)}
            </div>
          ))}

          {/* History stays lightweight: recent chats live in a popover instead of
           * taking a permanent destination in the primary navigation. */}
          <button
            ref={historyTriggerRef}
            type="button"
            data-testid="history-drawer-trigger"
            aria-label="Recent chats"
            aria-expanded={historyOpen}
            aria-controls="history-drawer"
            title={!expanded ? "Recent chats" : undefined}
            onClick={() => setHistoryOpen((open) => !open)}
            className={cn(
              "ras-nav-item group relative flex w-full items-center gap-3 rounded-lg px-3 py-1 text-[0.82rem] font-medium text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground",
              historyOpen && "is-active bg-sidebar-accent text-sidebar-foreground",
              !expanded && "justify-center px-0",
            )}
          >
            <Clock size={18} className={cn("shrink-0", historyOpen && "text-sidebar-primary")} />
            {expanded && <span className="flex-1 truncate text-left">Recent chats</span>}
            {(runningCount || taskCount) > 0 && (
              <span className={cn("rounded-full bg-sidebar-primary/15 px-2 py-0.5 text-[0.65rem] font-semibold text-sidebar-primary", !expanded && "absolute -right-0.5 -top-1 px-1.5 py-0")}>{runningCount || taskCount}</span>
            )}
          </button>

          {/* Settings — pinned with the primary nav, always reachable */}
          <div className="mt-auto pt-2">
            <button
              type="button"
              data-testid="nav-settings"
              aria-label="Settings"
              aria-current={view === "settings" ? "page" : undefined}
              onClick={() => go("settings", "general")}
              title={!expanded ? "Settings" : undefined}
              className={cn(
                "ras-nav-item flex w-full items-center gap-3 rounded-lg px-3 py-1 text-[0.82rem] font-medium transition-colors",
                view === "settings"
                  ? "is-active bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                !expanded && "justify-center px-0",
              )}
            >
              <Settings size={18} className="shrink-0" />
              {expanded && <span>Settings</span>}
            </button>
          </div>
        </nav>

        {expanded && (
          <section className="ras-sidebar-projects mt-3" aria-labelledby="sidebar-projects-heading">
            <div className="flex items-center justify-between gap-2 px-3 pb-1">
              <span id="sidebar-projects-heading" className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/35">Projects</span>
              <button type="button" className="text-[0.65rem] text-sidebar-foreground/45 transition-colors hover:text-sidebar-foreground" onClick={() => go("workspaces")}>Manage</button>
            </div>
            <div className="flex flex-col gap-0.5" data-testid="sidebar-project-list">
              {projects.map((project) => {
                const projectPath = project.path || project.root || "";
                const projectId = project.id || projectPath;
                const projectName = project.displayName || project.display_name || project.name || projectPath.split(/[\\/]/).filter(Boolean).pop() || "Project";
                const active = (activeWorkspaceId && project.id === activeWorkspaceId) || (activeWorkspacePath && projectPath === activeWorkspacePath);
                return (
                  <div key={projectId} className={cn("group/project flex items-center rounded-lg", active ? "bg-sidebar-accent text-sidebar-foreground" : "text-sidebar-foreground/55 hover:bg-sidebar-accent hover:text-sidebar-foreground")}>
                    <button type="button" className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-1.5 text-left text-[0.78rem]" title={`Open ${projectName}`} aria-current={active ? "location" : undefined} onClick={() => onSelectProject?.(project)}>
                      <Folder size={14} className="shrink-0 opacity-75" aria-hidden="true" />
                      <span className="truncate">{projectName}</span>
                    </button>
                    <button type="button" className="mr-1 grid size-7 shrink-0 place-items-center rounded-md text-sidebar-foreground/45 transition-colors hover:bg-sidebar-primary/10 hover:text-sidebar-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sidebar-ring" title={`Index and Graphify ${projectName}`} aria-label={`Index and Graphify ${projectName}`} onClick={() => graphifyProject?.(project)}>
                      <BrainCircuit size={13} aria-hidden="true" />
                    </button>
                  </div>
                );
              })}
              {projects.length === 0 && (
                <button type="button" className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[0.75rem] text-sidebar-foreground/45 hover:bg-sidebar-accent hover:text-sidebar-foreground" onClick={() => go("workspaces")}>
                  <FolderOpen size={14} aria-hidden="true" /> Open your first project
                </button>
              )}
            </div>
          </section>
        )}

        <div className="min-h-0 flex-1" aria-hidden="true" />

        {/* Runtime identity + privacy state — launch-time facts, never browser toggles. */}
        <div className={cn("ras-sidebar-footer mt-2 flex shrink-0 flex-col gap-1", !expanded && "is-collapsed", desktopOnly && "hidden")}>
          <div className="ras-runtime-row" title={nativeRuntime ? "Native workstation runtime" : "Docker server runtime"}>
            <RuntimeIcon size={15} aria-hidden="true" />
            {expanded && <span><small>Runtime</small><strong>{nativeRuntime ? "Native workstation" : "Docker server"}</strong></span>}
          </div>
          <div className="ras-privacy-row" title={locked ? "Privacy Lock enabled" : "Review mode"}>
            <LockKeyhole size={15} aria-hidden="true" />
            {expanded && <span>{locked ? "Privacy Lock enabled" : "Review mode"}</span>}
            <i className={locked ? "is-locked" : ""} aria-hidden="true" />
          </div>
          {expanded && <div className="ras-privacy-row" title={`${roleLabel(role)} appliance role`}>
            <LockKeyhole size={15} aria-hidden="true" />
            <span>{roleLabel(role)}</span>
          </div>}
          {logout && <button
            type="button"
            data-testid="sidebar-logout"
            onClick={logout}
            title={!expanded ? "Log out" : `Log out ${session?.username || ""}`}
            aria-label={`Log out ${session?.username || "current account"}`}
            className={cn("ras-privacy-row ras-sidebar-logout", !expanded && "justify-center")}
          >
            <LogOut size={15} aria-hidden="true" />
            {expanded && <span>Log out{session?.username ? ` · ${session.username}` : ""}</span>}
          </button>}
        </div>
      </aside>
      {historyOpen && (
        <>
          <button
            type="button"
            data-testid="history-drawer-scrim"
            aria-label="Close recent chats"
            onClick={() => setHistoryOpen(false)}
            className="fixed inset-0 z-40 cursor-default bg-black/25 sm:bg-transparent"
          />
          <section
            id="history-drawer"
            data-testid="history-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="history-drawer-title"
            className={cn(
              "fixed inset-y-0 left-0 z-50 flex w-[min(360px,calc(100vw-1rem))] flex-col border-r border-sidebar-border bg-sidebar px-4 py-4 text-sidebar-foreground shadow-2xl shadow-black/40 sm:left-[220px]",
              collapsed && "sm:left-[54px]",
            )}
          >
            <header className="flex items-start justify-between gap-3 border-b border-sidebar-border pb-3">
              <div>
                <p className="text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/40">Workspace memory</p>
                <h2 id="history-drawer-title" className="mt-1 text-base font-semibold">Recent chats</h2>
              </div>
              <button type="button" data-testid="history-drawer-close" aria-label="Close recent chats" onClick={() => setHistoryOpen(false)} className="grid size-8 place-items-center rounded-lg text-sidebar-foreground/55 hover:bg-sidebar-accent hover:text-sidebar-foreground">&#215;</button>
            </header>
            <label className="relative mt-3 block">
              <span className="sr-only">Search recent chats</span>
              <Search size={15} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sidebar-foreground/40" />
              <input
                ref={historySearchRef}
                data-testid="history-search"
                type="search"
                value={historyQuery}
                onChange={(event) => setHistoryQuery(event.target.value)}
                placeholder="Search recent chats"
                className="w-full rounded-lg border border-sidebar-border bg-sidebar-accent/55 py-2 pl-9 pr-3 text-sm text-sidebar-foreground outline-none placeholder:text-sidebar-foreground/35 focus:border-sidebar-primary/60 focus:ring-2 focus:ring-sidebar-primary/20"
              />
            </label>
            <div className="mt-3 flex items-center justify-between text-[0.67rem] text-sidebar-foreground/45">
              <span>{filteredSessions.length} of {sessions.length} recent chats</span>
              {taskAccess && emptySessionCount > 0 && <button type="button" data-testid="sidebar-clear-empty-chats" onClick={() => cleanupEmptySessions?.()} className="flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-sidebar-accent hover:text-sidebar-foreground"><Trash2 size={12} aria-hidden="true" />Clear {emptySessionCount} empty</button>}
            </div>
            <div className="mt-2 min-h-0 flex-1 overflow-y-auto" data-testid="history-session-list">
              {filteredSessions.length > 0 ? filteredSessions.map((s) => {
                const active = s.id === activeSessionId;
                return (
                  <div key={s.id} data-testid={"history-session-" + s.id} className={cn("group/session flex items-center rounded-lg border border-transparent", active ? "bg-sidebar-accent text-sidebar-foreground" : "text-sidebar-foreground/65 hover:border-sidebar-border hover:bg-sidebar-accent/60 hover:text-sidebar-foreground")}>
                    <button type="button" title={s.title || "Untitled chat"} onClick={() => { resumeSession?.(s.id); setHistoryOpen(false); }} className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left">
                      <MessageSquare size={15} className="shrink-0 opacity-65" aria-hidden="true" />
                      <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{s.title || "Untitled chat"}</span><span className="mt-0.5 block truncate text-[0.65rem] text-sidebar-foreground/40">{s.model || "Local session"}</span></span>
                    </button>
                    {taskAccess && <button type="button" data-testid={"sidebar-delete-chat-" + s.id} aria-label={"Delete " + (s.title || "Untitled chat")} title={s.isEmpty ? "Delete empty chat" : "Delete chat"} onClick={() => deleteSession?.(s)} className="mr-1 grid size-7 shrink-0 place-items-center rounded-md text-sidebar-foreground/40 hover:bg-red-500/10 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sidebar-ring"><Trash2 size={13} aria-hidden="true" /></button>}
                  </div>
                );
              }) : <div className="rounded-lg border border-dashed border-sidebar-border px-3 py-6 text-center text-sm text-sidebar-foreground/45">{historyQuery ? "No chats match that search." : "No recent chats yet."}</div>}
            </div>
            <footer className="mt-3 border-t border-sidebar-border pt-3">
              <button type="button" data-testid="history-view-all" onClick={() => { setHistoryOpen(false); go("activity"); }} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium text-sidebar-primary hover:bg-sidebar-primary/10"><span>View all activity</span><span aria-hidden="true">-&gt;</span></button>
            </footer>
          </section>
        </>
      )}
    </div>
  );
}
