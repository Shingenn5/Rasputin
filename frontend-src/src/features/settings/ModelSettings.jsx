import React, { useEffect, useState } from "react";
import { Card, Form, Row, Col, Spinner, Badge } from "react-bootstrap";
import { BrainCircuit, Download, Cpu, Gauge, HardDrive, Layers3, SlidersHorizontal, Zap } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

const PERFORMANCE_OPTIONS = [
  ["responsive", "Responsive", "Prioritize interactive speed and lower latency."],
  ["balanced", "Balanced", "Choose a practical quality and speed tradeoff."],
  ["maximum_quality", "Maximum quality", "Prefer the largest capable model and context."],
];

const CONTEXT_OPTIONS = [
  ["automatic", "Automatic", "Let the selected runtime fit context to available memory."],
  ["4096", "4K tokens", "A reliable interactive ceiling for local models."],
  ["8192", "8K tokens", "More room for code and longer conversations."],
  ["16384", "16K tokens", "Use when the selected deployment has headroom."],
  ["32768", "32K tokens", "Use only when the deployment explicitly supports it."],
];

const FALLBACK_OPTIONS = [
  ["ask", "Ask before fallback", "Show the proposed model or runtime change and wait for confirmation."],
  ["single_gpu", "Single-GPU fallback", "Prefer one GPU when a model fits without sharding."],
  ["fail", "Block on mismatch", "Stop and explain the incompatibility instead of switching."],
];

export function ModelSettings({ models: availableModels, modeModelOverrides, setModeModelOverride }) {
  const modelSettings = useSettingsStore(state => state.models);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.models);

  const [downloadPath, setDownloadPath] = useState(modelSettings?.downloadPath || "");
  // Settings load async after mount — sync the local input when they arrive.
  useEffect(() => {
    setDownloadPath(modelSettings?.downloadPath || "");
  }, [modelSettings?.downloadPath]);

  const handleToggle = (key) => {
    const newVal = !(modelSettings?.[key]);
    updateSetting("models", key, newVal);
  };

  const handleChange = (key, val) => {
    updateSetting("models", key, val);
  };

  const selectionMode = modelSettings?.selectionMode || "automatic";
  const performancePreference = modelSettings?.performancePreference || "balanced";
  const maxContextTokens = String(modelSettings?.maxContextTokens ?? "automatic");
  const fallbackBehavior = modelSettings?.fallbackBehavior || "ask";
  const defaultEngine = modelSettings?.defaultEngine || "llamacpp";

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><BrainCircuit className="me-2 text-primary" size={28} />Model Governance</h2>
          <p className="text-body-secondary mb-0">Choose the outcome you want; Rasputin coordinates the runnable deployment.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Essentials */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-body-tertiary" data-testid="model-governance-essentials">
            <Card.Body className="p-4">
              <div className="d-flex justify-content-between align-items-start gap-3 mb-3">
                <div>
                  <h5 className="fw-semibold d-flex align-items-center mb-1">
                    <Gauge size={20} className="me-2 text-primary" />
                    Automatic model governance
                  </h5>
                  <p className="text-body-secondary mb-0">
                    Rasputin selects the model, weights, inference engine, context, and GPU placement as one compatible deployment.
                  </p>
                </div>
                <Badge bg={selectionMode === "automatic" ? "success" : "secondary"}>
                  {selectionMode === "automatic" ? "Automatic" : "Manual override"}
                </Badge>
              </div>

              <div className="alert alert-info py-2 mb-4">
                <Zap size={16} className="me-2" />
                Automatic selection uses your performance preference and measured hardware fit. Manual engine choices remain available below for troubleshooting.
              </div>

              <Row className="g-3">
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="fw-medium" htmlFor="model-selection-mode">Selection strategy</Form.Label>
                    <Form.Select id="model-selection-mode" data-testid="model-selection-mode" value={selectionMode} onChange={(event) => handleChange("selectionMode", event.target.value)}>
                      <option value="automatic">Automatic (recommended)</option>
                      <option value="manual">Manual engine override</option>
                    </Form.Select>
                    <Form.Text className="text-body-secondary">Automatic is the safe default for mixed hardware and changing model formats.</Form.Text>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="fw-medium" htmlFor="model-performance-preference">Performance preference</Form.Label>
                    <Form.Select id="model-performance-preference" data-testid="model-performance-preference" value={performancePreference} onChange={(event) => handleChange("performancePreference", event.target.value)}>
                      {PERFORMANCE_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </Form.Select>
                    <Form.Text className="text-body-secondary">{PERFORMANCE_OPTIONS.find(([value]) => value === performancePreference)?.[2]}</Form.Text>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="fw-medium" htmlFor="model-max-context">Maximum context</Form.Label>
                    <Form.Select id="model-max-context" data-testid="model-max-context" value={maxContextTokens} onChange={(event) => handleChange("maxContextTokens", event.target.value)}>
                      {CONTEXT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </Form.Select>
                    <Form.Text className="text-body-secondary">{CONTEXT_OPTIONS.find(([value]) => value === maxContextTokens)?.[2]}</Form.Text>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="fw-medium" htmlFor="model-fallback-behavior">When the preferred deployment is unavailable</Form.Label>
                    <Form.Select id="model-fallback-behavior" data-testid="model-fallback-behavior" value={fallbackBehavior} onChange={(event) => handleChange("fallbackBehavior", event.target.value)}>
                      {FALLBACK_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </Form.Select>
                    <Form.Text className="text-body-secondary">{FALLBACK_OPTIONS.find(([value]) => value === fallbackBehavior)?.[2]}</Form.Text>
                  </Form.Group>
                </Col>
              </Row>

              <div className="border-top mt-4 pt-3">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <div className="fw-medium d-flex align-items-center"><Layers3 size={16} className="me-2 text-primary" />Allow multi-GPU placement</div>
                    <div className="text-body-secondary small">Permit larger models to span GPUs when a single card cannot fit them.</div>
                  </div>
                  <Form.Check type="switch" id="model-multi-gpu-switch" data-testid="model-multi-gpu-switch" checked={!!modelSettings?.allowMultiGpu} onChange={() => handleToggle("allowMultiGpu")} aria-label="Allow multi-GPU placement" />
                </div>
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <div className="fw-medium d-flex align-items-center"><Gauge size={16} className="me-2 text-success" />Automatic benchmarking</div>
                    <div className="text-body-secondary small">Use measured local performance to rank compatible model and runtime profiles.</div>
                  </div>
                  <Form.Check type="switch" id="model-auto-benchmark-switch" data-testid="model-auto-benchmark-switch" checked={modelSettings?.automaticBenchmarking !== false} onChange={() => handleToggle("automaticBenchmarking")} aria-label="Automatic benchmarking" />
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        <Col md={12}>
          <details className="border rounded p-3" data-testid="model-advanced-disclosure">
            <summary className="fw-semibold d-flex align-items-center gap-2">
              <SlidersHorizontal size={18} className="text-secondary" />
              Advanced model controls
              <Badge bg="secondary" className="ms-auto">Engine, routing, storage</Badge>
            </summary>
            <div className="pt-4">
              <Card className="shadow-sm border-0 mb-3">
                <Card.Body>
                  <h5 className="fw-semibold d-flex align-items-center mb-3"><Cpu size={20} className="me-2 text-primary" />Manual inference engine override</h5>
                  <p className="text-body-secondary small mb-3">This legacy setting remains readable for troubleshooting. It is not the primary choice while Selection strategy is Automatic.</p>
                  <div className="d-flex flex-wrap gap-3">
                    <Form.Check type="radio" id="engine-llamacpp" name="engine" label={<><span className="fw-bold">Llama.cpp</span> <Badge bg="secondary" className="ms-1">GGUF</Badge></>} checked={defaultEngine === "llamacpp"} onChange={() => handleChange("defaultEngine", "llamacpp")} />
                    <Form.Check type="radio" id="engine-vllm" name="engine" label={<><span className="fw-bold">vLLM</span> <Badge bg="primary" className="ms-1">High Throughput</Badge></>} checked={defaultEngine === "vllm"} onChange={() => handleChange("defaultEngine", "vllm")} />
                    <Form.Check type="radio" id="engine-ollama" name="engine" label={<span className="fw-bold">Ollama</span>} checked={defaultEngine === "ollama"} onChange={() => handleChange("defaultEngine", "ollama")} />
                  </div>
                </Card.Body>
              </Card>
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
            </div>
          </details>
        </Col>
      </Row>
    </section>
  );
}
