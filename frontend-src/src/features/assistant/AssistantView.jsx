import React, { useMemo } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Stack } from "react-bootstrap";
import { Bot, CheckCircle2, Clock3, Link2, Mic, RefreshCw, ShieldCheck, Volume2, XCircle } from "lucide-react";

function titleize(value) {
  return String(value || "").replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusVariant(status) {
  if (["approved", "prepared", "ready_for_broker", "approved_for_broker", "ready", "completed"].includes(status)) return "success";
  if (["rejected", "denied", "blocked", "expired", "missing", "failed"].includes(status)) return "danger";
  if (["pending_approval", "awaiting_approval", "review_required", "needs_health_check"].includes(status)) return "warning";
  return "secondary";
}

function SectionHeader({ title, text, action }) {
  return (
    <div className="section-row mb-3">
      <div>
        <h2 className="h5 mb-1">{title}</h2>
        {text && <p className="text-body-secondary mb-0 small">{text}</p>}
      </div>
      {action}
    </div>
  );
}

export function AssistantView({
  view,
  profile,
  capabilities,
  plans,
  modelPacks,
  handoffs,
  voicePreview,
  contextPreview,
  loading = false,
  error = "",
  refresh,
  createPlan,
  saveModelPack,
  reviewPlan,
  requestHandoff,
  prepareHandoff,
  dispatchHandoff,
  previewVoice,
}) {
  const controlOperations = capabilities?.controlOperations || {};
  const brokerOperationMetadata = useMemo(() => {
    const raw = capabilities?.broker?.dispatchOperationMetadata || [];
    return Array.isArray(raw) ? Object.fromEntries(raw.map((item) => [item.operation, item])) : raw;
  }, [capabilities]);
  const operationEntries = useMemo(() => {
    if (Array.isArray(controlOperations)) return controlOperations.map((item) => [item.operation, item]);
    return Object.entries(controlOperations).map(([key, definition]) => {
      const operation = definition.operation || key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
      return [operation, { ...definition, operation }];
    });
  }, [controlOperations]);
  const planItems = plans?.plans || [];
  const packItems = modelPacks?.packs || [];
  const handoffItems = handoffs?.handoffs || [];
  const voiceRoles = capabilities?.voiceRoles || [];
  const policy = profile?.localControlPolicy || {};
  const contextPolicy = profile?.contextAuthority || {};

  return (
    <section className={`app-view ${view === "assistant" ? "active" : ""}`} id="assistantView" data-app-view="assistant" data-testid="assistant-view">
      <div className="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-3">
        <div>
          <p className="text-uppercase small fw-semibold text-body-secondary mb-1">Personal assistant control plane</p>
          <h1 className="h3 mb-1">{profile?.displayName || "Rasputin"}</h1>
          <p className="text-body-secondary mb-0">{profile?.mission || "Coordinate local models and agents as one dependable workstation assistant."}</p>
        </div>
        <Button variant="outline-secondary" size="sm" onClick={refresh} disabled={loading} data-testid="assistant-refresh">
          <RefreshCw size={14} className={loading ? "spin me-1" : "me-1"} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <div className="task-dashboard assistant-dashboard">
        <Row className="g-3">
          <Col xl={5}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-identity-card">
              <Card.Body>
                <SectionHeader title="Identity and context" text="Rasputin remains the stable personality and owner-scoped context authority." />
                <div className="d-flex align-items-start gap-3">
                  <div className="rounded-circle bg-primary-subtle text-primary p-3"><Bot size={22} aria-hidden="true" /></div>
                  <div>
                    <strong>{profile?.displayName || "Rasputin"}</strong>
                    <p className="small text-body-secondary mb-0 mt-1">{profile?.persona?.summary || "Local-first orchestration partner."}</p>
                  </div>
                </div>
                <div className="mt-3 d-flex flex-wrap gap-2">
                  {(profile?.persona?.traits || []).map((trait) => <Badge bg="light" text="dark" key={trait}>{trait}</Badge>)}
                </div>
                <dl className="row small mt-4 mb-0">
                  <dt className="col-6 text-body-secondary">Context scope</dt>
                  <dd className="col-6 text-end">{contextPolicy.crossWorkspace ? "Owner / cross-workspace" : "Current workspace"}</dd>
                  <dt className="col-6 text-body-secondary">Sensitive context</dt>
                  <dd className="col-6 text-end">{contextPolicy.sensitiveByDefault ? "Included" : "Excluded by default"}</dd>
                  <dt className="col-6 text-body-secondary">Host control</dt>
                  <dd className="col-6 text-end">{policy.brokerOnly ? "Broker only" : "Review policy"}</dd>
                </dl>
                <div className="border-top mt-3 pt-3 small text-body-secondary">
                  <ShieldCheck size={14} className="me-1 text-success" aria-hidden="true" />
                  Model containers have no direct host access.
                </div>
                <div className="border-top mt-3 pt-3" data-testid="assistant-context-preview">
                  <SectionHeader title="Context surface" text="Inspect owner-scoped memory and history before Rasputin builds a plan." />
                  <Form onSubmit={previewContext}>
                    <Row className="g-2">
                      <Col md={6}><Form.Control name="contextObjective" required placeholder="What should Rasputin recall?" aria-label="Context objective" /></Col>
                      <Col md={6}><Form.Control name="contextQuery" placeholder="Search across chats and workspaces" aria-label="Context query" /></Col>
                    </Row>
                    <div className="d-flex justify-content-end mt-2"><Button type="submit" size="sm" variant="outline-primary">Inspect context</Button></div>
                  </Form>
                  {contextPreview && (
                    <div className="small mt-2">
                      <div className="d-flex flex-wrap gap-2">
                        <Badge bg="secondary">Memory {contextPreview.memory?.items?.length || 0}</Badge>
                        <Badge bg="secondary">History {contextPreview.ownerHistory?.results?.length || 0}</Badge>
                        <Badge bg="light" text="dark">Sensitive excluded {contextPreview.memory?.sensitiveExcluded || 0}</Badge>
                      </div>
                      <div className="text-body-secondary mt-2">Owner scoped: {contextPreview.policy?.ownerScoped ? "yes" : "no"} · Cross workspace: {contextPreview.policy?.crossWorkspace ? "yes" : "no"}</div>
                    </div>
                  )}
                </div>
              </Card.Body>
            </Card>
          </Col>

          <Col xl={7}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-plan-composer">
              <Card.Body>
                <SectionHeader title="Plan a request" text="Describe the outcome. Rasputin will build a reviewable plan without starting anything." />
                <Form onSubmit={createPlan}>
                  <Form.Group className="mb-3" controlId="assistantObjective">
                    <Form.Label>Objective</Form.Label>
                    <Form.Control name="objective" required placeholder="Prepare a voice-enabled coding session" />
                  </Form.Group>
                  <Row className="g-2">
                    <Col md={6}>
                      <Form.Label htmlFor="assistantModelPack">Model pack</Form.Label>
                      <Form.Select id="assistantModelPack" name="modelPackId" defaultValue="">
                        <option value="">Use inline core pack</option>
                        {packItems.map((pack) => <option key={pack.packId} value={pack.packId}>{pack.packId} · v{pack.version}</option>)}
                      </Form.Select>
                    </Col>
                    <Col md={6}>
                      <Form.Label>Requested operations</Form.Label>
                      <div className="d-flex flex-wrap gap-2">
                        {operationEntries.map(([operation, definition]) => (
                          <Form.Check
                            key={operation}
                            inline
                            type="checkbox"
                            id={`assistant-op-${operation}`}
                            name="requestedOperations"
                            value={operation}
                            label={definition.label || titleize(operation)}
                          />
                        ))}
                      </div>
                    </Col>
                  </Row>
                  <div className="d-flex justify-content-end mt-3">
                    <Button type="submit" disabled={loading} data-testid="assistant-create-plan">Create preview</Button>
                  </div>
                </Form>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Row className="g-3 mt-1">
          <Col xl={5}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-model-packs">
              <Card.Body>
                <SectionHeader title="Named model packs" text="Reusable fleet definitions for conversation, planning, and voice workers." />
                <Form onSubmit={saveModelPack} className="border-bottom pb-3 mb-3">
                  <div className="d-flex gap-2">
                    <Form.Control name="packId" required placeholder="voice-core" aria-label="Model pack id" />
                    <Button type="submit" variant="outline-primary">Save pack</Button>
                  </div>
                  <div className="mt-2 d-flex flex-wrap gap-2 small">
                    {["main", "planner", "speech_to_text", "text_to_speech"].map((role) => (
                      <Form.Check key={role} inline type="checkbox" name="packRoles" value={role} label={titleize(role)} defaultChecked={role === "main"} />
                    ))}
                  </div>
                </Form>
                {packItems.length ? packItems.map((pack) => (
                  <div key={pack.packId} className="d-flex align-items-center justify-content-between gap-2 border-bottom py-2">
                    <div>
                      <strong className="small">{pack.packId}</strong>
                      <div className="text-body-secondary small">v{pack.version} · {(pack.pack?.entries || []).length} roles</div>
                    </div>
                    <Badge bg="secondary">Broker only</Badge>
                  </div>
                )) : <p className="small text-body-secondary mb-0">No saved packs yet.</p>}
                {voiceRoles.length > 0 && (
                  <div className="mt-3 small text-body-secondary"><Mic size={14} className="me-1" />Voice roles: {voiceRoles.map(titleize).join(", ")}</div>
                )}
                <div className="border-top mt-3 pt-3" data-testid="assistant-voice-loop">
                  <SectionHeader title="Voice loop readiness" text="Preview transcribe → reason → synthesize routing without opening a microphone or speaker." />
                  <div className="d-flex align-items-center justify-content-between gap-2">
                    <Badge bg={voicePreview ? (voicePreview.ready ? "success" : "warning") : "secondary"}>
                      {voicePreview ? (voicePreview.ready ? "Ready for adapter" : "Models needed") : "Not checked"}
                    </Badge>
                    <Button size="sm" variant="outline-primary" onClick={() => previewVoice(packItems[0]?.packId || "")}>Check readiness</Button>
                  </div>
                  {voicePreview && (
                    <div className="mt-2 small">
                      <div className="d-flex flex-wrap gap-2">
                        {(voicePreview.stages || []).map((stage) => <Badge key={stage.stage} bg={statusVariant(stage.status)}>{titleize(stage.stage)}: {titleize(stage.status)}</Badge>)}
                      </div>
                      {(voicePreview.blockers || []).length > 0 && <div className="text-danger mt-2">Blocked: {voicePreview.blockers.join(", ")}</div>}
                      <div className="text-body-secondary mt-2"><ShieldCheck size={13} className="me-1" />Audio I/O started: {voicePreview.execution?.audioIoStarted ? "yes" : "no"}</div>
                    </div>
                  )}
                </div>
              </Card.Body>
            </Card>
          </Col>

          <Col xl={7}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-plan-ledger">
              <Card.Body>
                <SectionHeader title="Plan ledger" text="Review plans before any future broker adapter can act on them." />
                {planItems.length ? planItems.map((record) => {
                  const plan = record.plan || {};
                  const operations = plan.localControl?.operations || [];
                  return (
                    <div key={record.id} className="border-bottom py-3" data-testid={`assistant-plan-${record.id}`}>
                      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2">
                        <div>
                          <strong>{plan.objective || "Assistant plan"}</strong>
                          <div className="small text-body-secondary">{record.id} · {plan.modelPackSource || "inline"} model pack</div>
                        </div>
                        <Badge bg={statusVariant(record.status)}>{titleize(record.status)}</Badge>
                      </div>
                      {(plan.blockers || []).length > 0 && <div className="small text-danger mt-2">Blocked: {plan.blockers.join(", ")}</div>}
                      <div className="d-flex flex-wrap gap-2 mt-2">
                        {record.status === "preview" && !(plan.blockers || []).length > 0 && <Button size="sm" variant="success" onClick={() => reviewPlan(record.id, "approved")}><CheckCircle2 size={13} className="me-1" />Approve review</Button>}
                        {record.status === "preview" && <Button size="sm" variant="outline-danger" onClick={() => reviewPlan(record.id, "rejected")}><XCircle size={13} className="me-1" />Reject</Button>}
                        {record.status === "approved" && operations.filter((operation) => operation.status === "planned").map((operation) => (
                          <Button key={operation.operation} size="sm" variant="outline-primary" onClick={() => requestHandoff(record.id, operation.operation)}>
                            <Link2 size={13} className="me-1" />Handoff {operation.label || titleize(operation.operation)}
                          </Button>
                        ))}
                      </div>
                    </div>
                  );
                }) : <p className="small text-body-secondary mb-0">No plans yet. Create a preview above.</p>}
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Card className="settings-card shadow-sm mt-3" data-testid="assistant-handoffs">
          <Card.Body>
            <SectionHeader title="Broker handoffs" text="Track the action state before Rasputin invokes an allowlisted local adapter." />
            {handoffItems.length ? handoffItems.map((handoff) => (
              <div key={handoff.id} className="d-flex flex-wrap align-items-center justify-content-between gap-2 border-bottom py-2" data-testid={`assistant-handoff-${handoff.id}`}>
                <div className="d-flex align-items-center gap-2">
                  {handoff.actionState === "failed" ? <XCircle size={16} className="text-danger" aria-hidden="true" /> : ["approved", "prepared", "completed"].includes(handoff.actionState) ? <CheckCircle2 size={16} className="text-success" aria-hidden="true" /> : <Clock3 size={16} className="text-warning" aria-hidden="true" />}
                  <span>
                    <strong>{titleize(handoff.operation)}</strong> <span className="small text-body-secondary">· {handoff.id}</span>
                    {brokerOperationMetadata[handoff.operation]?.sideEffects && <Badge bg="warning" text="dark" className="ms-2">Host action</Badge>}
                  </span>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <Badge bg={statusVariant(handoff.actionState || handoff.brokerStatus)}>{titleize(handoff.actionState || handoff.brokerStatus)}</Badge>
                  {handoff.brokerStatus === "approved_for_broker" && <Button size="sm" variant="outline-primary" onClick={() => prepareHandoff(handoff.id)}>Prepare broker</Button>}
                  {handoff.brokerStatus === "ready_for_broker" && handoff.operation === "docker_status" && <Button size="sm" variant="outline-success" onClick={() => dispatchHandoff(handoff.id, handoff.operation)}>Inspect Docker</Button>}
                  {handoff.brokerStatus === "ready_for_broker" && handoff.operation === "open_vscode" && <Button size="sm" variant="outline-warning" onClick={() => dispatchHandoff(handoff.id, handoff.operation)}>Open VS Code</Button>}
                </div>
              </div>
            )) : <p className="small text-body-secondary mb-0"><Volume2 size={14} className="me-1" />No broker handoffs requested.</p>}
          </Card.Body>
        </Card>
      </div>
    </section>
  );
}
