import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Archive,
  Box,
  Brain,
  FlaskConical,
  LayoutDashboard,
  Laptop,
  LockKeyhole,
  LogOut,
  MessageSquare,
  PanelLeft,
  Plus,
  Rocket,
  Search,
  Settings,
  Sparkles,
  Trash2,
  FolderGit2,
} from "lucide-react";
import { cn } from "@/lib/utils.js";
import { canAccessView, canRunTasks, normalizedRole, roleLabel } from "@/lib/access.js";

/* Grouped navigation modeled on the reference dashboards. */
const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { view: "home", label: "Dashboard", icon: LayoutDashboard, testId: "nav-home" },
      { view: "chat", label: "Chat", icon: MessageSquare, testId: "nav-chat" },
      { view: "workspaces", label: "Workspaces", icon: FolderGit2, testId: "nav-workspaces" },
      { view: "activity", label: "Activity", icon: Activity, testId: "nav-activity" },
    ],
  },
  {
    label: "Fleet",
    items: [
      { view: "models", label: "Models", icon: Sparkles, testId: "nav-models" },
      { view: "warsat", label: "Warsat", icon: Rocket, testId: "nav-warsat" },
      { view: "trials", label: "Trials", icon: FlaskConical, testId: "nav-trials" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { view: "archive", label: "Archive", icon: Archive, testId: "nav-archive" },
      { view: "memory", label: "Memory", icon: Brain, testId: "nav-memory" },
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
}) {
  const role = normalizedRole(session?.role);
  const taskAccess = canRunTasks(role);
  const visibleNavGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => canAccessView(role, item.view)),
  })).filter((group) => group.items.length > 0);
  const asideRef = useRef(null);
  const wasMobileOpenRef = useRef(mobileOpen);
  const reducedMotion = motionMode === "reduced";
  // Collapsed mode is a deliberate, persistent rail. It never relies on hover
  // for access; the brand control is always keyboard-reachable and reopens it.
  const expanded = !collapsed || mobileOpen;

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

  const isActive = (item) =>
    view === item.view && (item.view !== "settings" || settingsSection === item.section);
  const sessions = (recentSessions || []).slice(0, 12);
  const nativeRuntime = runtimeMode === "native";
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
        aria-label={item.label}
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
        {expanded && item.testId === "nav-activity" && (runningCount || taskCount) > 0 && (
          <span className="rounded-full bg-sidebar-primary/15 px-2 py-0.5 text-[0.65rem] font-semibold text-sidebar-primary">
            {runningCount || taskCount}
          </span>
        )}
      </button>
    );
  };

  return (
    <div
      className={cn(
        "relative h-dvh shrink-0 w-0",
        collapsed ? "sm:w-[76px]" : "sm:w-[248px]",
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
          "ras-sidebar ras-sidebar-scroll absolute inset-y-0 left-0 z-30 flex flex-col overflow-x-hidden overflow-y-auto border-r border-sidebar-border bg-sidebar px-3 py-3 text-sidebar-foreground transition-[width,transform] duration-200 ease-out",
          expanded ? "w-[248px]" : "w-[76px]",
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
            aria-label={collapsed && !mobileOpen ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed && !mobileOpen ? "Expand sidebar" : "Collapse sidebar"}
            className="ras-brand-sigil shrink-0"
          >
            <span>R</span><i aria-hidden="true" />
            <PanelLeft size={11} className="ras-brand-toggle-icon" aria-hidden="true" />
          </button>
          {expanded && (
            <div className="flex flex-col leading-tight">
              <span className="ras-sidebar-wordmark text-[1rem] font-bold tracking-tight">Rasputin</span>
              <span className="text-[0.63rem] uppercase tracking-[0.12em] text-sidebar-foreground/45">Operator console</span>
            </div>
          )}
        </div>

        {/* New chat */}
        {taskAccess ? <button
          type="button"
          data-testid="new-task"
          onClick={newTask}
          title={!expanded ? "New Chat" : undefined}
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

        {/* Navigation participates in the sidebar's single unified scroll surface. */}
        <nav className="flex shrink-0 flex-col gap-0.5">
          {visibleNavGroups.map((group) => (
            <div key={group.label} className="mt-1">
              {expanded && (
                <div className="px-3 pb-1 text-[0.58rem] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/35">
                  {group.label}
                </div>
              )}
              {group.items.map(navBtn)}
            </div>
          ))}

          {/* Settings — pinned with the primary nav, always reachable */}
          <div className="mt-1">
            <button
              type="button"
              data-testid="nav-settings"
              aria-label="Settings"
              aria-current={view === "settings" ? "page" : undefined}
              onClick={() => go("settings", role === "admin" ? "general" : "accounts")}
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
            <button
              type="button"
              data-testid="sidebar-command-palette"
              aria-label="Search and commands"
              onClick={() => window.dispatchEvent(new Event("rasputin:open-command-palette"))}
              title={!expanded ? "Search and commands" : undefined}
              className={cn(
                "ras-nav-item mt-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-1 text-[0.82rem] font-medium text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground",
                !expanded && "justify-center px-0",
              )}
            >
              <Search size={18} className="shrink-0" />
              {expanded && <><span className="flex-1 text-left">Search &amp; commands</span><kbd className="text-[0.58rem] text-sidebar-foreground/35">Ctrl K</kbd></>}
            </button>
          </div>
        </nav>

        {/* Recent chats continue naturally in the unified sidebar flow. */}
        {expanded && sessions.length > 0 && (
          <div className="-mr-1 mt-3 flex shrink-0 flex-col pr-1">
            <div className="flex shrink-0 items-center justify-between gap-2 px-3 pb-1">
              <span className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/35">
                Recent Chats
              </span>
              {taskAccess && <span className="flex items-center gap-2">
                {emptySessionCount > 0 && <button
                  type="button"
                  data-testid="sidebar-clear-empty-chats"
                  onClick={() => cleanupEmptySessions?.()}
                  title={`Remove ${emptySessionCount} empty chat${emptySessionCount === 1 ? "" : "s"}`}
                  aria-label={`Remove ${emptySessionCount} empty chat${emptySessionCount === 1 ? "" : "s"}`}
                  className="flex items-center gap-1 text-[0.65rem] text-sidebar-foreground/45 transition-colors hover:text-sidebar-foreground"
                >
                  <Trash2 size={11} aria-hidden="true" /> {emptySessionCount}
                </button>}
                <button
                  type="button"
                  onClick={() => go("sessions")}
                  className="text-[0.65rem] text-sidebar-foreground/45 transition-colors hover:text-sidebar-foreground"
                >
                  All
                </button>
              </span>}
            </div>
            <div className="flex flex-col gap-0.5">
              {sessions.map((s) => {
                const active = s.id === activeSessionId;
                return (
                  <div
                    key={s.id}
                    className={cn(
                      "group/session flex shrink-0 items-center rounded-lg transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-foreground"
                        : "text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                    )}
                  >
                    <button
                      type="button"
                      title={s.title || "Untitled chat"}
                      onClick={() => resumeSession?.(s.id)}
                      className="flex min-w-0 flex-1 items-center gap-2.5 truncate px-3 py-1.5 text-left text-[0.8rem]"
                    >
                      <MessageSquare size={14} className="shrink-0 opacity-70" />
                      <span className="truncate">{s.title || "Untitled chat"}</span>
                    </button>
                    {taskAccess && <button
                      type="button"
                      data-testid={`sidebar-delete-chat-${s.id}`}
                      aria-label={`Delete ${s.title || "Untitled chat"}`}
                      title={s.isEmpty ? "Delete empty chat" : "Delete chat"}
                      onClick={() => deleteSession?.(s)}
                      className="mr-1 grid size-7 shrink-0 place-items-center rounded-md text-sidebar-foreground/50 transition-colors hover:bg-red-500/10 hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-sidebar-ring"
                    >
                      <Trash2 size={13} aria-hidden="true" />
                    </button>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {(!expanded || sessions.length === 0) && <div className="min-h-0 flex-1" aria-hidden="true" />}

        {/* Runtime identity + privacy state — launch-time facts, never browser toggles. */}
        <div className={cn("ras-sidebar-footer mt-2 flex shrink-0 flex-col gap-1", !expanded && "is-collapsed")}>
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
          <button
            type="button"
            data-testid="sidebar-logout"
            onClick={logout}
            title={!expanded ? "Log out" : `Log out ${session?.username || ""}`}
            aria-label={`Log out ${session?.username || "current account"}`}
            className={cn("ras-privacy-row ras-sidebar-logout", !expanded && "justify-center")}
          >
            <LogOut size={15} aria-hidden="true" />
            {expanded && <span>Log out{session?.username ? ` · ${session.username}` : ""}</span>}
          </button>
        </div>
      </aside>
    </div>
  );
}
