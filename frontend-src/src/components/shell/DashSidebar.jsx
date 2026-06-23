import React from "react";
import {
  Activity,
  Archive,
  Brain,
  ChevronsLeft,
  ChevronsRight,
  FlaskConical,
  LayoutDashboard,
  MessageSquare,
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
  recentSessions = [],
  resumeSession,
  activeSessionId,
}) {
  const isActive = (item) =>
    view === item.view && (item.view !== "settings" || settingsSection === item.section);

  const sessions = (recentSessions || []).slice(0, 8);

  return (
    <aside
      className={cn(
        "flex h-dvh flex-col gap-1 overflow-y-auto border-r border-sidebar-border bg-sidebar px-3 py-5 text-sidebar-foreground",
        collapsed ? "w-[76px] items-center" : "w-[248px]",
      )}
    >
      {/* Brand */}
      <div className={cn("flex items-center gap-2.5 px-2 pb-4", collapsed && "flex-col gap-3 px-0")}>
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-primary to-emerald-700 font-extrabold text-primary-foreground shadow-[0_4px_16px_-4px_var(--primary)]">
          R
        </div>
        {!collapsed && (
          <div className="flex flex-col leading-tight">
            <span className="text-[0.95rem] font-bold tracking-tight">Rasputin</span>
            <span className="text-[0.66rem] text-muted-foreground">Local AI Operations</span>
          </div>
        )}
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "grid size-7 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
            !collapsed && "ml-auto",
          )}
        >
          {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        </button>
      </div>

      {/* New chat */}
      <button
        type="button"
        data-testid="new-task"
        onClick={newTask}
        className={cn(
          "mb-2 flex items-center gap-2.5 rounded-xl bg-primary/12 px-3 py-2.5 text-sm font-medium text-primary ring-1 ring-inset ring-primary/20 transition-colors hover:bg-primary/20",
          collapsed && "justify-center px-0",
        )}
      >
        <Plus size={18} />
        {!collapsed && <span>New Chat</span>}
      </button>

      {/* Grouped nav */}
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="mt-3">
          {!collapsed && (
            <div className="px-3 pb-2 text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground/70">
              {group.label}
            </div>
          )}
          {group.items.map((item) => {
            const Icon = item.icon;
            const active = isActive(item);
            return (
              <button
                key={item.view}
                type="button"
                data-testid={item.testId}
                aria-current={active ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                onClick={() => go(item.view, item.section)}
                className={cn(
                  "group mb-0.5 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  active
                    ? "bg-gradient-to-r from-primary/15 to-transparent text-foreground ring-1 ring-inset ring-border"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  collapsed && "justify-center px-0",
                )}
              >
                <Icon size={18} className={cn("shrink-0", active && "text-primary")} />
                {!collapsed && <span className="flex-1 text-left">{item.label}</span>}
                {!collapsed && item.testId === "nav-activity" && (runningCount || taskCount) > 0 && (
                  <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[0.65rem] font-semibold text-primary">
                    {runningCount || taskCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      {/* Chat history */}
      {!collapsed && sessions.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between px-3 pb-2">
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
          <div className="flex flex-col">
            {sessions.map((s) => {
              const active = s.id === activeSessionId;
              return (
                <button
                  key={s.id}
                  type="button"
                  title={s.title || "Untitled chat"}
                  onClick={() => resumeSession?.(s.id)}
                  className={cn(
                    "flex items-center gap-2.5 truncate rounded-lg px-3 py-2 text-left text-[0.8rem] transition-colors",
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
      )}

      <div className="flex-1" />

      {/* Settings + promo */}
      <button
        type="button"
        data-testid="nav-settings"
        onClick={() => go("settings", "general")}
        className={cn(
          "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
          view === "settings" && "bg-accent text-foreground",
          collapsed && "justify-center px-0",
        )}
      >
        <Settings size={18} className="shrink-0" />
        {!collapsed && <span>Settings</span>}
      </button>

      {!collapsed && (
        <div className="mt-2 rounded-xl border border-border bg-gradient-to-br from-secondary to-card p-3.5">
          <div className="flex items-center gap-2">
            <LifeBuoy size={15} className="text-primary" />
            <span className="text-sm font-semibold">{locked ? "Privacy locked" : "Review mode"}</span>
          </div>
          <p className="mt-1 text-[0.68rem] text-muted-foreground">
            All operations run locally on your hardware.
          </p>
        </div>
      )}
    </aside>
  );
}
