import React, { useState } from "react";
import { Card, Form, Row, Col, Spinner, Badge } from "react-bootstrap";
import { BrainCircuit, Download, Cpu, HardDrive } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function ModelSettings({ models: availableModels, modeModelOverrides, setModeModelOverride }) {
  const modelSettings = useSettingsStore(state => state.models);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.models);

  const [downloadPath, setDownloadPath] = useState(modelSettings?.downloadPath || "");

  const handleToggle = (key) => {
    const newVal = !(modelSettings?.[key]);
    updateSetting("models", key, newVal);
  };

  const handleChange = (key, val) => {
    updateSetting("models", key, val);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><BrainCircuit className="me-2 text-primary" size={28} />Model Governance</h2>
          <p className="text-body-secondary mb-0">Control AI infrastructure behavior, default runtimes, and download rules.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Runtime Engine */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-body-tertiary">
            <Card.Body>
              <h5 className="fw-semibold d-flex align-items-center mb-4">
                <Cpu size={20} className="me-2 text-primary" />
                Default Inference Engine
              </h5>
              
              <Form.Group as={Row} className="align-items-center">
                <Form.Label column sm={3} className="fw-medium text-muted">
                  Engine Backend
                </Form.Label>
                <Col sm={9}>
                  <div className="d-flex gap-3">
                    <Form.Check 
                      type="radio"
                      id="engine-llamacpp"
                      name="engine"
                      label={<><span className="fw-bold">Llama.cpp</span> <Badge bg="secondary" className="ms-1">GGUF</Badge></>}
                      checked={modelSettings?.defaultEngine === "llamacpp" || !modelSettings?.defaultEngine}
                      onChange={() => handleChange("defaultEngine", "llamacpp")}
                    />
                    <Form.Check 
                      type="radio"
                      id="engine-vllm"
                      name="engine"
                      label={<><span className="fw-bold">vLLM</span> <Badge bg="primary" className="ms-1">High Throughput</Badge></>}
                      checked={modelSettings?.defaultEngine === "vllm"}
                      onChange={() => handleChange("defaultEngine", "vllm")}
                    />
                    <Form.Check 
                      type="radio"
                      id="engine-ollama"
                      name="engine"
                      label={<span className="fw-bold">Ollama</span>}
                      checked={modelSettings?.defaultEngine === "ollama"}
                      onChange={() => handleChange("defaultEngine", "ollama")}
                    />
                  </div>
                </Col>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* Global Capability Routing */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0">
              <BrainCircuit size={18} className="me-2 text-muted" />
              Default Capability Routing
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <div className="text-muted small mb-4">
                Define the fallback AI models used for different types of autonomous tasks when a specific workspace doesn't have an override set.
              </div>
              <Row className="g-3">
                {[
                  { mode: 'chat', label: 'Main Chat Assistant', desc: 'Default model for conversational queries.' },
                  { mode: 'code', label: 'Default Coder', desc: 'Handles code generation and refactoring.' },
                  { mode: 'organize', label: 'Default Executor', desc: 'Runs CLI commands and manipulates files.' }
                ].map((item) => (
                  <Col md={4} key={item.mode}>
                    <Form.Group>
                      <Form.Label className="fw-medium text-body mb-1">{item.label}</Form.Label>
                      <div className="text-muted small mb-2">{item.desc}</div>
                      <Form.Select 
                        value={modeModelOverrides?.[item.mode] || ""}
                        onChange={(e) => setModeModelOverride(item.mode, e.target.value)}
                        className="form-select-sm"
                      >
                        <option value="">(Auto Detect)</option>
                        {(availableModels || []).map(m => (
                          <option key={m.key} value={m.key}>{m.name || m.key}</option>
                        ))}
                      </Form.Select>
                    </Form.Group>
                  </Col>
                ))}
              </Row>
            </Card.Body>
          </Card>
        </Col>

        {/* Acquisition & Storage */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0">
              <HardDrive size={18} className="me-2 text-muted" />
              Acquisition & Storage
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Model Storage Path</Form.Label>
                <Form.Control 
                  type="text" 
                  size="lg"
                  className="fs-6 font-monospace"
                  value={downloadPath}
                  onChange={(e) => setDownloadPath(e.target.value)}
                  onBlur={() => handleChange("downloadPath", downloadPath)}
                  placeholder="/var/rasputin/models"
                />
                <Form.Text className="text-muted">Absolute path where raw model files (GGUF, Safetensors) are saved.</Form.Text>
              </Form.Group>

              <div className="bg-body-tertiary p-3 rounded border">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <div className="fw-medium d-flex align-items-center">
                      <Download size={16} className="me-2 text-primary" />
                      Auto-Download Quantizations
                    </div>
                    <div className="text-muted small ms-4">Automatically download Q4_K_M quantizations if a specific variant isn't requested.</div>
                  </div>
                  <Form.Check 
                    type="switch" 
                    id="auto-quant-switch"
                    checked={modelSettings?.autoQuantization !== false}
                    onChange={() => handleToggle("autoQuantization")}
                  />
                </div>

                <div className="border-top pt-3 mt-3"></div>

                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <div className="fw-medium d-flex align-items-center">
                      <BrainCircuit size={16} className="me-2 text-success" />
                      Allow Unverified Sources
                    </div>
                    <div className="text-muted small ms-4">Permit downloading models from non-HuggingFace URLs.</div>
                  </div>
                  <Form.Check 
                    type="switch" 
                    id="unverified-sources-switch"
                    checked={!!modelSettings?.allowUnverifiedSources}
                    onChange={() => handleToggle("allowUnverifiedSources")}
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
