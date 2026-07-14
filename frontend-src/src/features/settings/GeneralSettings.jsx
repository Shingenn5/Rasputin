import React, { useState, useEffect } from "react";
import { Card, Form, Row, Col, Badge, Spinner, Button } from "react-bootstrap";
import { Monitor, Moon, Sun, ShieldAlert, BookOpen, Settings2, Save } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";
import { themeOptions } from "../../lib/constants.js";

export function GeneralSettings({ setTheme, motionMode = "full", setMotionMode, testingMode, updateTestingMode }) {
  const general = useSettingsStore(state => state.general);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.general);

  // Local state for form
  const [formData, setFormData] = useState({});
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (general) {
      setFormData(general);
      setIsDirty(false);
    }
  }, [general]);

  const handleChange = (key, val) => {
    setFormData(prev => ({ ...prev, [key]: val }));
    setIsDirty(true);
    if (key === "theme" && setTheme) {
      setTheme(val);
    }
  };

  const handleToggle = (key) => {
    setFormData(prev => ({ ...prev, [key]: !prev[key] }));
    setIsDirty(true);
  };

  const handleSave = async () => {
    for (const [key, val] of Object.entries(formData)) {
      if (general?.[key] !== val) {
        await updateSetting("general", key, val);
      }
    }
    setIsDirty(false);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Settings2 className="me-2 text-primary" size={28} />General Configuration</h2>
          <p className="text-body-secondary mb-0">Manage platform-wide behavior, aesthetics, and workspace defaults.</p>
        </div>
        <div className="d-flex align-items-center gap-3">
          {loading && <Spinner animation="border" size="sm" variant="secondary" />}
          <Button variant="primary" disabled={!isDirty || loading} onClick={handleSave} className="d-flex align-items-center">
            <Save size={16} className="me-2" /> Save Changes
          </Button>
        </div>
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
                  value={formData?.theme || "rasputin-dark"}
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
                  value={formData?.language || "en"}
                  onChange={(e) => handleChange("language", e.target.value)}
                >
                  <option value="en">English (US)</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="ja">日本語</option>
                </Form.Select>
              </Form.Group>

              <Form.Group className="mt-4">
                <Form.Label className="fw-medium text-muted small text-uppercase tracking-wide">Interface Motion</Form.Label>
                <Form.Select
                  data-testid="interface-motion-select"
                  size="lg"
                  className="fs-6"
                  value={motionMode}
                  onChange={(event) => setMotionMode?.(event.target.value)}
                >
                  <option value="full">Full motion — cinematic effects</option>
                  <option value="reduced">Reduced motion — minimal effects</option>
                </Form.Select>
                <Form.Text className="text-muted">Applies immediately and is saved as your Rasputin preference.</Form.Text>
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
                  value={formData?.workspacePath || ""}
                  onChange={(e) => handleChange("workspacePath", e.target.value)}
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
                    checked={formData?.markdownOutput !== false}
                    onChange={() => handleToggle("markdownOutput")}
                  />
                </div>
                <div className="d-flex justify-content-between align-items-center">
                  <div>
                    <span className="fw-medium">Testing Mode</span>
                    <Badge bg="" className="badge-soft-warn ms-2">Dry-Run</Badge>
                    <Form.Text className="d-block text-muted">Routes chat to a mock model with canned replies. Applies immediately.</Form.Text>
                  </div>
                  <Form.Check
                    type="switch"
                    id="testing-mode-switch"
                    checked={!!testingMode}
                    onChange={() => updateTestingMode?.(!testingMode)}
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
