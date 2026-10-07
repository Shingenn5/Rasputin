import React, { useEffect, useState } from "react";
import { Badge, Button, Card, Col, Form, Row, Stack } from "react-bootstrap";
import { PageHeader, formatRuntimeTime } from "./RuntimePrimitives.jsx";

export function MemoryView({
  view,
  workspace,
  memoryItems,
  memoryExpiredItems,
  memoryReview,
  memorySearchResults,
  addMemory,
  updateMemory,
  deleteMemory,
  searchMemory,
  approveMemory,
  rejectMemory,
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("fact");
  const [scope, setScope] = useState("global");
  const [workspaceId, setWorkspaceId] = useState(workspace?.activePath || "");
  const [value, setValue] = useState("");
  const [sensitive, setSensitive] = useState(false);
  const [retention, setRetention] = useState("persistent");
  const [memoryError, setMemoryError] = useState("");
  const [editingId, setEditingId] = useState("");
  const [editingValue, setEditingValue] = useState("");
  const [editingRetention, setEditingRetention] = useState("persistent");
  const pending = memoryReview?.items || [];
  const saved = memoryItems?.items || [];
  const expired = memoryExpiredItems?.items || [];

  useEffect(() => {
    if (!workspaceId && workspace?.activePath) setWorkspaceId(workspace.activePath);
  }, [workspace?.activePath, workspaceId]);

  async function submitMemory(event) {
    event.preventDefault();
    setMemoryError("");
    try {
      await addMemory({
        kind,
        value,
        scope,
        workspaceId: scope === "workspace" ? workspaceId : null,
        sensitive,
        retention,
      });
      setValue("");
      setSensitive(false);
      setRetention("persistent");
    } catch (error) {
      setMemoryError(error.message);
    }
  }

  function beginEdit(item) {
    setEditingId(item.id);
    setEditingValue(formatMemoryContent(item.content));
    setEditingRetention(item.retention || "persistent");
    setMemoryError("");
  }

  async function saveEdit(item) {
    setMemoryError("");
    try {
      await updateMemory(item.id, { value: editingValue, retention: editingRetention });
      setEditingId("");
      setEditingValue("");
      setEditingRetention("persistent");
    } catch (error) {
      setMemoryError(error.message);
    }
  }

  async function restoreMemory(item) {
    setMemoryError("");
    try {
      await updateMemory(item.id, { retention: "persistent" });
    } catch (error) {
      setMemoryError(error.message);
    }
  }

  async function removeMemory(item) {
    if (!window.confirm("Delete this saved memory? This cannot be undone.")) return;
    setMemoryError("");
    try {
      await deleteMemory(item.id);
      if (editingId === item.id) setEditingId("");
    } catch (error) {
      setMemoryError(error.message);
    }
  }

  return (
    <section className={`app-view ${view === "memory" ? "active" : ""}`} id="memoryView" data-app-view="memory">
      <PageHeader title="Memory" text="Durable owner-scoped recall with explicit review, editing, and deletion." />
      <div className="task-dashboard">
        <Card className="settings-card shadow-sm" data-testid="memory-create-card">
          <Card.Body>
            <h2>Save a memory</h2>
            <p className="text-body-secondary">Keep a preference, fact, or project lesson across future conversations.</p>
            <Form onSubmit={submitMemory} data-testid="memory-create-form">
              <Row className="g-2">
                <Col md={5}>
                  <Form.Label htmlFor="memoryValue">Memory</Form.Label>
                  <Form.Control
                    id="memoryValue"
                    as="textarea"
                    rows={2}
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    placeholder="Example: Prefer concise status summaries."
                    required
                  />
                </Col>
                <Col md={2}>
                  <Form.Label htmlFor="memoryKind">Type</Form.Label>
                  <Form.Select id="memoryKind" value={kind} onChange={(event) => setKind(event.target.value)}>
                    <option value="fact">Fact</option>
                    <option value="preference">Preference</option>
                    <option value="project_note">Project note</option>
                    <option value="workflow_lesson">Workflow lesson</option>
                    <option value="tool_lesson">Tool lesson</option>
                    <option value="blocked_pattern">Blocked pattern</option>
                  </Form.Select>
                </Col>
                <Col md={2}>
                  <Form.Label htmlFor="memoryScope">Scope</Form.Label>
                  <Form.Select id="memoryScope" value={scope} onChange={(event) => setScope(event.target.value)}>
                    <option value="global">All workspaces</option>
                    <option value="workspace">This workspace</option>
                  </Form.Select>
                </Col>
                <Col md={3}>
                  <Form.Label htmlFor="memoryWorkspace">Workspace reference</Form.Label>
                  <Form.Control
                    id="memoryWorkspace"
                    value={workspaceId}
                    onChange={(event) => setWorkspaceId(event.target.value)}
                    disabled={scope !== "workspace"}
                    placeholder={workspace?.activePath || "."}
                  />
                </Col>
              </Row>
              <Row className="g-2 mt-1">
                <Col md={3}>
                  <Form.Label htmlFor="memoryRetention">Retention</Form.Label>
                  <Form.Select id="memoryRetention" value={retention} onChange={(event) => setRetention(event.target.value)}>
                    <option value="persistent">Persistent</option>
                    <option value="7_days">Expire after 7 days</option>
                    <option value="30_days">Expire after 30 days</option>
                    <option value="90_days">Expire after 90 days</option>
                  </Form.Select>
                </Col>
              </Row>
              <div className="d-flex align-items-center gap-3 mt-3">
                <Form.Check
                  id="memorySensitive"
                  type="checkbox"
                  label="Sensitive (excluded from normal context previews)"
                  checked={sensitive}
                  onChange={(event) => setSensitive(event.target.checked)}
                />
                <Button type="submit" data-testid="memory-add-button">Save memory</Button>
              </div>
            </Form>
            {memoryError && <div className="text-danger mt-3" role="alert">{memoryError}</div>}
          </Card.Body>
        </Card>
        <Card className="settings-card shadow-sm">
          <Card.Body>
            <Form onSubmit={(event) => { event.preventDefault(); searchMemory(query); }}>
              <Row className="g-2">
                <Col><Form.Control value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search saved memory" /></Col>
                <Col xs="auto"><Button type="submit">Search</Button></Col>
              </Row>
            </Form>
            {memorySearchResults?.query && (
              <div className="border rounded p-3 mt-3" data-testid="memory-recall-explainer">
                <div className="section-row">
                  <div>
                    <h2 className="h5 mb-1">Why these memories were returned</h2>
                    <p className="text-body-secondary mb-0">
                      Query: <code>{memorySearchResults.query}</code>
                    </p>
                  </div>
                  <Badge bg="secondary">{memorySearchResults.items?.length || 0} eligible</Badge>
                </div>
                <p className="small text-body-secondary mt-2 mb-0">
                  Results are limited to your owner-scoped memory. Global items are eligible everywhere;
                  workspace items are eligible only when they match the active workspace
                  {memorySearchResults.workspaceId ? ` (${memorySearchResults.workspaceId})` : ""}.
                  Open “Why was this recalled?” on a result for matched terms and ranking factors.
                </p>
                {!memorySearchResults.items?.length && (
                  <p className="small text-body-secondary mt-2 mb-0">No saved memory matched the query and workspace policy.</p>
                )}
              </div>
            )}
            <Stack gap={2} className="mt-3">
              {(memorySearchResults?.items || []).map((item) => <MemoryItem key={item.id} item={item} />)}
            </Stack>
          </Card.Body>
        </Card>
        <Card className="settings-card shadow-sm mt-3" data-testid="memory-saved-list">
          <Card.Body>
            <h2>Saved memory</h2>
            <Stack gap={2}>
              {saved.map((item) => (
                <Card className="message-card" key={item.id}>
                  <Card.Body>
                    {editingId === item.id ? (
                      <>
                        <Form.Label htmlFor={`memory-edit-${item.id}`}>Edit memory</Form.Label>
                        <Form.Control
                          id={`memory-edit-${item.id}`}
                          as="textarea"
                          rows={3}
                          value={editingValue}
                          onChange={(event) => setEditingValue(event.target.value)}
                        />
                        <Form.Label className="mt-2" htmlFor={`memory-retention-${item.id}`}>Retention</Form.Label>
                        <Form.Select
                          id={`memory-retention-${item.id}`}
                          value={editingRetention}
                          onChange={(event) => setEditingRetention(event.target.value)}
                        >
                          <option value="persistent">Persistent</option>
                          <option value="7_days">Expire after 7 days</option>
                          <option value="30_days">Expire after 30 days</option>
                          <option value="90_days">Expire after 90 days</option>
                        </Form.Select>
                        <Stack direction="horizontal" gap={2} className="mt-2">
                          <Button size="sm" onClick={() => saveEdit(item)} data-testid={`memory-save-edit-${item.id}`}>Save changes</Button>
                          <Button size="sm" variant="outline-secondary" onClick={() => setEditingId("")}>Cancel</Button>
                        </Stack>
                      </>
                    ) : (
                      <>
                        <MemoryItem item={item} />
                        <Stack direction="horizontal" gap={2} className="mt-2">
                          <Button size="sm" variant="outline-secondary" onClick={() => beginEdit(item)} data-testid={`memory-edit-${item.id}`}>Edit</Button>
                          <Button size="sm" variant="outline-danger" onClick={() => removeMemory(item)} data-testid={`memory-delete-${item.id}`}>Delete</Button>
                        </Stack>
                      </>
                    )}
                  </Card.Body>
                </Card>
              ))}
              {!saved.length && <p className="text-body-secondary mb-0">No saved memories yet.</p>}
            </Stack>
          </Card.Body>
        </Card>
        <Card className="settings-card shadow-sm mt-3" data-testid="memory-expired-list">
          <Card.Body>
            <h2>Expired memory</h2>
            <p className="text-body-secondary">Expired records stay visible for audit and can be restored as persistent memory.</p>
            <Stack gap={2}>
              {expired.map((item) => (
                <Card className="message-card" key={item.id}>
                  <Card.Body>
                    <MemoryItem item={item} />
                    <Stack direction="horizontal" gap={2} className="mt-2">
                      <Button size="sm" onClick={() => restoreMemory(item)}>Restore persistently</Button>
                      <Button size="sm" variant="outline-danger" onClick={() => removeMemory(item)} data-testid={`memory-delete-expired-${item.id}`}>Delete</Button>
                    </Stack>
                  </Card.Body>
                </Card>
              ))}
              {!expired.length && <p className="text-body-secondary mb-0">No expired memories.</p>}
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

function MemoryItem({ item }) {
  const workspaceId = item.workspaceId || item.workspace_id;
  const scope = item.scope === "workspace" ? `Workspace: ${workspaceId || "unknown"}` : "Global";
  const recallCount = Number(item.recallCount ?? item.recall_count ?? 0);
  const retention = item.retention || "persistent";
  const expiresAt = item.expiresAt ?? item.expires_at;
  const sourceTask = item.sourceTaskId || item.source_task_id;
  const sourceSession = item.sourceSessionId || item.source_session_id;
  const sourceMessages = item.sourceMessageIds || item.source_message_ids || [];
  const supersedes = item.supersedesId || item.supersedes_id;
  const recallExplanation = item.recallExplanation || item.recall_explanation;
  const statusTone = item.status === "pending" ? "warning" : item.status === "expired" ? "danger" : item.status === "superseded" ? "dark" : "secondary";
  const badgeLabel = item.status === "expired" || item.status === "superseded" ? item.status : item.kind;
  return (
    <div>
      <Badge bg={statusTone}>{badgeLabel}</Badge>
      <span className="small text-body-secondary ms-2">{scope}</span>
      <p className="mb-0 mt-2">{formatMemoryContent(item.content)}</p>
      <div className="small text-body-secondary mt-2">
        Confidence {Math.round(Number(item.confidence ?? 0.5) * 100)}% · Importance {Math.round(Number(item.importance ?? 0.5) * 100)}% · Recalled {recallCount} times
        {item.sensitive && " · Sensitive"}
        {retention !== "persistent" && ` · ${retention.replace("_", " ")}`}
        {expiresAt && ` · Expires ${formatRuntimeTime(expiresAt)}`}
      </div>
      {(sourceTask || sourceSession || sourceMessages.length) && (
        <div className="small text-body-secondary mt-1">
          Source: {sourceTask ? `task ${sourceTask}` : "manual"}
          {sourceSession ? ` · session ${sourceSession}` : ""}
          {sourceMessages.length ? ` · ${sourceMessages.length} message${sourceMessages.length === 1 ? "" : "s"}` : ""}
        </div>
      )}
      {recallExplanation && <MemoryRecallExplanation item={item} explanation={recallExplanation} />}
      {supersedes && (
        <div className="small text-body-secondary mt-1">
          Correction of memory {supersedes}
        </div>
      )}
    </div>
  );
}

function MemoryRecallExplanation({ item, explanation }) {
  const matchedTerms = explanation.matchedTerms || explanation.matched_terms || [];
  const scopeReason = explanation.scopeReason || explanation.scope_reason;
  const score = explanation.score;
  const importance = explanation.importance;
  return (
    <details className="small mt-2" data-testid={`memory-recall-details-${item.id}`}>
      <summary className="text-body-secondary">Why was this recalled?</summary>
      <div className="border rounded p-2 mt-2" data-testid="memory-recall-explanation">
        <p className="mb-2">{explanation.summary || "Matched the query and passed the owner/workspace policy."}</p>
        <dl className="detail-grid mb-0">
          <dt>Matched terms</dt><dd>{matchedTerms.length ? matchedTerms.join(", ") : "Query match"}</dd>
          <dt>Scope rule</dt><dd>{scopeReason || "Owner/workspace policy allowed this memory."}</dd>
          <dt>Relevance score</dt><dd>{score == null ? "Unavailable" : Number(score).toFixed(3)}</dd>
          <dt>Importance</dt><dd>{importance == null ? "Unavailable" : `${Math.round(Number(importance) * 100)}%`}</dd>
        </dl>
      </div>
    </details>
  );
}

function formatMemoryContent(content) {
  return typeof content === "string" ? content : JSON.stringify(content, null, 2);
}
