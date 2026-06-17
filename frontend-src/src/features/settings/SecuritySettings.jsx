import React, { useState, useEffect } from "react";
import { Card, Form, Row, Col, Badge, Spinner, Button } from "react-bootstrap";
import { ShieldCheck, Lock, Unlock, Key, FileCheck2, Globe, Server, AlertTriangle } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting, rotateSecrets } from "./settingsActions.js";

export function SecuritySettings() {
  const security = useSettingsStore(state => state.security);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.security);

  const handleToggle = (key) => {
    const newVal = !(security?.[key]);
    updateSetting("security", key, newVal);
  };

  const handleRotateSecret = (type) => {
    rotateSecrets(type);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><ShieldCheck className="me-2 text-success" size={28} />Security Center</h2>
          <p className="text-body-secondary mb-0">Manage authentication, platform locks, and tool execution privileges.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger d-flex align-items-center mb-4">
          <AlertTriangle className="me-2" size={18} />
          {error}
        </div>
      )}

      {/* Hero Security Banner */}
      <Card className={`shadow-sm mb-4 border-0 text-white ${security?.offline_lock ? 'bg-danger' : security?.privacy_lock !== false ? 'bg-success' : 'bg-warning'}`}>
        <Card.Body className="d-flex align-items-center justify-content-between py-4 px-4">
          <div className="d-flex align-items-center">
            {security?.offline_lock ? <Lock size={48} className="me-4 opacity-75" /> : <ShieldCheck size={48} className="me-4 opacity-75" />}
            <div>
              <h4 className="mb-1 fw-bold text-white">
                {security?.offline_lock ? "Absolute Offline Mode" : security?.privacy_lock !== false ? "Privacy Lock Active" : "Network Unlocked"}
              </h4>
              <p className="mb-0 opacity-75 text-white">
                {security?.offline_lock 
                  ? "All internet access is blocked. Rasputin is completely isolated." 
                  : security?.privacy_lock !== false 
                    ? "Rasputin will not send requests outside the local network." 
                    : "Rasputin is allowed to communicate with external endpoints."}
              </p>
            </div>
          </div>
          <div className="d-flex flex-column gap-2 text-end">
            <Form.Check 
              type="switch" 
              id="privacy-lock-switch"
              className="fs-5"
              label={<span className="text-white ms-2">Privacy Lock</span>}
              checked={security?.privacy_lock !== false}
              onChange={() => handleToggle("privacy_lock")}
            />
            <Form.Check 
              type="switch" 
              id="offline-lock-switch"
              className="fs-5"
              label={<span className="text-white ms-2">Offline Mode</span>}
              checked={!!security?.offline_lock}
              onChange={() => handleToggle("offline_lock")}
            />
          </div>
        </Card.Body>
      </Card>

      <Row className="g-4 mb-4">
        {/* Privilege Matrix (Table) */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold border-bottom-0 pt-3 px-4">
              <Unlock size={18} className="me-2 text-muted" />
              Privilege & Approval Matrix
            </Card.Header>
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0 border-top">
                <thead className="table-light text-muted small text-uppercase">
                  <tr>
                    <th className="ps-4">Capability</th>
                    <th>Status</th>
                    <th className="text-end pe-4">Action</th>
                  </tr>
                </thead>
                <tbody className="border-top-0">
                  <tr>
                    <td className="ps-4">
                      <div className="fw-medium"><Globe size={16} className="me-2 text-primary"/>Web Search</div>
                      <div className="text-muted small">Allow agents to query search engines.</div>
                    </td>
                    <td>
                      {security?.allow_web_search !== false ? <Badge bg="success">Allowed</Badge> : <Badge bg="secondary">Blocked</Badge>}
                    </td>
                    <td className="text-end pe-4">
                      <Form.Check type="switch" id="allow-web-search" checked={security?.allow_web_search !== false} onChange={() => handleToggle("allow_web_search")} />
                    </td>
                  </tr>
                  <tr>
                    <td className="ps-4">
                      <div className="fw-medium"><Server size={16} className="me-2 text-info"/>Remote Models</div>
                      <div className="text-muted small">Connect to external APIs (OpenAI, Anthropic).</div>
                    </td>
                    <td>
                      {security?.allow_remote_models ? <Badge bg="success">Allowed</Badge> : <Badge bg="secondary">Blocked</Badge>}
                    </td>
                    <td className="text-end pe-4">
                      <Form.Check type="switch" id="allow-remote-models" checked={!!security?.allow_remote_models} onChange={() => handleToggle("allow_remote_models")} />
                    </td>
                  </tr>
                  <tr>
                    <td className="ps-4">
                      <div className="fw-medium"><Box size={16} className="me-2 text-danger"/>WarSat Docker Control</div>
                      <div className="text-muted small">Allow WarSat to manage host containers.</div>
                    </td>
                    <td>
                      {security?.allow_docker_control ? <Badge bg="danger">Allowed</Badge> : <Badge bg="secondary">Blocked</Badge>}
                    </td>
                    <td className="text-end pe-4">
                      <Form.Check type="switch" id="allow-docker-control" checked={!!security?.allow_docker_control} onChange={() => handleToggle("allow_docker_control")} />
                    </td>
                  </tr>
                  <tr>
                    <td className="ps-4">
                      <div className="fw-medium"><FileCheck2 size={16} className="me-2 text-warning"/>File Modifications</div>
                      <div className="text-muted small">Require user approval before saving files.</div>
                    </td>
                    <td>
                      {security?.approval_required_file_write !== false ? <Badge bg="warning" text="dark">Approval Req.</Badge> : <Badge bg="success">Auto-Approve</Badge>}
                    </td>
                    <td className="text-end pe-4">
                      <Form.Check type="switch" id="approval-file-write" checked={security?.approval_required_file_write !== false} onChange={() => handleToggle("approval_required_file_write")} />
                    </td>
                  </tr>
                  <tr>
                    <td className="ps-4">
                      <div className="fw-medium"><AlertTriangle size={16} className="me-2 text-danger"/>Shell Execution</div>
                      <div className="text-muted small">Allow agents to execute terminal commands.</div>
                    </td>
                    <td>
                      {security?.allow_shell_execution ? <Badge bg="warning" text="dark">Approval Req.</Badge> : <Badge bg="secondary">Blocked</Badge>}
                    </td>
                    <td className="text-end pe-4">
                      <Form.Check type="switch" id="allow-shell-execution" checked={!!security?.allow_shell_execution} onChange={() => handleToggle("allow_shell_execution")} />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Danger Zone */}
      <Card className="shadow-sm border-danger border-opacity-50">
        <Card.Header className="bg-danger bg-opacity-10 text-danger fw-bold py-3">
          <Key size={18} className="me-2" />
          Danger Zone: Secrets & Tokens
        </Card.Header>
        <Card.Body className="d-flex justify-content-between align-items-center">
          <div>
            <h6 className="fw-bold mb-1">Rotate Internal JWTs</h6>
            <p className="text-muted small mb-0">
              Immediately invalidate all active agent sessions and force re-authentication. Use this if you suspect a compromised relay.
            </p>
          </div>
          <Button 
            variant="danger" 
            className="fw-semibold px-4"
            onClick={() => handleRotateSecret("jwt")}
            disabled={loading}
          >
            Rotate Tokens
          </Button>
        </Card.Body>
      </Card>
    </section>
  );
}
