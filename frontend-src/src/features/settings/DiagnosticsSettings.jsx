import React, { useState } from "react";
import { Card, Button, Row, Col, Spinner, Alert } from "react-bootstrap";
import { ActivitySquare, HeartPulse, Terminal, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "../../api/client.js";

export function DiagnosticsSettings() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

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
