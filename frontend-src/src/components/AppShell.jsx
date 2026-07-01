import React from "react";
import { Menu, X } from "lucide-react";
import { DashSidebar } from "./shell/DashSidebar.jsx";

export function AppShell({ children, globalStatus, clearGlobalStatus, sidebarProps }) {
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
      <div className="dash-aurora" aria-hidden="true"><i /></div>
      <div className="dash-frame relative z-[1] flex h-dvh overflow-hidden bg-transparent text-foreground" id="appFrame">
        <DashSidebar {...sidebarProps} />
        <main className="dash-frame-main min-w-0 flex-1 overflow-y-auto" id="mainContent" tabIndex="-1">
          {/* Sticky mobile topbar — hamburger + brand, hidden on sm+ */}
          <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-sidebar/90 px-3 py-2.5 backdrop-blur-sm sm:hidden">
            <button
              type="button"
              data-testid="mobile-sidebar-toggle"
              aria-label="Open navigation"
              onClick={sidebarProps.toggleSidebar}
              className="grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <Menu size={18} />
            </button>
            <span className="text-sm font-semibold text-foreground">Rasputin</span>
          </div>
          {children}
        </main>
      </div>
    </>
  );
}
