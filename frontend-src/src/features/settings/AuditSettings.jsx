import React from "react";
import { Card, Form, Row, Col, Spinner, Table, Badge } from "react-bootstrap";
import { FileText, ShieldAlert, Clock, Database, History } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function AuditSettings() {
  const audit = useSettingsStore(state => state.audit);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.audit);

  const handleToggle = (key) => {
    const newVal = !(audit?.[key]);
    updateSetting("audit", key, newVal);
  };

  const handleSelect = (key, val) => {
    updateSetting("audit", key, val);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><FileText className="me-2 text-dark" size={28} />Audit & Compliance</h2>
          <p className="text-body-secondary mb-0">Manage telemetry retention, logging strictness, and compliance records.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Retention Policy */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-body-tertiary">
            <Card.Header className="bg-transparent border-0 pt-4 px-4 fw-semibold d-flex align-items-center">
              <Clock size={20} className="me-2 text-primary" />
              Retention Policy
            </Card.Header>
            <Card.Body className="px-4 pb-4">
              <Form.Group as={Row} className="align-items-center mb-4">
                <Form.Label column sm={3} className="fw-medium text-muted">Telemetry History</Form.Label>
                <Col sm={9}>
                  <Form.Select 
                    value={audit?.telemetryRetention || "30"}
                    onChange={(e) => handleSelect("telemetryRetention", e.target.value)}
                  >
                    <option value="7">Keep for 7 Days</option>
                    <option value="30">Keep for 30 Days (Default)</option>
                    <option value="90">Keep for 90 Days</option>
                    <option value="forever">Keep Indefinitely (Not Recommended)</option>
                  </Form.Select>
                </Col>
              </Form.Group>
              
              <Form.Group as={Row} className="align-items-center">
                <Form.Label column sm={3} className="fw-medium text-muted">Mission Artifacts</Form.Label>
                <Col sm={9}>
                  <Form.Select 
                    value={audit?.artifactRetention || "forever"}
                    onChange={(e) => handleSelect("artifactRetention", e.target.value)}
                  >
                    <option value="30">Delete after 30 Days</option>
                    <option value="90">Delete after 90 Days</option>
                    <option value="forever">Keep Indefinitely</option>
                  </Form.Select>
                </Col>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* Audit Matrices */}
        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <Database size={18} className="me-2 text-warning" />
              Data Collection
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <div className="fw-medium">Log Full Prompts & Responses</div>
                  <div className="text-muted small">Required for debugging, uses more disk space.</div>
                </div>
                <Form.Check type="switch" id="log-prompts" checked={audit?.logPrompts !== false} onChange={() => handleToggle("logPrompts")} />
              </div>
              <div className="border-top pt-3"></div>
              <div className="d-flex justify-content-between align-items-center">
                <div>
                  <div className="fw-medium">Anonymize Sensitive Data</div>
                  <div className="text-muted small">Attempt to strip PII from logs before saving.</div>
                </div>
                <Form.Check type="switch" id="anonymize-logs" checked={!!audit?.anonymize} onChange={() => handleToggle("anonymize")} />
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Security Events */}
        <Col md={6}>
          <Card className="shadow-sm border-0 h-100 border-danger border-opacity-25">
            <Card.Header className="bg-danger bg-opacity-10 fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center text-danger">
              <ShieldAlert size={18} className="me-2" />
              Security Logging
            </Card.Header>
            <Card.Body className="px-4 border-top border-danger border-opacity-10">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium">Log Failed Tool Approvals</div>
                <Form.Check type="switch" id="log-failed-tools" checked={audit?.logFailedTools !== false} onChange={() => handleToggle("logFailedTools")} />
              </div>
              <div className="border-top pt-3 border-danger border-opacity-10"></div>
              <div className="d-flex justify-content-between align-items-center">
                <div className="fw-medium">Log Policy Violations</div>
                <Form.Check type="switch" id="log-policy" checked={audit?.logPolicyViolations !== false} onChange={() => handleToggle("logPolicyViolations")} />
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
