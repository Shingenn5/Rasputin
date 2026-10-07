import React from "react";
import { Badge, Button, Card, Stack } from "react-bootstrap";
import { displayWorkspaceName } from "../../lib/display.js";
import { PageHeader, formatRuntimeTime } from "./RuntimePrimitives.jsx";

export function ApprovalsView({ view, approvals, approveApproval, denyApproval, refreshApprovals, openTaskDetails }) {
  const items = approvals?.approvals || [];
  return (
    <section className={`app-view ${view === "approvals" ? "active" : ""}`} id="approvalsView" data-app-view="approvals">
      <PageHeader title="Approvals" text="Risky tool actions wait here before execution." action={<Button variant="outline-secondary" size="sm" onClick={refreshApprovals}>Refresh</Button>} />
      <div className="task-dashboard">
        <Stack gap={3}>
          {items.map((approval) => (
            <Card className="settings-card shadow-sm" key={approval.id} data-testid="approval-card">
              <Card.Body>
                <div className="section-row">
                  <div>
                    <Badge bg={approval.status === "pending" ? "warning" : approval.status === "approved" ? "success" : "secondary"}>{approval.status}</Badge>
                    <h2 className="mt-2">{approval.summary}</h2>
                    <p className="text-body-secondary mb-0">
                      Code {approval.code} / {approval.actionType || approval.action_type} / {displayWorkspaceName(approval.workspace)}
                    </p>
                  </div>
                  <Stack direction="horizontal" gap={2}>
                    {approval.taskId && (
                      <Button variant="outline-secondary" onClick={() => openTaskDetails(approval.taskId)}>Open Task</Button>
                    )}
                    {approval.status === "pending" && (
                      <>
                        <Button onClick={() => approveApproval(approval.id)}>Approve</Button>
                        <Button variant="outline-danger" onClick={() => denyApproval(approval.id)}>Deny</Button>
                      </>
                    )}
                  </Stack>
                </div>
                <dl className="detail-grid approval-detail-grid mt-3">
                  <dt>Risk</dt><dd>{approval.riskLevel || approval.risk_level || "approval required"}</dd>
                  <dt>Workspace</dt><dd>{displayWorkspaceName(approval.workspace)}</dd>
                  <dt>Expires</dt><dd>{formatRuntimeTime(approval.expiresAt || approval.expires_at)}</dd>
                  <dt>Details</dt><dd>{summarizeApproval(approval.redactedDetail || approval.redacted_detail || {})}</dd>
                </dl>
                <details className="advanced-block approval-raw-detail">
                  <summary>Redacted metadata</summary>
                  <pre className="log-box mt-3 mb-0">{JSON.stringify(approval.redactedDetail || approval.redacted_detail || {}, null, 2)}</pre>
                </details>
              </Card.Body>
            </Card>
          ))}
          {!items.length && <EmptyCard title="No approvals" text="Rasputin has no pending approval requests." />}
        </Stack>
      </div>
    </section>
  );
}

function EmptyCard({ title, text }) {
  return <Card className="settings-card shadow-sm"><Card.Body><h2>{title}</h2><p className="text-body-secondary mb-0">{text}</p></Card.Body></Card>;
}

function summarizeApproval(value) {
  if (!value || typeof value !== "object") return "No redacted details.";
  return Object.entries(value)
    .slice(0, 6)
    .map(([key, item]) => `${key}: ${typeof item === "object" ? JSON.stringify(item) : item}`)
    .join(" / ") || "No redacted details.";
}
