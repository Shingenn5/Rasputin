import React, { useState } from "react";
import { Card, Button, Row, Col, Spinner, Alert } from "react-bootstrap";
import { ActivitySquare, HeartPulse, Terminal, AlertCircle, CheckCircle2 } from "lucide-react";
import { api, postJson } from "../../api/client.js";

export function DiagnosticsSettings() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");
  const [recovery, setRecovery] = useState(null);
  const [recoveryBusy, setRecoveryBusy] = useState(false);

  const runDiagnostics = async () => {
    setRunning(true);
    setResults(null);
    setError("");
    try {
      setResults(await api("/api/settings/diagnostics?category=all"));
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setRunning(false);
    }
  };

  const runRecovery = async (action, body = {}) => {
    setRecoveryBusy(true);
    setError("");
    try {
      const path = action === "backup" ? "/api/recovery/backup" : action === "export" ? "/api/recovery/export" : "/api/recovery/delete-preview";
      setRecovery({ action, data: await postJson(path, body) });
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setRecoveryBusy(false);
    }
  };

  const deleteMyData = async () => {
    if (!window.confirm("Delete your Rasputin sessions, tasks, memory, and assistant records? This cannot be undone.")) return;
    setRecoveryBusy(true);
    try {
      setRecovery({ action: "delete", data: await postJson("/api/recovery/delete", { confirmation: "DELETE MY RASPUTIN DATA", dryRun: false }) });
    } catch (err) {
      setError(String(err.message || err));
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
          {recovery && (
            <Alert variant={recovery.action === "delete" ? "warning" : "info"} className="mt-3 mb-0" data-testid="recovery-result">
              <strong>{titleize(recovery.action)} result</strong>
              {recovery.data?.path && <div className="small mt-1">Artifact: <code>{recovery.data.path}</code></div>}
              {recovery.data?.fileCount !== undefined && <div className="small mt-1">{recovery.data.fileCount} file(s) included; {recovery.data.excludedCount || 0} excluded by policy.</div>}
              {recovery.data?.counts && <div className="small mt-1">Owner records: {Object.entries(recovery.data.counts).map(([key, value]) => `${key} ${value}`).join(" · ") || "none"}</div>}
              {recovery.action === "delete" && recovery.data?.dryRun && <Button variant="danger" size="sm" className="mt-2" onClick={deleteMyData}>Confirm permanent deletion</Button>}
            </Alert>
          )}
        </Card.Body>
      </Card>

      {error && <Alert variant="danger" role="alert" data-testid="diagnostic-error">{error}</Alert>}

      {results && (
        <div data-testid="diagnostic-results">
        <Row className="g-3 animate-fade-in">
          <Col md={12}>
            <Alert variant={overallVariant(results.status)} className="d-flex align-items-start m-0">
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
                  {check.nextAction && <div className="small mt-2"><strong>Next:</strong> {check.nextAction}</div>}
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
