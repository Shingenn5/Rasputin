import React, { useState } from "react";
import { Card, Button, Row, Col, Spinner, Alert } from "react-bootstrap";
import { ActivitySquare, HeartPulse, Terminal, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, postJson } from "../../api/client.js";

export function DiagnosticsSettings() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [recovery, setRecovery] = useState(null);
  const [recoveryBusy, setRecoveryBusy] = useState(false);

  const runDiagnostics = async () => {
    setRunning(true);
    setResults(null);
    setError(null);
    try {
      setResults(await api("/api/settings/diagnostics?category=all"));
    } catch (err) {
      setError({ context: "diagnostics", message: String(err.message || err), nextAction: "Check that you are signed in and that Docker/WSL or the local runtime is available, then retry diagnostics." });
    } finally {
      setRunning(false);
    }
  };

  const runRecovery = async (action, body = {}) => {
    setRecoveryBusy(true);
    setError(null);
    try {
      const path = action === "backup" ? "/api/recovery/backup" : action === "export" ? "/api/recovery/export" : "/api/recovery/delete-preview";
      setRecovery({ action, data: await postJson(path, body) });
    } catch (err) {
      setError({ context: "recovery", message: String(err.message || err), nextAction: "No data was changed. Check authentication, workspace permissions, and available disk space, then retry the recovery action." });
    } finally {
      setRecoveryBusy(false);
    }
  };

  const deleteMyData = async () => {
    if (!window.confirm("Delete your Rasputin sessions, tasks, memory, and assistant records? This cannot be undone.")) return;
    setRecoveryBusy(true);
    setError(null);
    try {
      setRecovery({ action: "delete", data: await postJson("/api/recovery/delete", { confirmation: "DELETE MY RASPUTIN DATA", dryRun: false }) });
    } catch (err) {
      setError({ context: "recovery", message: String(err.message || err), nextAction: "No data was deleted. Check authentication and permissions, then retry only after reviewing the deletion preview." });
    } finally {
      setRecoveryBusy(false);
    }
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><HeartPulse className="me-2 text-danger" size={28} />Diagnostics Center</h2>
          <p className="text-body-secondary mb-0">Validate system health, dependency status, and network connectivity.</p>
        </div>
      </div>

      <Card className="shadow-sm border-0 mb-4 bg-body-tertiary">
        <Card.Body className="p-4 text-center">
          <ActivitySquare size={48} className="text-muted mb-3 opacity-50" />
          <h5>System Health Check</h5>
          <p className="text-muted mb-4">Run a full diagnostic suite to ensure Rasputin has all required permissions and dependencies to operate.</p>
          {running && <Alert variant="info" role="status" aria-live="polite" data-testid="diagnostic-loading" className="text-start">Diagnostics are running. This may take a moment while runtime, Docker/WSL, tool, and workspace checks complete.</Alert>}
          <Button 
            variant="primary" 
            size="lg" 
            className="fw-semibold px-5"
            onClick={runDiagnostics}
            disabled={running}
          >
            {running ? <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" className="me-2" />Running Diagnostics...</> : "Start Diagnostic Run"}
          </Button>
        </Card.Body>
      </Card>

      <Card className="shadow-sm border-0 mb-4" data-testid="recovery-panel">
        <Card.Body className="p-4">
          <div className="d-flex flex-wrap align-items-start justify-content-between gap-3">
            <div>
              <h5>Recovery and ownership</h5>
              <p className="text-muted mb-0">Create a hashed, manifest-backed application backup, export owner-safe metadata, or preview deletion of your records.</p>
            </div>
            <div className="d-flex flex-wrap gap-2">
              <Button variant="outline-primary" size="sm" disabled={recoveryBusy} onClick={() => runRecovery("backup", { dryRun: true })}>Preview backup</Button>
              <Button variant="primary" size="sm" disabled={recoveryBusy} onClick={() => runRecovery("backup", { dryRun: false })}>Create backup</Button>
              <Button variant="outline-secondary" size="sm" disabled={recoveryBusy} onClick={() => runRecovery("export")}>Export my data</Button>
              <Button variant="outline-danger" size="sm" disabled={recoveryBusy} onClick={() => runRecovery("delete")}>Preview deletion</Button>
            </div>
          </div>
          {recoveryBusy && <Alert variant="info" role="status" aria-live="polite" data-testid="recovery-loading" className="mt-3 mb-0">Recovery action is running. Keep this page open until the result is reported.</Alert>}
          {recovery && (
            <Alert variant={recovery.action === "delete" ? "warning" : "success"} role="status" aria-live="polite" className="mt-3 mb-0" data-testid="recovery-result">
              <strong>{titleize(recovery.action)} result</strong>
              {recovery.data?.path && <div className="small mt-1">Artifact: <code>{recovery.data.path}</code></div>}
              {recovery.data?.fileCount !== undefined && <div className="small mt-1">{recovery.data.fileCount} file(s) included; {recovery.data.excludedCount || 0} excluded by policy.</div>}
              {recovery.data?.counts && <div className="small mt-1">Owner records: {Object.entries(recovery.data.counts).map(([key, value]) => `${key} ${value}`).join(" · ") || "none"}</div>}
              {recovery.action === "delete" && recovery.data?.dryRun && <Button variant="danger" size="sm" className="mt-2" onClick={deleteMyData}>Confirm permanent deletion</Button>}
            </Alert>
          )}
        </Card.Body>
      </Card>

      {error && <Alert variant="danger" role="alert" aria-live="assertive" data-testid={error.context === "recovery" ? "recovery-error" : "diagnostic-error"}>
        <strong>{error.context === "recovery" ? "Recovery action failed" : "Diagnostics failed"}</strong>
        <div>{error.message}</div>
        <div className="small mt-2"><strong>Next:</strong> {error.nextAction}</div>
      </Alert>}

      {results && (
        <div data-testid="diagnostic-results">
        <Row className="g-3 animate-fade-in">
          <Col md={12}>
            <Alert variant={overallVariant(results.status)} role={results.status === "healthy" ? "status" : "alert"} aria-live="polite" className="d-flex align-items-start m-0" data-testid={results.status === "healthy" ? "diagnostic-success" : "diagnostic-status"}>
              {results.status === "healthy" ? <CheckCircle2 className="me-3" size={24} /> : <AlertCircle className="me-3" size={24} />}
              <div>
                <strong>Diagnostic status: {titleize(results.status)}</strong><br />
                <span className="small">Rasputin {results.app?.version || "unknown"} · {results.app?.runtime || "runtime unknown"} · {results.app?.platform || "platform unknown"}</span>
              </div>
            </Alert>
          </Col>
          {(results.checks || []).map((check) => (
            <Col md={6} key={check.id || check.label}>
              <Alert variant={statusVariant(check.status)} className="d-flex align-items-start m-0 h-100">
                {check.status === "pass" ? <CheckCircle2 className="me-3" size={24} /> : check.status === "warn" ? <Terminal className="me-3" size={24} /> : <AlertCircle className="me-3" size={24} />}
                <div>
                  <strong>{check.label}</strong><br />
                  <span className="small">{check.detail}</span>
                  {nextActionFor(check) && <div className="small mt-2"><strong>Next:</strong> {nextActionFor(check)}</div>}
                </div>
              </Alert>
            </Col>
          ))}
        </Row>
        </div>
      )}
    </section>
  );
}

function statusVariant(status) {
  if (status === "pass") return "success";
  if (status === "warn") return "warning";
  return "danger";
}

function overallVariant(status) {
  if (status === "healthy") return "success";
  if (status === "attention") return "warning";
  return "danger";
}

function titleize(value) {
  return String(value || "unknown").replace(/[-_]/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}


function nextActionFor(check) {
  if (check.nextAction) return check.nextAction;
  const text = `${check.id || ""} ${check.label || ""} ${check.detail || ""}`.toLowerCase();
  if (/model|runtime|stopped|ownership/.test(text)) return "Open Models or Runtime, confirm the model is running, and remove or reclaim stale runtime ownership before retrying.";
  if (/tool|mcp/.test(text)) return "Switch to chat-only mode or reconnect the unavailable tool provider, then retry the task.";
  if (/docker|wsl|container/.test(text)) return "Start Docker Desktop and WSL, then rerun diagnostics and confirm the runtime service is reachable.";
  if (/workspace|permission|denied|access/.test(text)) return "Verify workspace membership and approval permissions, then retry the workspace action.";
  if (check.status === "fail") return "Review the detail above, correct the reported dependency or permission, and rerun diagnostics.";
  if (check.status === "warn") return "Review the detail above and follow the suggested operator action before retrying.";
  return "";
}
