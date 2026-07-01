import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Archive,
  Brain,
  ChevronsLeft,
  FlaskConical,
  LayoutDashboard,
  MessageSquare,
  PanelLeft,
  Plus,
  Rocket,
  Settings,
  Sparkles,
  FolderGit2,
  LifeBuoy,
} from "lucide-react";
import { cn } from "@/lib/utils.js";

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
  mobileOpen = false,
  recentSessions = [],
  resumeSession,
  activeSessionId,
}) {
  // `collapsed` is the persisted rail mode; hovering temporarily expands on sm+.
  // `mobileOpen` drives the slide-in overlay on mobile (< sm breakpoint).
  const [hovered, setHovered] = useState(false);
  const expanded = !collapsed || hovered || mobileOpen;

  const isActive = (item) =>
    view === item.view && (item.view !== "settings" || settingsSection === item.section);
  const sessions = (recentSessions || []).slice(0, 12);

  const navBtn = (item) => {
    const Icon = item.icon;
    const active = isActive(item);
    return (
      <button
        key={item.view}
        type="button"
        data-testid={item.testId}
        aria-current={active ? "page" : undefined}
        title={!expanded ? item.label : undefined}
        onClick={() => go(item.view, item.section)}
        className={cn(
          "group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
          active ? "text-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
          !expanded && "justify-center px-0",
        )}
      >
        {active && (
          <motion.span
            layoutId="nav-active"
            transition={{ type: "spring", stiffness: 400, damping: 32 }}
            className="absolute inset-0 -z-10 rounded-xl bg-gradient-to-r from-primary/18 to-primary/5 ring-1 ring-inset ring-primary/25"
          />
        )}
        <Icon size={18} className={cn("shrink-0", active && "text-primary")} />
        {expanded && <span className="flex-1 truncate text-left">{item.label}</span>}
        {expanded && item.testId === "nav-activity" && (runningCount || taskCount) > 0 && (
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[0.65rem] font-semibold text-primary">
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
      onMouseEnter={() => collapsed && setHovered(true)}
      onMouseLeave={() => setHovered(false)}
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
        className={cn(
          "absolute inset-y-0 left-0 z-30 flex flex-col overflow-hidden border-r border-sidebar-border bg-sidebar px-3 py-5 text-sidebar-foreground transition-[width,transform] duration-200 ease-out",
          expanded ? "w-[248px]" : "w-[76px]",
          // Mobile: slide off-screen when closed; sm+ always visible in flow.
          !mobileOpen && "-translate-x-full sm:translate-x-0",
          // Shadow: hover-expand on desktop, or slide-in overlay on mobile.
          (collapsed && hovered) || mobileOpen ? "shadow-2xl shadow-black/50" : "",
        )}
      >
        {/* Brand */}
        <div className={cn("flex shrink-0 items-center gap-2.5 px-2 pb-4", !expanded && "justify-center px-0")}>
          <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-primary to-emerald-700 font-extrabold text-primary-foreground shadow-[0_4px_16px_-4px_var(--primary)]">
            R
          </div>
          {expanded && (
            <div className="flex flex-col leading-tight">
              <span className="text-[0.95rem] font-bold tracking-tight">Rasputin</span>
              <span className="text-[0.66rem] text-muted-foreground">Local AI Operations</span>
            </div>
          )}
          {expanded && (
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={collapsed ? "Pin sidebar open" : "Collapse sidebar"}
              title={collapsed ? "Pin open" : "Collapse"}
              className="ml-auto grid size-7 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {collapsed ? <PanelLeft size={15} /> : <ChevronsLeft size={16} />}
            </button>
          )}
        </div>

        {/* New chat */}
        <button
          type="button"
          data-testid="new-task"
          onClick={newTask}
          title={!expanded ? "New Chat" : undefined}
          className={cn(
            "mb-2 flex shrink-0 items-center gap-2.5 rounded-xl bg-primary/12 px-3 py-2.5 text-sm font-medium text-primary ring-1 ring-inset ring-primary/20 transition-colors hover:bg-primary/20",
            !expanded && "justify-center px-0",
          )}
        >
          <Plus size={18} className="shrink-0" />
          {expanded && <span>New Chat</span>}
        </button>

        {/* Primary nav (does not scroll) */}
        <nav className="flex shrink-0 flex-col gap-0.5">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mt-3">
              {expanded && (
                <div className="px-3 pb-2 text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
                  {group.label}
                </div>
              )}
              {group.items.map(navBtn)}
            </div>
          ))}

          {/* Settings — pinned with the primary nav, always reachable */}
          <div className="mt-3">
            <button
              type="button"
              data-testid="nav-settings"
              onClick={() => go("settings", "general")}
              title={!expanded ? "Settings" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                view === "settings"
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
                !expanded && "justify-center px-0",
              )}
            >
              <Settings size={18} className="shrink-0" />
              {expanded && <span>Settings</span>}
            </button>
          </div>
        </nav>

        {/* Recent chats — the flexible, scrollable region between the pinned
            nav (with Settings) above and the pinned privacy chip below. */}
        {expanded && sessions.length > 0 ? (
          <div className="mt-4 flex min-h-0 flex-1 flex-col">
            <div className="flex shrink-0 items-center justify-between px-3 pb-2">
              <span className="text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
                Recent Chats
              </span>
              <button
                type="button"
                onClick={() => go("chat")}
                className="text-[0.62rem] text-muted-foreground/70 transition-colors hover:text-foreground"
              >
                All
              </button>
            </div>
            <div className="-mr-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto pr-1">
              {sessions.map((s) => {
                const active = s.id === activeSessionId;
                return (
                  <button
                    key={s.id}
                    type="button"
                    title={s.title || "Untitled chat"}
                    onClick={() => resumeSession?.(s.id)}
                    className={cn(
                      "flex shrink-0 items-center gap-2.5 truncate rounded-lg px-3 py-2 text-left text-[0.8rem] transition-colors",
                      active
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground",
                    )}
                  >
                    <MessageSquare size={14} className="shrink-0 opacity-70" />
                    <span className="truncate">{s.title || "Untitled chat"}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex-1" />
        )}

        {/* Privacy chip — pinned at the very bottom */}
        {expanded && (
          <div className="mt-3 flex shrink-0 items-center gap-2 rounded-xl border border-border bg-gradient-to-br from-secondary to-card px-3.5 py-2.5">
            <LifeBuoy size={15} className="shrink-0 text-primary" />
            <span className="text-[0.8rem] font-semibold">{locked ? "Privacy locked" : "Review mode"}</span>
          </div>
        )}
      </aside>
    </div>
  );
}
