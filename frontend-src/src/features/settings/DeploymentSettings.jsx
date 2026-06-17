import React, { useState } from "react";
import { Card, Form, Row, Col, Badge, Spinner } from "react-bootstrap";
import { Rocket, Box, Network, ServerCrash, KeySquare } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function DeploymentSettings() {
  const deployments = useSettingsStore(state => state.deployments);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.deployments);

  const [registryUrl, setRegistryUrl] = useState(deployments?.registryUrl || "");

  const handleToggle = (key) => {
    const newVal = !(deployments?.[key]);
    updateSetting("deployments", key, newVal);
  };

  const handleChange = (key, val) => {
    updateSetting("deployments", key, val);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Rocket className="me-2 text-primary" size={24} />Deployment Governance</h2>
          <p className="text-body-secondary mb-0">Platform rules for how WarSat containerizes and hosts AI models.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <div className="d-grid gap-4">
        {/* ── Orchestration Target ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <Box size={16} className="me-2 text-muted" />
            Orchestration Target
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <Form.Group as={Row} className="align-items-center">
              <Form.Label column sm={4} className="fw-medium">
                Default Provider
                <div className="text-muted small fw-normal">The engine WarSat will use to spin up capabilities.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Select 
                  value={deployments?.provider || "docker"}
                  onChange={(e) => handleChange("provider", e.target.value)}
                >
                  <option value="docker">Local Docker</option>
                  <option value="compose">Docker Compose (Multi-container)</option>
                  <option value="kubernetes">Kubernetes (Remote/K3s)</option>
                </Form.Select>
              </Col>
            </Form.Group>
            
            {deployments?.provider === "kubernetes" && (
              <>
                <div className="border-top pt-3"></div>
                <Form.Group as={Row} className="align-items-center">
                  <Form.Label column sm={4} className="fw-medium">
                    Kubeconfig Context
                  </Form.Label>
                  <Col sm={8}>
                    <Form.Control 
                      type="text" 
                      value={deployments?.kubeContext || "default"}
                      onChange={(e) => handleChange("kubeContext", e.target.value)}
                      placeholder="e.g. minikube"
                    />
                  </Col>
                </Form.Group>
              </>
            )}
          </Card.Body>
        </Card>

        {/* ── Container Policies ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <Network size={16} className="me-2 text-muted" />
            Container Policies
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <Form.Group as={Row} className="align-items-center">
              <Form.Label column sm={4} className="fw-medium">
                Network Mode
                <div className="text-muted small fw-normal">Isolation level for deployed containers.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Select 
                  value={deployments?.networkMode || "bridge"}
                  onChange={(e) => handleChange("networkMode", e.target.value)}
                >
                  <option value="bridge">Bridge (Default)</option>
                  <option value="host">Host Network (High Performance)</option>
                  <option value="none">Isolated (No external internet)</option>
                </Form.Select>
              </Col>
            </Form.Group>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Restart Automatically</div>
                <div className="text-muted small">Restart containers if they crash or the host machine reboots.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="restart-policy-switch"
                checked={!!deployments?.autoRestart}
                onChange={() => handleToggle("autoRestart")}
              />
            </div>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Auto-Prune Orphaned Containers</div>
                <div className="text-muted small">Destroy containers whose parent mission has been completely archived or deleted.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="auto-prune-switch"
                checked={deployments?.autoPrune !== false} // default true
                onChange={() => handleToggle("autoPrune")}
              />
            </div>
          </Card.Body>
        </Card>

        {/* ── Container Registries ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <KeySquare size={16} className="me-2 text-muted" />
            Registry Settings
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <Form.Group as={Row} className="align-items-center">
              <Form.Label column sm={4} className="fw-medium">
                Base Image Registry
                <div className="text-muted small fw-normal">Where WarSat pulls Llama.cpp or vLLM base images from.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Control 
                  type="text" 
                  value={registryUrl}
                  onChange={(e) => setRegistryUrl(e.target.value)}
                  onBlur={() => handleChange("registryUrl", registryUrl)}
                  placeholder="docker.io"
                />
              </Col>
            </Form.Group>
            
            <div className="d-flex justify-content-between align-items-center mt-2">
              <div>
                <div className="fw-medium text-warning">Force Image Pulls</div>
                <div className="text-muted small">Always contact the registry for the latest layer hashes, skipping local cache.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="force-pull-switch"
                checked={!!deployments?.forcePull}
                onChange={() => handleToggle("forcePull")}
              />
            </div>
          </Card.Body>
        </Card>

      </div>
    </section>
  );
}
