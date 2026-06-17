import React from "react";
import { Card, Form, Row, Col, Spinner } from "react-bootstrap";
import { Bell, Mail, MessageSquare, Volume2, MonitorSmartphone } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function NotificationSettings() {
  const notifications = useSettingsStore(state => state.notifications);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.notifications);

  const handleToggle = (key) => {
    const newVal = !(notifications?.[key]);
    updateSetting("notifications", key, newVal);
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Bell className="me-2 text-primary" size={28} />Notification Management</h2>
          <p className="text-body-secondary mb-0">Configure alerts for mission completions, failures, and system events.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      <Row className="g-4">
        {/* Browser Notifications */}
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-body-tertiary">
            <Card.Header className="bg-transparent border-0 pt-4 px-4 fw-semibold d-flex align-items-center">
              <MonitorSmartphone size={20} className="me-2 text-primary" />
              Browser & Desktop Alerts
            </Card.Header>
            <Card.Body className="px-4 pb-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium">Mission Complete Alerts</div>
                <Form.Check type="switch" id="notify-complete" checked={notifications?.missionComplete !== false} onChange={() => handleToggle("missionComplete")} />
              </div>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium text-danger">Mission Failure Alerts</div>
                <Form.Check type="switch" id="notify-failed" checked={notifications?.missionFailed !== false} onChange={() => handleToggle("missionFailed")} />
              </div>
              <div className="border-top pt-3 mt-1 d-flex justify-content-between align-items-center">
                <div className="fw-medium d-flex align-items-center">
                  <Volume2 size={16} className="me-2 text-muted" />
                  Play Sounds
                </div>
                <Form.Check type="switch" id="notify-sounds" checked={!!notifications?.playSounds} onChange={() => handleToggle("playSounds")} />
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* External Channels */}
        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <Mail size={18} className="me-2 text-muted" />
              Email Notifications
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <p className="text-muted small">Send reports and alerts directly to your inbox via SMTP.</p>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium">Enable Email Alerts</div>
                <Form.Check type="switch" id="email-switch" checked={!!notifications?.emailEnabled} onChange={() => handleToggle("emailEnabled")} />
              </div>
              {notifications?.emailEnabled && (
                <Form.Group>
                  <Form.Label className="small text-muted">SMTP Server</Form.Label>
                  <Form.Control type="text" placeholder="smtp.example.com" />
                </Form.Group>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4 border-bottom-0 d-flex align-items-center">
              <MessageSquare size={18} className="me-2 text-success" />
              Webhooks (Slack/Discord)
            </Card.Header>
            <Card.Body className="px-4 border-top">
              <p className="text-muted small">Post mission updates directly to a specific chat channel.</p>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div className="fw-medium">Enable Webhooks</div>
                <Form.Check type="switch" id="webhook-switch" checked={!!notifications?.webhookEnabled} onChange={() => handleToggle("webhookEnabled")} />
              </div>
              {notifications?.webhookEnabled && (
                <Form.Group>
                  <Form.Label className="small text-muted">Webhook URL</Form.Label>
                  <Form.Control type="text" placeholder="https://..." />
                </Form.Group>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
