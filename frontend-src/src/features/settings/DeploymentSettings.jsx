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
          <h2 className="mb-1"><Rocket className="me-2 text-primary" size={28} />Deployment Governance</h2>
          <p className="text-body-secondary mb-0">Platform rules for how WarSat containerizes and hosts AI models.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      {/* Orchestration Target Section - Visual Cards */}
      <div className="mb-5">
        <h5 className="fw-semibold mb-3 d-flex align-items-center">
          <Box size={20} className="me-2 text-primary" />
          Primary Orchestration Provider
        </h5>
        <Row className="g-3 mb-3">
          {[
            { id: "docker", title: "Local Docker", icon: <Box size={32} />, desc: "Deploy single containers directly to the host Docker daemon." },
            { id: "compose", title: "Docker Compose", icon: <Network size={32} />, desc: "Deploy multi-container stacks via Compose files." },
            { id: "kubernetes", title: "Kubernetes", icon: <ServerCrash size={32} />, desc: "Deploy capabilities to a local or remote K8s cluster." }
          ].map(provider => (
            <Col md={4} key={provider.id}>
              <Card 
                className={`h-100 cursor-pointer transition-all ${deployments?.provider === provider.id ? 'border-primary bg-primary bg-opacity-10 shadow' : 'border-secondary border-opacity-25 opacity-75'}`}
                onClick={() => handleChange("provider", provider.id)}
                style={{ cursor: "pointer" }}
              >
                <Card.Body className="text-center p-4">
                  <div className={`mb-3 ${deployments?.provider === provider.id ? 'text-primary' : 'text-muted'}`}>
                    {provider.icon}
                  </div>
                  <h6 className="fw-bold">{provider.title}</h6>
                  <p className="small text-muted mb-0">{provider.desc}</p>
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
        
        {deployments?.provider === "kubernetes" && (
          <div className="bg-body-tertiary p-3 rounded border border-info border-opacity-50 animate-fade-in">
            <Form.Group as={Row} className="align-items-center mb-0">
              <Form.Label column sm={3} className="fw-medium text-info">
                Kubeconfig Context
              </Form.Label>
              <Col sm={9}>
                <Form.Control 
                  type="text" 
                  value={deployments?.kubeContext || "default"}
                  onChange={(e) => handleChange("kubeContext", e.target.value)}
                  placeholder="e.g. minikube, docker-desktop"
                />
              </Col>
            </Form.Group>
          </div>
        )}
      </div>

      <Row className="g-4">
        {/* Container Policies */}
        <Col md={6}>
          <Card className="shadow-sm h-100 border-0 bg-body-tertiary">
            <Card.Body>
              <h6 className="fw-semibold mb-4 d-flex align-items-center">
                <Network size={18} className="me-2 text-warning" />
                Container Sandbox Policies
              </h6>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Network Mode</Form.Label>
                <Form.Select 
                  className="fs-6"
                  value={deployments?.networkMode || "bridge"}
                  onChange={(e) => handleChange("networkMode", e.target.value)}
                >
                  <option value="bridge">Bridge (Default Isolation)</option>
                  <option value="host">Host Network (High Performance)</option>
                  <option value="none">Air-Gapped (No external internet)</option>
                </Form.Select>
              </Form.Group>

              <div className="bg-body p-3 rounded border">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div className="fw-medium">Auto-Restart (Always)</div>
                  <Form.Check 
                    type="switch" 
                    id="restart-policy-switch"
                    checked={!!deployments?.autoRestart}
                    onChange={() => handleToggle("autoRestart")}
                  />
                </div>
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <span className="fw-medium">Auto-Prune Orphans</span>
                  </div>
                  <Form.Check 
                    type="switch" 
                    id="auto-prune-switch"
                    checked={deployments?.autoPrune !== false}
                    onChange={() => handleToggle("autoPrune")}
                  />
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Registry & Sourcing */}
        <Col md={6}>
          <Card className="shadow-sm h-100 border-0 bg-body-tertiary">
            <Card.Body>
              <h6 className="fw-semibold mb-4 d-flex align-items-center">
                <KeySquare size={18} className="me-2 text-info" />
                Image Registry Sourcing
              </h6>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Base Image Registry URL</Form.Label>
                <Form.Control 
                  type="text" 
                  className="fs-6 font-monospace"
                  value={registryUrl}
                  onChange={(e) => setRegistryUrl(e.target.value)}
                  onBlur={() => handleChange("registryUrl", registryUrl)}
                  placeholder="docker.io"
                />
                <Form.Text className="text-muted">Where WarSat pulls foundational runtime images from.</Form.Text>
              </Form.Group>
              
              <Card className="border-warning border-opacity-50 bg-warning bg-opacity-10 shadow-none">
                <Card.Body className="py-3">
                  <div className="d-flex justify-content-between align-items-center">
                    <div>
                      <div className="fw-bold text-warning text-darken">Force Image Pulls</div>
                      <div className="text-muted small">Skip local cache, always fetch manifest.</div>
                    </div>
                    <Form.Check 
                      type="switch" 
                      id="force-pull-switch"
                      className="fs-5"
                      checked={!!deployments?.forcePull}
                      onChange={() => handleToggle("forcePull")}
                    />
                  </div>
                </Card.Body>
              </Card>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
