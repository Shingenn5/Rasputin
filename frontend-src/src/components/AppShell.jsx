import React from "react";
import { Box, Laptop, Menu, ShieldAlert, X } from "lucide-react";
import { DashSidebar } from "./shell/DashSidebar.jsx";

export function AppShell({ children, globalStatus, clearGlobalStatus, sidebarProps, trustedWorkspace, onRevokeTrust }) {
  const nativeRuntime = sidebarProps?.runtimeMode === "native";
  const mobileSidebarTriggerRef = React.useRef(null);

  return (
    <>
      <a className="skip-link" href="#mainContent">Skip to main content</a>
      {globalStatus && (
        <div id="globalStatus" className="global-status" role="status" aria-live="polite">
          <span>{globalStatus}</span>
          {clearGlobalStatus && (
            <button type="button" aria-label="Dismiss status message" onClick={clearGlobalStatus}>
              <X size={14} />
            </button>
          )}
        </div>
      )}
      <div className="dash-aurora ras-atmosphere" aria-hidden="true"><i /></div>
      <div className="dash-frame relative z-[1] flex h-dvh overflow-hidden text-foreground" id="appFrame">
        <DashSidebar {...sidebarProps} mobileTriggerRef={mobileSidebarTriggerRef} />
        <main className="dash-frame-main min-w-0 flex-1 overflow-y-auto" id="mainContent" tabIndex="-1">
          {/* Sticky top stack: trusted-workspace banner (all breakpoints) + mobile topbar (< sm) share one sticky offset so they don't overlap on scroll */}
          <div className="sticky top-0 z-10 flex flex-col">
            {trustedWorkspace?.active && (
              <div
                className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-500/40 bg-amber-500/15 px-3 py-2 text-xs font-medium text-amber-800 dark:text-amber-200 sm:text-sm"
                role="status"
                data-testid="trusted-workspace-banner"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <ShieldAlert size={14} className="shrink-0" aria-hidden="true" />
                  <span className="truncate">
                    Trusted Dev Mode active for <strong>{trustedWorkspace.name}</strong> — file writes and local git run without per-action approval. Host Shell remains separate.
                  </span>
                </span>
                <button
                  type="button"
                  onClick={onRevokeTrust}
                  aria-label={`Revoke Trusted Dev Mode for ${trustedWorkspace.name}`}
                  className="shrink-0 rounded-md border border-amber-500/50 px-2 py-1 text-xs font-semibold text-amber-900 transition-colors hover:bg-amber-500/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-600 dark:text-amber-100"
                >
                  Revoke
                </button>
              </div>
            )}
            {/* Mobile topbar — hamburger + brand, hidden on sm+ */}
            <div className="flex items-center gap-3 border-b border-border bg-sidebar/90 px-3 py-2.5 backdrop-blur-sm sm:hidden">
              <button
                ref={mobileSidebarTriggerRef}
                type="button"
                data-testid="mobile-sidebar-toggle"
                aria-label={sidebarProps.mobileOpen ? "Close navigation" : "Open navigation"}
                aria-expanded={Boolean(sidebarProps.mobileOpen)}
                aria-controls="rasputin-sidebar"
                onClick={sidebarProps.toggleSidebar}
                className="ras-mobile-nav-trigger grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <Menu size={18} />
              </button>
              <span className="ras-mobile-brand text-sm font-semibold text-foreground">Rasputin</span>
              <span className="ras-mobile-runtime ml-auto inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                {nativeRuntime ? <Laptop size={12} aria-hidden="true" /> : <Box size={12} aria-hidden="true" />}
                {nativeRuntime ? "Native" : "Docker"}
              </span>
            </div>
          </div>
          {children}
        </main>
      </div>
    </>
  );
}
