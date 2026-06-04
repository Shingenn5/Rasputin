import React, { useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Row, Stack } from "react-bootstrap";
import { displayWorkspaceName } from "../../lib/display.js";

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

export function SessionsView({ view, sessions, selectedSession, loadSession, createSkillFromSession }) {
  return (
    <section className={`app-view ${view === "sessions" ? "active" : ""}`} id="sessionsView" data-app-view="sessions">
      <PageHeader title="Sessions" text="Persistent conversations and task history stored in SQLite." />
      <div className="task-dashboard">
        <Row className="g-3">
          <Col lg={4}>
            <Card className="settings-card shadow-sm h-100">
              <Card.Body>
                <h2>Recent Sessions</h2>
                <ListGroup className="runtime-list">
                  {(sessions?.sessions || []).map((session) => (
                    <ListGroup.Item key={session.id} action onClick={() => loadSession(session.id)}>
                      <strong>{session.title}</strong>
                      <small className="d-block text-body-secondary">{session.status} / {session.mode} / {session.workspace}</small>
                    </ListGroup.Item>
                  ))}
                </ListGroup>
              </Card.Body>
            </Card>
          </Col>
          <Col lg={8}>
            <Card className="settings-card shadow-sm h-100">
              <Card.Body>
                <div className="section-row">
                  <div>
                    <h2>{selectedSession?.session?.title || "Select a session"}</h2>
                    <p className="text-body-secondary mb-0">{selectedSession?.session?.summary || "Review messages, tasks, and saved context."}</p>
                  </div>
                  {selectedSession?.session && <Button variant="outline-secondary" onClick={() => createSkillFromSession(selectedSession.session.id)}>Preview Skill</Button>}
                </div>
                <Stack gap={2} className="mt-3">
                  {(selectedSession?.messages || []).map((message, index) => (
                    <Card className="message-card" key={`${message.createdAt || message.created_at}-${index}`}>
                      <Card.Body>
                        <Badge bg={message.role === "assistant" ? "primary" : "secondary"}>{message.role}</Badge>
                        <p className="mb-0 mt-2">{message.content}</p>
                      </Card.Body>
                    </Card>
                  ))}
                </Stack>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </div>
    </section>
  );
}

export function ApprovalsView({ view, approvals, approveApproval, denyApproval, refreshApprovals, openTaskDetails }) {
  const items = approvals?.approvals || [];
  return (
    <section className={`app-view ${view === "approvals" ? "active" : ""}`} id="approvalsView" data-app-view="approvals">
      <PageHeader title="Approvals" text="Risky tool actions wait here before execution." action={<Button variant="outline-secondary" size="sm" onClick={refreshApprovals}>Refresh</Button>} />
      <div className="task-dashboard">
        <Stack gap={3}>
          {items.map((approval) => (
            <Card className="settings-card shadow-sm" key={approval.id} data-testid="approval-card">
              <Card.Body>
                <div className="section-row">
                  <div>
                    <Badge bg={approval.status === "pending" ? "warning" : approval.status === "approved" ? "success" : "secondary"}>{approval.status}</Badge>
                    <h2 className="mt-2">{approval.summary}</h2>
                    <p className="text-body-secondary mb-0">
                      Code {approval.code} / {approval.actionType || approval.action_type} / {displayWorkspaceName(approval.workspace)}
                    </p>
                  </div>
                  <Stack direction="horizontal" gap={2}>
                    {approval.taskId && (
                      <Button variant="outline-secondary" onClick={() => openTaskDetails(approval.taskId)}>Open Task</Button>
                    )}
                    {approval.status === "pending" && (
                      <>
                        <Button onClick={() => approveApproval(approval.id)}>Approve</Button>
                        <Button variant="outline-danger" onClick={() => denyApproval(approval.id)}>Deny</Button>
                      </>
                    )}
                  </Stack>
                </div>
                <dl className="detail-grid approval-detail-grid mt-3">
                  <dt>Risk</dt><dd>{approval.riskLevel || approval.risk_level || "approval required"}</dd>
                  <dt>Workspace</dt><dd>{displayWorkspaceName(approval.workspace)}</dd>
                  <dt>Expires</dt><dd>{formatRuntimeTime(approval.expiresAt || approval.expires_at)}</dd>
                  <dt>Details</dt><dd>{summarizeApproval(approval.redactedDetail || approval.redacted_detail || {})}</dd>
                </dl>
                <details className="advanced-block approval-raw-detail">
                  <summary>Redacted metadata</summary>
                  <pre className="log-box mt-3 mb-0">{JSON.stringify(approval.redactedDetail || approval.redacted_detail || {}, null, 2)}</pre>
                </details>
              </Card.Body>
            </Card>
          ))}
          {!items.length && <EmptyCard title="No approvals" text="Rasputin has no pending approval requests." />}
        </Stack>
      </div>
    </section>
  );
}

export function MemoryView({ view, memoryReview, memorySearchResults, searchMemory, approveMemory, rejectMemory }) {
  const [query, setQuery] = useState("");
  const pending = memoryReview?.items || [];
  return (
    <section className={`app-view ${view === "memory" ? "active" : ""}`} id="memoryView" data-app-view="memory">
      <PageHeader title="Memory" text="Warmind recall, memory suggestions, and local Markdown exports." />
      <div className="task-dashboard">
        <Card className="settings-card shadow-sm">
          <Card.Body>
            <Form onSubmit={(event) => { event.preventDefault(); searchMemory(query); }}>
              <Row className="g-2">
                <Col><Form.Control value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search saved memory" /></Col>
                <Col xs="auto"><Button type="submit">Search</Button></Col>
              </Row>
            </Form>
            <Stack gap={2} className="mt-3">
              {(memorySearchResults?.items || []).map((item) => <MemoryItem key={item.id} item={item} />)}
            </Stack>
          </Card.Body>
        </Card>
        <Card className="settings-card shadow-sm mt-3">
          <Card.Body>
            <h2>Review Queue</h2>
            <Stack gap={2}>
              {pending.map((item) => (
                <Card className="message-card" key={item.id}>
                  <Card.Body>
                    <div className="section-row">
                      <MemoryItem item={item} />
                      <Stack direction="horizontal" gap={2}>
                        <Button size="sm" onClick={() => approveMemory(item.id)}>Save</Button>
                        <Button size="sm" variant="outline-danger" onClick={() => rejectMemory(item.id)}>Reject</Button>
                      </Stack>
                    </div>
                  </Card.Body>
                </Card>
              ))}
              {!pending.length && <p className="text-body-secondary mb-0">No memory suggestions waiting.</p>}
            </Stack>
          </Card.Body>
        </Card>
      </div>
    </section>
  );
}

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

export function WarsatView({ view, warsat, plan, error, createPlan, refresh }) {
  const protocols = warsat?.protocols || [];
  const firstProtocol = protocols[0];
  return (
    <section className={`app-view ${view === "warsat" ? "active" : ""}`} id="warsatView" data-app-view="warsat" data-testid="warsat-view">
      <PageHeader
        title="Warsat"
        text="Model runtime launch protocols for local Docker containers. Current mode is planning only."
        action={<Button variant="outline-secondary" size="sm" onClick={refresh}>Refresh Protocols</Button>}
      />
      <div className="task-dashboard warsat-dashboard">
        <Row className="g-3">
          <MiniCard title="Launch protocols" value={warsat?.count || protocols.length} />
          <MiniCard title="Docker control" value={warsat?.dockerControlEnabled ? "Enabled" : "Off"} />
          <MiniCard title="Execution" value={warsat?.executionEnabled ? "Enabled" : "Plan only"} />
        </Row>

        <Card className="settings-card warsat-panel shadow-sm mt-3">
          <Card.Body>
            <div className="section-row">
              <div>
                <h2>Launch Plan</h2>
                <p className="text-body-secondary mb-0">
                  Generate a dry-run plan before Rasputin is allowed to pull images, start containers, or edit the model registry.
                </p>
              </div>
              <Badge bg="warning">Approval required later</Badge>
            </div>
            <Form className="mt-3" data-testid="warsat-plan-form" onSubmit={createPlan}>
              <Row className="g-3 align-items-end">
                <Col lg={4}>
                  <Form.Label htmlFor="warsatProtocolId">Protocol</Form.Label>
                  <Form.Select id="warsatProtocolId" name="protocolId" defaultValue={firstProtocol?.id || ""} required>
                    <option value="" disabled>Choose a protocol</option>
                    {protocols.map((protocol) => (
                      <option key={protocol.id} value={protocol.id}>{protocol.name}</option>
                    ))}
                  </Form.Select>
                </Col>
                <Col lg={4}>
                  <Form.Label htmlFor="warsatModelRef">Model id</Form.Label>
                  <Form.Control id="warsatModelRef" name="modelRef" placeholder="Qwen/Qwen2.5-Coder-7B-Instruct" />
                  <Form.Text>Use this for vLLM or any Hugging Face based runtime.</Form.Text>
                </Col>
                <Col lg={4}>
                  <Form.Label htmlFor="warsatModelPath">Mounted model path</Form.Label>
                  <Form.Control id="warsatModelPath" name="modelPath" placeholder="models/my-model.gguf" />
                  <Form.Text>Use this for GGUF protocols or mounted model folders.</Form.Text>
                </Col>
                <Col md={3}>
                  <Form.Label htmlFor="warsatHostPort">Host port</Form.Label>
                  <Form.Control id="warsatHostPort" name="hostPort" type="number" min="1024" max="65535" placeholder="Auto" />
                </Col>
                <Col md={3}>
                  <Form.Label htmlFor="warsatRole">Model role</Form.Label>
                  <Form.Select id="warsatRole" name="role" defaultValue={firstProtocol?.defaultRole || "helper"}>
                    {["main", "planner", "executor", "coder", "researcher", "summarizer", "memory", "embeddings", "helper"].map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </Form.Select>
                </Col>
                <Col md={4}>
                  <Form.Label htmlFor="warsatContainerName">Container name</Form.Label>
                  <Form.Control id="warsatContainerName" name="containerName" placeholder="Auto" />
                </Col>
                <Col md={2}>
                  <Button className="w-100" type="submit">Plan</Button>
                </Col>
              </Row>
            </Form>
            {error && <p className="text-danger mt-3 mb-0" role="alert">{error}</p>}
          </Card.Body>
        </Card>

        <Row className="g-3 mt-1">
          {protocols.map((protocol) => (
            <Col xl={6} key={protocol.id}>
              <Card className="settings-card warsat-protocol-card shadow-sm h-100" data-testid="warsat-protocol-card">
                <Card.Body>
                  <div className="section-row align-items-start">
                    <div>
                      <Badge bg="secondary">{protocol.runtime}</Badge>
                      <h2 className="mt-2">{protocol.name}</h2>
                      <p className="text-body-secondary mb-0">{protocol.description}</p>
                    </div>
                    <Badge bg={protocol.gpu?.required ? "danger" : "success"}>{protocol.gpu?.required ? "GPU" : "CPU OK"}</Badge>
                  </div>
                  <dl className="detail-grid mt-3 mb-0">
                    <dt>Image</dt><dd>{protocol.image}</dd>
                    <dt>Format</dt><dd>{protocol.modelFormat}</dd>
                    <dt>Default port</dt><dd>{protocol.defaultHostPort}</dd>
                    <dt>Capabilities</dt><dd>{(protocol.capabilities || []).join(", ") || "chat"}</dd>
                  </dl>
                  {!!protocol.notes?.length && (
                    <ul className="warsat-note-list mt-3 mb-0">
                      {protocol.notes.slice(0, 3).map((note) => <li key={note}>{note}</li>)}
                    </ul>
                  )}
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>

        {plan && (
          <Card className="settings-card warsat-plan-card shadow-sm mt-3" data-testid="warsat-launch-plan">
            <Card.Body>
              <div className="section-row">
                <div>
                  <Badge bg="warning">{plan.riskLevel}</Badge>
                  <h2 className="mt-2">{plan.protocolName}</h2>
                  <p className="text-body-secondary mb-0">
                    {plan.runtime} on port {plan.hostPort}. Execution is {plan.executionEnabled ? "enabled" : "disabled"}.
                  </p>
                </div>
                <Badge bg={plan.securityChecks?.localhostOnly ? "success" : "danger"}>
                  {plan.securityChecks?.localhostOnly ? "localhost only" : "review binding"}
                </Badge>
              </div>

              <Row className="g-3 mt-1">
                <Col lg={6}>
                  <h3>Model Registry Entry</h3>
                  <dl className="detail-grid">
                    <dt>Name</dt><dd>{plan.expectedModelRegistryEntry?.name}</dd>
                    <dt>Role</dt><dd>{plan.expectedModelRegistryEntry?.role}</dd>
                    <dt>Endpoint</dt><dd>{plan.expectedModelRegistryEntry?.baseUrl}</dd>
                    <dt>Container</dt><dd>{plan.expectedModelRegistryEntry?.container}</dd>
                  </dl>
                </Col>
                <Col lg={6}>
                  <h3>Safety Checks</h3>
                  <dl className="detail-grid">
                    <dt>Approval</dt><dd>{plan.requiresApproval ? "Required" : "Not required"}</dd>
                    <dt>No new privileges</dt><dd>{plan.securityChecks?.noNewPrivileges ? "Yes" : "No"}</dd>
                    <dt>Host network</dt><dd>{plan.securityChecks?.hostNetwork ? "Requested" : "Blocked"}</dd>
                    <dt>Health</dt><dd>{plan.healthUrl}</dd>
                  </dl>
                </Col>
              </Row>

              <details className="advanced-block mt-3" open>
                <summary>Command Preview</summary>
                <pre className="log-box mt-3 mb-0">{formatCommandPreview(plan.commandPreview)}</pre>
              </details>

              {!!plan.warnings?.length && (
                <div className="warsat-warning-list mt-3" role="status">
                  {plan.warnings.map((warning) => <p key={warning} className="mb-1">{warning}</p>)}
                </div>
              )}
            </Card.Body>
          </Card>
        )}
      </div>
    </section>
  );
}

function PageHeader({ title, text, action }) {
  return (
    <header className="page-header border-bottom bg-body">
      <div>
        <h1 className="mb-0">{title}</h1>
        <p className="text-body-secondary mb-0">{text}</p>
      </div>
      {action}
    </header>
  );
}

function MiniCard({ title, value }) {
  return (
    <Col md={4}>
      <Card className="settings-card shadow-sm h-100"><Card.Body><strong className="fs-4">{value}</strong><span className="text-body-secondary d-block">{title}</span></Card.Body></Card>
    </Col>
  );
}

function EmptyCard({ title, text }) {
  return <Card className="settings-card shadow-sm"><Card.Body><h2>{title}</h2><p className="text-body-secondary mb-0">{text}</p></Card.Body></Card>;
}

function MemoryItem({ item }) {
  return (
    <div>
      <Badge bg={item.status === "pending" ? "warning" : "secondary"}>{item.kind}</Badge>
      <p className="mb-0 mt-2">{typeof item.content === "string" ? item.content : JSON.stringify(item.content)}</p>
    </div>
  );
}

function formatRuntimeTime(value) {
  if (!value) return "Unknown";
  const numeric = Number(value);
  const date = new Date(numeric > 10_000_000_000 ? numeric : numeric * 1000);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function summarizeApproval(value) {
  if (!value || typeof value !== "object") return "No redacted details.";
  return Object.entries(value)
    .slice(0, 6)
    .map(([key, item]) => `${key}: ${typeof item === "object" ? JSON.stringify(item) : item}`)
    .join(" / ") || "No redacted details.";
}

function formatCommandPreview(commandPreview) {
  if (!commandPreview) return "No command preview.";
  const pull = commandPreview.pull || [];
  const run = commandPreview.run || [];
  return [
    "# Pull image",
    shellJoin(pull),
    "",
    "# Start runtime",
    shellJoin(run),
  ].join("\n");
}

function shellJoin(parts) {
  return (parts || [])
    .map((part) => String(part).includes(" ") ? JSON.stringify(String(part)) : String(part))
    .join(" ");
}
