import React, { useState } from "react";
import { Badge, Button, Card, Col, Form, Row } from "react-bootstrap";
import { PageHeader } from "./RuntimePrimitives.jsx";

export function SkillsView({ view, skills, skillPreview, sessions, createSkillFromSession, enableSkill, disableSkill }) {
  const [sessionId, setSessionId] = useState("");
  return (
    <section className={`app-view ${view === "skills" ? "active" : ""}`} id="skillsView" data-app-view="skills">
      <PageHeader title="Skills" text="Reusable local workflows stored as SKILL.md packages." />
      <div className="task-dashboard">
        <Card className="settings-card shadow-sm mb-3">
          <Card.Body>
            <Form onSubmit={(event) => { event.preventDefault(); createSkillFromSession(sessionId); }}>
              <Row className="g-2 align-items-end">
                <Col>
                  <Form.Label>Save workflow from session</Form.Label>
                  <Form.Select value={sessionId} onChange={(event) => setSessionId(event.target.value)}>
                    <option value="">Choose a session</option>
                    {(sessions?.sessions || []).map((session) => <option key={session.id} value={session.id}>{session.title}</option>)}
                  </Form.Select>
                </Col>
                <Col xs="auto"><Button type="submit" disabled={!sessionId}>Preview Skill</Button></Col>
              </Row>
            </Form>
            {skillPreview && <pre className="log-box mt-3">{skillPreview.content}</pre>}
          </Card.Body>
        </Card>
        <Row className="g-3">
          {(skills?.skills || []).map((skill) => (
            <Col lg={6} key={skill.name}>
              <Card className="settings-card shadow-sm h-100">
                <Card.Body>
                  <div className="section-row">
                    <div>
                      <Badge bg={skill.enabled ? "success" : "secondary"}>{skill.enabled ? "enabled" : "disabled"}</Badge>
                      <h2 className="mt-2">{skill.name}</h2>
                      <p className="text-body-secondary mb-0">{skill.description}</p>
                    </div>
                    <Button variant="outline-secondary" size="sm" onClick={() => skill.enabled ? disableSkill(skill.name) : enableSkill(skill.name)}>{skill.enabled ? "Disable" : "Enable"}</Button>
                  </div>
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      </div>
    </section>
  );
}
