import React, { useState, useEffect } from "react";
import { Card, Form, Row, Col, Badge, Spinner } from "react-bootstrap";
import { Monitor, Moon, Sun, ShieldAlert, BookOpen, Settings2 } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";
import { themeOptions } from "../../lib/constants.js";

export function GeneralSettings() {
  const general = useSettingsStore(state => state.general);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.general);

  // Local state for debouncing inputs
  const [workspacePath, setWorkspacePath] = useState(general?.workspacePath || "");

  useEffect(() => {
    if (general?.workspacePath !== undefined) {
      setWorkspacePath(general.workspacePath);
    }
  }, [general?.workspacePath]);

  const handleToggle = (key) => {
    const newVal = !(general?.[key]);
    updateSetting("general", key, newVal);
  };

  const handleChange = (key, val) => {
    updateSetting("general", key, val);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Settings2 className="me-2 text-primary" size={28} />General Configuration</h2>
          <p className="text-body-secondary mb-0">Manage platform-wide behavior, aesthetics, and workspace defaults.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger d-flex align-items-center mb-4">
          <ShieldAlert className="me-2" size={18} />
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Left Column */}
        <Col md={6}>
          <Card className="shadow-sm h-100 border-0 bg-body-tertiary">
            <Card.Body>
              <div className="d-flex align-items-center mb-4">
                <div className="bg-primary bg-opacity-10 text-primary p-2 rounded me-3">
                  <Monitor size={20} />
                </div>
                <h5 className="mb-0 fw-semibold">Aesthetics & UI</h5>
              </div>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Platform Theme</Form.Label>
                <Form.Select 
                  size="lg"
                  className="fs-6"
                  value={general?.theme || "rasputin-dark"}
                  onChange={(e) => handleChange("theme", e.target.value)}
                >
                  {themeOptions.map(([val, label, desc]) => (
                    <option key={val} value={val}>{label} - {desc}</option>
                  ))}
                </Form.Select>
              </Form.Group>

              <Form.Group>
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Interface Language</Form.Label>
                <Form.Select 
                  size="lg"
                  className="fs-6"
                  value={general?.language || "en"}
                  onChange={(e) => handleChange("language", e.target.value)}
                >
                  <option value="en">English (US)</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="ja">日本語</option>
                </Form.Select>
              </Form.Group>
            </Card.Body>
          </Card>
        </Col>

        {/* Right Column */}
        <Col md={6}>
          <Card className="shadow-sm h-100 border-0 bg-body-tertiary">
            <Card.Body>
              <div className="d-flex align-items-center mb-4">
                <div className="bg-info bg-opacity-10 text-info p-2 rounded me-3">
                  <BookOpen size={20} />
                </div>
                <h5 className="mb-0 fw-semibold">Environment</h5>
              </div>
              
              <Form.Group className="mb-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Default Workspace Path</Form.Label>
                <Form.Control 
                  type="text" 
                  size="lg"
                  className="fs-6 font-monospace"
                  value={workspacePath}
                  onChange={(e) => setWorkspacePath(e.target.value)}
                  onBlur={() => handleChange("workspacePath", workspacePath)}
                  placeholder="/var/rasputin/workspace"
                />
                <Form.Text className="text-muted">The root directory for new agent tasks and file outputs.</Form.Text>
              </Form.Group>

              <div className="bg-body p-3 rounded border">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div className="fw-medium">Markdown Formatting</div>
                  <Form.Check 
                    type="switch" 
                    id="markdown-switch"
                    checked={general?.markdownOutput !== false}
                    onChange={() => handleToggle("markdownOutput")}
                  />
                </div>
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <span className="fw-medium">Testing Mode</span>
                    <Badge bg="warning" text="dark" className="ms-2">Dry-Run</Badge>
                  </div>
                  <Form.Check 
                    type="switch" 
                    id="testing-mode-switch"
                    checked={!!general?.testingMode}
                    onChange={() => handleToggle("testingMode")}
                  />
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Full Width Footer Area */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-primary bg-opacity-10 text-primary">
            <Card.Body className="d-flex justify-content-between align-items-center py-3">
              <div>
                <h6 className="mb-1 fw-bold">Telemetry & Analytics</h6>
                <p className="mb-0 small opacity-75">Help us improve Rasputin by sharing anonymous usage data.</p>
              </div>
              <Form.Check 
                type="switch" 
                id="telemetry-switch"
                className="fs-4"
                checked={!!general?.telemetryEnabled}
                onChange={() => handleToggle("telemetryEnabled")}
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
