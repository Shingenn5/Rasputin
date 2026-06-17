import React, { useState } from "react";
import { Card, Form, Row, Col, Spinner, ProgressBar } from "react-bootstrap";
import { Server, Cpu, HardDrive, Zap, RefreshCw } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function ResourceSettings() {
  const resources = useSettingsStore(state => state.resources);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.resources);

  const [cpuLimit, setCpuLimit] = useState(resources?.cpuLimit || 80);
  const [ramLimit, setRamLimit] = useState(resources?.ramLimit || 16);

  const handleBlur = (key, localVal, defaultVal) => {
    const val = parseInt(localVal, 10);
    if (isNaN(val)) {
      updateSetting("resources", key, defaultVal);
    } else {
      updateSetting("resources", key, val);
    }
  };

  const handleToggle = (key) => {
    const newVal = !(resources?.[key]);
    updateSetting("resources", key, newVal);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Server className="me-2 text-danger" size={28} />Resource Governance</h2>
          <p className="text-body-secondary mb-0">Control how Rasputin agents and models consume system resources.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Hardware Limits */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-body-tertiary">
            <Card.Header className="bg-transparent border-0 pt-4 px-4 fw-semibold d-flex align-items-center">
              <Cpu size={20} className="me-2 text-danger" />
              Compute Limits
            </Card.Header>
            <Card.Body className="px-4 pb-4">
              <Form.Group as={Row} className="align-items-center mb-4">
                <Form.Label column sm={3} className="fw-medium text-muted">CPU Allocation Limit (%)</Form.Label>
                <Col sm={7}>
                  <Form.Range 
                    value={cpuLimit} 
                    onChange={(e) => setCpuLimit(e.target.value)} 
                    onMouseUp={() => handleBlur("cpuLimit", cpuLimit, 80)}
                  />
                </Col>
                <Col sm={2} className="text-end fw-bold">{cpuLimit}%</Col>
              </Form.Group>
              
              <Form.Group as={Row} className="align-items-center">
                <Form.Label column sm={3} className="fw-medium text-muted">RAM Allocation (GB)</Form.Label>
                <Col sm={7}>
                  <Form.Control 
                    type="number" 
                    value={ramLimit}
                    onChange={(e) => setRamLimit(e.target.value)}
                    onBlur={() => handleBlur("ramLimit", ramLimit, 16)}
                  />
                </Col>
                <Col sm={2} className="text-end fw-bold">{ramLimit} GB</Col>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* Acceleration */}
        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <Zap size={18} className="me-2 text-warning" />
              Hardware Acceleration
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <div className="fw-medium">Enable GPU Acceleration</div>
                  <div className="text-muted small">Allow models to offload layers to the GPU.</div>
                </div>
                <Form.Check 
                  type="switch" 
                  id="gpu-switch"
                  checked={resources?.enableGpu !== false}
                  onChange={() => handleToggle("enableGpu")}
                />
              </div>
              <div className="d-flex justify-content-between align-items-center">
                <div>
                  <div className="fw-medium">Force CPU Fallback</div>
                  <div className="text-muted small">Automatically fall back to CPU if VRAM is exceeded.</div>
                </div>
                <Form.Check 
                  type="switch" 
                  id="cpu-fallback-switch"
                  checked={!!resources?.cpuFallback}
                  onChange={() => handleToggle("cpuFallback")}
                />
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Disk Quotas */}
        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <HardDrive size={18} className="me-2 text-info" />
              Disk Quotas
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium">Model Cache Retention</div>
                <Form.Select 
                  size="sm" 
                  className="w-auto"
                  value={resources?.cacheRetention || "30"}
                  onChange={(e) => handleBlur("cacheRetention", e.target.value, 30)}
                >
                  <option value="7">7 Days</option>
                  <option value="30">30 Days</option>
                  <option value="90">90 Days</option>
                  <option value="never">Never Delete</option>
                </Form.Select>
              </div>
              
              <div className="bg-body-tertiary p-3 rounded mt-4">
                <div className="d-flex justify-content-between text-muted small mb-1">
                  <span>Current Disk Usage</span>
                  <span>42 GB / 500 GB</span>
                </div>
                <ProgressBar variant="info" now={8.4} className="mb-2" style={{ height: "6px" }} />
                <button className="btn btn-outline-danger btn-sm w-100"><RefreshCw size={14} className="me-2"/>Clear Cache</button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
