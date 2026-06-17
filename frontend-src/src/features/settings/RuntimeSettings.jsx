import React, { useState } from "react";
import { Card, Form, Row, Col, Spinner, Badge } from "react-bootstrap";
import { Activity, Cpu, Timer, HardDrive, ListOrdered } from "lucide-react";
import { useSettingsStore } from "./settingsStore.js";
import { updateSetting } from "./settingsActions.js";

export function RuntimeSettings() {
  const runtime = useSettingsStore(state => state.runtime);
  const loading = useSettingsStore(state => state.loading);
  const error = useSettingsStore(state => state.errors?.runtime);

  const [maxAgents, setMaxAgents] = useState(runtime?.maxAgents || 10);
  const [taskTimeout, setTaskTimeout] = useState(runtime?.taskTimeout || 3600);
  const [queueLimit, setQueueLimit] = useState(runtime?.queueLimit || 500);

  const handleChange = (key, val) => {
    updateSetting("runtime", key, parseInt(val, 10));
  };

  const handleBlur = (key, localVal, defaultVal) => {
    const val = parseInt(localVal, 10);
    if (isNaN(val)) {
      handleChange(key, defaultVal);
    } else {
      handleChange(key, val);
    }
  };

  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3 d-flex justify-content-between align-items-center">
        <div>
          <h2 className="mb-1"><Activity className="me-2 text-info" size={28} />Runtime Configuration</h2>
          <p className="text-body-secondary mb-0">Manage agent limits, execution timeouts, and task queue constraints.</p>
        </div>
        {loading && <Spinner animation="border" size="sm" variant="secondary" />}
      </div>

      {error && (
        <div className="alert alert-danger mb-4">
          {error}
        </div>
      )}

      {/* Hero Stats */}
      <Row className="g-4 mb-4">
        <Col md={4}>
          <Card className="shadow-sm border-0 bg-info bg-opacity-10 text-info h-100">
            <Card.Body className="d-flex align-items-center">
              <Cpu size={40} className="me-3 opacity-75" />
              <div>
                <h6 className="mb-0 fw-bold">Concurrency</h6>
                <div className="fs-4 fw-semibold">{maxAgents} <span className="fs-6 fw-normal opacity-75">Agents</span></div>
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="shadow-sm border-0 bg-warning bg-opacity-10 text-warning h-100">
            <Card.Body className="d-flex align-items-center">
              <Timer size={40} className="me-3 opacity-75" />
              <div>
                <h6 className="mb-0 fw-bold">Task Timeout</h6>
                <div className="fs-4 fw-semibold">{taskTimeout} <span className="fs-6 fw-normal opacity-75">sec</span></div>
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="shadow-sm border-0 bg-primary bg-opacity-10 text-primary h-100">
            <Card.Body className="d-flex align-items-center">
              <ListOrdered size={40} className="me-3 opacity-75" />
              <div>
                <h6 className="mb-0 fw-bold">Queue Depth</h6>
                <div className="fs-4 fw-semibold">{queueLimit} <span className="fs-6 fw-normal opacity-75">tasks</span></div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="g-4">
        {/* Execution Constraints */}
        <Col md={12}>
          <Card className="shadow-sm border-0">
            <Card.Header className="bg-body-tertiary fw-semibold pt-3 px-4">
              <HardDrive size={18} className="me-2 text-muted" />
              Execution Constraints
            </Card.Header>
            <Card.Body className="px-4 py-4">
              
              <Form.Group as={Row} className="align-items-center mb-4">
                <Form.Label column sm={4} className="fw-medium">
                  Maximum Concurrent Agents
                  <div className="text-muted small fw-normal">Hard limit on how many subagents can run simultaneously.</div>
                </Form.Label>
                <Col sm={4}>
                  <Form.Control 
                    type="number" 
                    className="fs-5"
                    value={maxAgents}
                    onChange={(e) => setMaxAgents(e.target.value)}
                    onBlur={() => handleBlur("maxAgents", maxAgents, 10)}
                    min="1"
                    max="100"
                  />
                </Col>
              </Form.Group>

              <div className="border-top pt-4"></div>

              <Form.Group as={Row} className="align-items-center mb-4">
                <Form.Label column sm={4} className="fw-medium">
                  Global Task Timeout (Seconds)
                  <div className="text-muted small fw-normal">Kill runaway background tasks after this duration.</div>
                </Form.Label>
                <Col sm={4}>
                  <Form.Control 
                    type="number" 
                    className="fs-5"
                    value={taskTimeout}
                    onChange={(e) => setTaskTimeout(e.target.value)}
                    onBlur={() => handleBlur("taskTimeout", taskTimeout, 3600)}
                    min="60"
                  />
                </Col>
              </Form.Group>

              <div className="border-top pt-4"></div>

              <Form.Group as={Row} className="align-items-center">
                <Form.Label column sm={4} className="fw-medium">
                  Maximum Queue Depth
                  <div className="text-muted small fw-normal">Maximum number of pending tasks allowed in the queue.</div>
                </Form.Label>
                <Col sm={4}>
                  <Form.Control 
                    type="number" 
                    className="fs-5"
                    value={queueLimit}
                    onChange={(e) => setQueueLimit(e.target.value)}
                    onBlur={() => handleBlur("queueLimit", queueLimit, 500)}
                    min="10"
                  />
                </Col>
              </Form.Group>

            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
