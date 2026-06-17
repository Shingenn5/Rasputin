import React, { useState } from "react";
import { Card, Button, Row, Col, Spinner, Alert } from "react-bootstrap";
import { ActivitySquare, HeartPulse, Terminal, AlertCircle, CheckCircle2 } from "lucide-react";

export function DiagnosticsSettings() {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);

  const runDiagnostics = () => {
    setRunning(true);
    setResults(null);
    // Simulate a diagnostic run
    setTimeout(() => {
      setResults({
        api: "healthy",
        relay: "connected",
        database: "healthy",
        docker: "unreachable",
        disk: "warning"
      });
      setRunning(false);
    }, 2000);
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

      {results && (
        <Row className="g-3 animate-fade-in">
          <Col md={12}>
            <h6 className="fw-bold mb-3 text-uppercase tracking-wide text-muted">Diagnostic Results</h6>
          </Col>
          <Col md={6}>
            <Alert variant="success" className="d-flex align-items-center m-0">
              <CheckCircle2 className="me-3" size={24} />
              <div>
                <strong>Core API</strong><br/>
                <span className="small">Responding normally (12ms)</span>
              </div>
            </Alert>
          </Col>
          <Col md={6}>
            <Alert variant="success" className="d-flex align-items-center m-0">
              <CheckCircle2 className="me-3" size={24} />
              <div>
                <strong>Relay Connection</strong><br/>
                <span className="small">Authenticated via WebSocket</span>
              </div>
            </Alert>
          </Col>
          <Col md={6}>
            <Alert variant="danger" className="d-flex align-items-center m-0">
              <AlertCircle className="me-3" size={24} />
              <div>
                <strong>Docker Daemon</strong><br/>
                <span className="small">Cannot connect to docker.sock. WarSat will fail to deploy.</span>
              </div>
            </Alert>
          </Col>
          <Col md={6}>
            <Alert variant="warning" className="d-flex align-items-center m-0 text-dark">
              <Terminal className="me-3" size={24} />
              <div>
                <strong>Disk Space</strong><br/>
                <span className="small">Only 4GB remaining on model partition.</span>
              </div>
            </Alert>
          </Col>
        </Row>
      )}
    </section>
  );
}
