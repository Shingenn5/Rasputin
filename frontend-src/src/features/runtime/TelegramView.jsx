import React from "react";
import { Badge, Button, Card, Col, Form, Row } from "react-bootstrap";
import { PageHeader } from "./RuntimePrimitives.jsx";

export function TelegramView({ view, telegram, configureTelegram, testTelegram }) {
  return (
    <section className={`app-view ${view === "telegram" ? "active" : ""}`} id="telegramView" data-app-view="telegram">
      <PageHeader title="Telegram" text="Optional phone approvals through outbound Bot API polling. No public webhook." />
      <div className="task-dashboard">
        <Card className="settings-card shadow-sm">
          <Card.Body>
            <div className="section-row">
              <div>
                <Badge bg={telegram?.enabled ? "success" : "secondary"}>{telegram?.enabled ? "enabled" : "disabled"}</Badge>
                <h2 className="mt-2">Approval Bot</h2>
                <p className="text-body-secondary mb-0">Telegram receives redacted metadata only: code, action type, risk, workspace, and shortened paths.</p>
              </div>
              <Button variant="outline-secondary" onClick={testTelegram} disabled={!telegram?.configured}>Send Test</Button>
            </div>
            <Form className="mt-3" onSubmit={configureTelegram}>
              <Row className="g-3">
                <Col lg={5}><Form.Label>Bot token</Form.Label><Form.Control name="botToken" type="password" placeholder={telegram?.configured ? "Configured" : "123456:ABC"} /></Col>
                <Col lg={4}><Form.Label>Allowed chat id</Form.Label><Form.Control name="allowedChatId" defaultValue={telegram?.allowedChatId || ""} /></Col>
                <Col lg={3}><Form.Label>Mode</Form.Label><Form.Select name="redactionMode" defaultValue={telegram?.redactionMode || "summary"}><option value="summary">Redacted summary</option><option value="codes">Codes only</option></Form.Select></Col>
                <Col xs={12}><Form.Check type="switch" name="enabled" defaultChecked={!!telegram?.enabled} label="Enable polling" /></Col>
                <Col xs={12}><Button type="submit">Save Telegram</Button></Col>
              </Row>
            </Form>
            {telegram?.lastError && <p className="text-danger mt-3 mb-0">{telegram.lastError}</p>}
          </Card.Body>
        </Card>
      </div>
    </section>
  );
}
