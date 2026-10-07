import React from "react";
import { Badge, Card, Col, Row } from "react-bootstrap";
import { PageHeader } from "./RuntimePrimitives.jsx";

export function AgentsView({ view, tasks, models }) {
  const running = tasks.filter((task) => task.status === "running");
  const helpers = tasks.filter((task) => task.parentId);
  return (
    <section className={`app-view ${view === "agents" ? "active" : ""}`} id="agentsView" data-app-view="agents">
      <PageHeader title="Agents" text="Runtime orchestration, sub-agents, model roles, and current autonomy state." />
      <div className="task-dashboard">
        <Row className="g-3">
          <MiniCard title="Active runs" value={running.length} />
          <MiniCard title="Sub-agents" value={helpers.length} />
          <MiniCard title="Model roles" value={new Set(models.map((model) => model.role || "helper")).size} />
        </Row>
        <Card className="settings-card shadow-sm mt-3">
          <Card.Body>
            <h2>Runtime Pipeline</h2>
            <div className="runtime-steps">
              {["Intake", "Context", "Plan", "Tool Plan", "Approval", "Execute", "Reflect", "Memory"].map((step) => (
                <Badge bg="secondary" key={step}>{step}</Badge>
              ))}
            </div>
            <p className="text-body-secondary mt-3 mb-0">Risky actions are routed through the approval queue. Local RAG, Graphify, and memory recall can run autonomously inside approved workspaces.</p>
          </Card.Body>
        </Card>
      </div>
    </section>
  );
}

function MiniCard({ title, value }) {
  return (
    <Col md={4}>
      <Card className="settings-card shadow-sm h-100"><Card.Body><strong className="fs-4">{value}</strong><span className="text-body-secondary d-block">{title}</span></Card.Body></Card>
    </Col>
  );
}
