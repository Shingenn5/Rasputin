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
          <h2 className="mb-1"><Settings2 className="me-2" size={24} />General Configuration</h2>
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

      <div className="d-grid gap-4">
        {/* ── Environment & Paths ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <BookOpen size={16} className="me-2 text-muted" />
            Environment & Paths
          </Card.Header>
          <Card.Body>
            <Form.Group as={Row} className="align-items-center mb-0">
              <Form.Label column sm={4} className="fw-medium">
                Default Workspace Path
                <div className="text-muted small fw-normal">The root directory for new agent tasks.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Control 
                  type="text" 
                  value={workspacePath}
                  onChange={(e) => setWorkspacePath(e.target.value)}
                  onBlur={() => handleChange("workspacePath", workspacePath)}
                  placeholder="/var/rasputin/workspace"
                />
              </Col>
            </Form.Group>
          </Card.Body>
        </Card>

        {/* ── Aesthetics & UI ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <Monitor size={16} className="me-2 text-muted" />
            Aesthetics & UI
          </Card.Header>
          <Card.Body className="d-grid gap-4">
            <Form.Group as={Row} className="align-items-center">
              <Form.Label column sm={4} className="fw-medium">
                Platform Theme
                <div className="text-muted small fw-normal">Color scheme for the Rasputin GUI.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Select 
                  value={general?.theme || "rasputin-dark"}
                  onChange={(e) => handleChange("theme", e.target.value)}
                >
                  {themeOptions.map(([val, label, desc]) => (
                    <option key={val} value={val}>{label} - {desc}</option>
                  ))}
                </Form.Select>
              </Col>
            </Form.Group>

            <div className="border-top pt-3"></div>

            <Form.Group as={Row} className="align-items-center">
              <Form.Label column sm={4} className="fw-medium">
                Interface Language
                <div className="text-muted small fw-normal">Language used throughout the system.</div>
              </Form.Label>
              <Col sm={8}>
                <Form.Select 
                  value={general?.language || "en"}
                  onChange={(e) => handleChange("language", e.target.value)}
                >
                  <option value="en">English (US)</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="ja">日本語</option>
                </Form.Select>
              </Col>
            </Form.Group>
          </Card.Body>
        </Card>

        {/* ── System Behavior ── */}
        <Card className="shadow-sm">
          <Card.Header className="bg-body-tertiary fw-semibold">
            <ShieldAlert size={16} className="me-2 text-muted" />
            System Behavior
          </Card.Header>
          <Card.Body className="d-grid gap-3">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Testing Mode</div>
                <div className="text-muted small">Run commands and relays in dry-run mode to prevent actual execution.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="testing-mode-switch"
                checked={!!general?.testingMode}
                onChange={() => handleToggle("testingMode")}
              />
            </div>

            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Markdown Formatting</div>
                <div className="text-muted small">Render outputs using GitHub-flavored markdown.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="markdown-switch"
                checked={general?.markdownOutput !== false} // default true
                onChange={() => handleToggle("markdownOutput")}
              />
            </div>
            
            <div className="border-top pt-3"></div>

            <div className="d-flex justify-content-between align-items-center">
              <div>
                <div className="fw-medium">Telemetry Sharing <Badge bg="secondary" className="ms-1">Beta</Badge></div>
                <div className="text-muted small">Send anonymous performance data to improve WarSat reliability.</div>
              </div>
              <Form.Check 
                type="switch" 
                id="telemetry-switch"
                checked={!!general?.telemetryEnabled}
                onChange={() => handleToggle("telemetryEnabled")}
              />
            </div>
          </Card.Body>
        </Card>

      </div>
    </section>
  );
}
