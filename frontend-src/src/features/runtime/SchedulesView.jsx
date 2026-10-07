import React from "react";
import { Badge, Button, Card, Col, Form, Row, Stack } from "react-bootstrap";
import { PageHeader } from "./RuntimePrimitives.jsx";

export function SchedulesView({ view, schedules, createSchedule }) {
  return (
    <section className={`app-view ${view === "schedules" ? "active" : ""}`} id="schedulesView" data-app-view="schedules">
      <PageHeader title="Schedules" text="Durable schedule definitions for future autonomous recurring tasks." />
      <div className="task-dashboard">
        <Card className="settings-card shadow-sm mb-3">
          <Card.Body>
            <Form onSubmit={createSchedule}>
              <Row className="g-3 align-items-end">
                <Col md={3}><Form.Label>Name</Form.Label><Form.Control name="name" placeholder="Daily review" /></Col>
                <Col md={5}><Form.Label>Prompt</Form.Label><Form.Control name="prompt" placeholder="Review my active workspace" /></Col>
                <Col md={2}><Form.Label>Interval seconds</Form.Label><Form.Control name="intervalSeconds" type="number" defaultValue="0" /></Col>
                <Col md={2}><Form.Check type="switch" name="enabled" label="Enabled" /></Col>
                <Col xs={12}><Button type="submit">Create Schedule</Button></Col>
              </Row>
            </Form>
          </Card.Body>
        </Card>
        <Stack gap={2}>
          {(schedules?.schedules || []).map((schedule) => (
            <Card className="settings-card shadow-sm" key={schedule.id}>
              <Card.Body>
                <h2>{schedule.name}</h2>
                <p>{schedule.prompt}</p>
                <Badge bg={schedule.enabled ? "success" : "secondary"}>{schedule.enabled ? "enabled" : "disabled"}</Badge>
              </Card.Body>
            </Card>
          ))}
        </Stack>
      </div>
    </section>
  );
}
