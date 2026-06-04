import React from "react";
import { Button } from "react-bootstrap";

export function AuditView({ view, events, refresh }) {
  return (
    <section className={`app-view ${view === "audit" ? "active" : ""}`} id="auditView" data-app-view="audit">
      <header className="page-header border-bottom bg-body">
        <div>
          <h1 className="mb-0">Audit</h1>
          <p className="text-body-secondary mb-0">Recent local security and runtime events.</p>
        </div>
        <Button variant="outline-secondary" size="sm" onClick={refresh}>Refresh Audit</Button>
      </header>
      <pre id="auditLog" className="log-box audit-log">{JSON.stringify(events, null, 2)}</pre>
    </section>
  );
}
