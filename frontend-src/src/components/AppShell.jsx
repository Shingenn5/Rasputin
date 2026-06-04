import React from "react";
import { PanelLeftOpen } from "lucide-react";
import { Sidebar } from "./Sidebar.jsx";

export function AppShell({ children, globalStatus, sidebarProps }) {
  return (
    <>
      <a className="skip-link" href="#mainContent">Skip to main content</a>
      {globalStatus && (
        <div id="globalStatus" className="global-status" role="status" aria-live="polite">
          {globalStatus}
        </div>
      )}
      <div className="app-frame" id="appFrame">
        <Sidebar {...sidebarProps} />
        <button
          className="mobile-shell-toggle icon-button"
          data-testid="mobile-sidebar-toggle"
          type="button"
          aria-label="Open navigation"
          onClick={sidebarProps.toggleSidebar}
        >
          <PanelLeftOpen size={19} />
        </button>
        <main className="app-main" id="mainContent" tabIndex="-1">{children}</main>
      </div>
    </>
  );
}
