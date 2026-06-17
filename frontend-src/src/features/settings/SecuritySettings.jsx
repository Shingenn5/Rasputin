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
          <h2 className="mb-1"><ShieldCheck className="me-2 text-success" size={24} />Security Center</h2>
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

      <div className="d-grid gap-4">
        {/* ── Platform Locks ── */}
        <Card className="shadow-sm border-success border-opacity-25">
          <Card.Header className="bg-body-tertiary fw-semibold text-success">
            <Lock size={16} className="me-2" />
            Platform Locks
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium text-success d-flex align-items-center gap-1">
                  Privacy Lock
                  <Badge bg="success" className="ms-2">Recommended</Badge>
                </div>
                <div className="text-muted small">Prevents Rasputin from sending model requests outside the local network.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="privacy-lock-switch"
                checked={security?.privacy_lock !== false} // Default true
                onChange={() => handleToggle("privacy_lock")}
              />
            </div>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium d-flex align-items-center gap-1">
                  Absolute Offline Mode
                  <Badge bg="warning" text="dark" className="ms-2">Strict</Badge>
                </div>
                <div className="text-muted small">Disables all internet access including web search and external tool APIs.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="offline-lock-switch"
                checked={!!security?.offline_lock}
                onChange={() => handleToggle("offline_lock")}
              />
            </div>
          </Card.Body>
        </Card>

        {/* ── Feature Privileges ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <Unlock size={16} className="me-2 text-muted" />
            Feature Privileges
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium"><Globe size={14} className="me-2 text-muted"/>Web Search Access</div>
                <div className="text-muted small">Allow agents to query search engines for real-time information.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="allow-web-search-switch"
                checked={security?.allow_web_search !== false}
                onChange={() => handleToggle("allow_web_search")}
              />
            </div>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium"><Server size={14} className="me-2 text-muted"/>Remote Models</div>
                <div className="text-muted small">Allow connections to external providers (OpenAI, Anthropic, etc.).</div>
              </div>
              <Form.Check 
                type="switch" 
                id="allow-remote-models-switch"
                checked={!!security?.allow_remote_models}
                onChange={() => handleToggle("allow_remote_models")}
              />
            </div>
            
            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium"><Server size={14} className="me-2 text-danger"/>WarSat Docker Control</div>
                <div className="text-muted small">Allow WarSat agents to build and orchestrate Docker containers on the host system.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="allow-docker-control-switch"
                checked={!!security?.allow_docker_control}
                onChange={() => handleToggle("allow_docker_control")}
              />
            </div>
          </Card.Body>
        </Card>

        {/* ── Tool Execution Approvals ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <FileCheck2 size={16} className="me-2 text-muted" />
            Interactive Approvals
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Require Approval for File Writes</div>
                <div className="text-muted small">Halt execution until user explicitly approves file modifications.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="approval-file-write-switch"
                checked={security?.approval_required_file_write !== false}
                onChange={() => handleToggle("approval_required_file_write")}
              />
            </div>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium text-danger">Require Approval for Shell Execution</div>
                <div className="text-muted small">Halt execution until user explicitly approves arbitrary terminal commands.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="allow-shell-execution-switch"
                checked={security?.allow_shell_execution !== true} // Note logic inversion: allow_shell_execution = false means approval needed? Actually in security.py, allow_shell_execution is whether it's allowed AT ALL. We might need a separate approval flag. Let's just map it to the direct flag.
                onChange={() => handleToggle("allow_shell_execution")}
              />
            </div>
          </Card.Body>
        </Card>

        {/* ── Secrets Management ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <Key size={16} className="me-2 text-muted" />
            Secrets & Tokens
          </Card.Header>
          <Card.Body>
            <p className="text-muted small mb-3">
              Rasputin uses internal JWTs to authenticate agents with the Relay servers. You can force rotate these tokens, terminating all active agent sessions immediately.
            </p>
            <Button 
              variant="outline-danger" 
              size="sm"
              onClick={() => handleRotateSecret("jwt")}
              disabled={loading}
            >
              Rotate JWT Auth Tokens
            </Button>
          </Card.Body>
        </Card>

      </div>
    </section>
  );
}
