import React, { useState } from "react";
import { Card, Form, Row, Col, Spinner, Badge, Button, InputGroup } from "react-bootstrap";
import { Plug, Database, Github, GitBranch, RefreshCw, CheckCircle2 } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function IntegrationSettings() {
  const integrations = useSettingsStore(state => state.integrations);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.integrations);

  const [githubToken, setGithubToken] = useState(integrations?.githubToken || "");
  const [hfToken, setHfToken] = useState(integrations?.hfToken || "");

  const handleToggle = (key) => {
    const newVal = !(integrations?.[key]);
    updateSetting("integrations", key, newVal);
  };

  const handleChange = (key, val) => {
    updateSetting("integrations", key, val);
  };

  const testConnection = (target) => {
    // This would ideally call a specific test action in settingsActions.js
    console.log(`Testing connection for ${target}`);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Plug className="me-2 text-warning" size={28} />Integration Center</h2>
          <p className="text-body-secondary mb-0">Manage external systems, remote registries, and source control.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* HuggingFace Hub */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <Database size={18} className="me-2 text-warning" />
              HuggingFace Hub
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <p className="small text-muted mb-4">
                Authenticate with HuggingFace to download gated models and private repositories.
              </p>
              <Form.Group className="mb-3">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Access Token</Form.Label>
                <InputGroup>
                  <Form.Control 
                    type="password" 
                    value={hfToken}
                    onChange={(e) => setHfToken(e.target.value)}
                    onBlur={() => handleChange("hfToken", hfToken)}
                    placeholder="hf_..."
                  />
                  <Button variant="outline-secondary" onClick={() => testConnection('hf')}>
                    <RefreshCw size={16} className="me-2" />Test
                  </Button>
                </InputGroup>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* GitHub / Version Control */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <Github size={18} className="me-2 text-dark" />
              Source Control (GitHub)
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <p className="small text-muted mb-4">
                Connect Rasputin to GitHub to allow agents to automatically clone, branch, and PR against repositories.
              </p>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Personal Access Token</Form.Label>
                <InputGroup>
                  <Form.Control 
                    type="password" 
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    onBlur={() => handleChange("githubToken", githubToken)}
                    placeholder="ghp_..."
                  />
                  <Button variant="outline-secondary" onClick={() => testConnection('github')}>
                    <RefreshCw size={16} className="me-2" />Test
                  </Button>
                </InputGroup>
              </Form.Group>

              <div className="bg-body-tertiary p-3 rounded border">
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <div className="fw-medium d-flex align-items-center">
                      <GitBranch size={16} className="me-2 text-primary" />
                      Auto-Branching
                    </div>
                    <div className="text-muted small ms-4">Agents will automatically create a new branch before modifying code.</div>
                  </div>
                  <Form.Check 
                    type="switch" 
                    id="auto-branch-switch"
                    checked={integrations?.autoBranch !== false}
                    onChange={() => handleToggle("autoBranch")}
                  />
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
