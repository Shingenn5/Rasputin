import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Row, Stack } from "react-bootstrap";
import { displayWorkspaceName, labelize } from "../../lib/display.js";

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

export function SessionsView({
  view,
  sessions,
  chatFolders,
  activeChatFolder,
  setActiveChatFolder,
  selectedSession,
  loadSession,
  resumeSession,
  createChatFolder,
  assignSessionFolder,
  createSkillFromSession,
}) {
  const folders = chatFolders?.folders || [];
  const sessionItems = sessions?.sessions || [];
  const filteredSessions = sessionItems.filter((session) => {
    if (activeChatFolder === "all") return true;
    if (activeChatFolder === "unfiled") return !session.folder;
    return session.folder === activeChatFolder;
  });
  return (
    <section className={`app-view ${view === "sessions" ? "active" : ""}`} id="sessionsView" data-app-view="sessions">
      <PageHeader title="Sessions" text="Persistent conversations, chat folders, and task history stored locally in SQLite." />
      <div className="task-dashboard">
        <Row className="g-3">
          <Col lg={4}>
            <Card className="settings-card shadow-sm h-100">
              <Card.Body>
                <div className="section-row">
                  <div>
                    <h2>Chat Folders</h2>
                    <p className="text-body-secondary mb-0">Organize conversations without moving message data.</p>
                  </div>
                </div>
                <form className="chat-folder-create" data-testid="chat-folder-create" onSubmit={createChatFolder}>
                  <Form.Label htmlFor="chatFolderName">New folder</Form.Label>
                  <div>
                    <Form.Control id="chatFolderName" name="name" placeholder="Writing, Coding, Research" />
                    <Button type="submit">Create</Button>
                  </div>
                </form>
                <div className="chat-folder-list" data-testid="chat-folder-list" aria-label="Chat folders">
                  <button type="button" className={activeChatFolder === "all" ? "is-active" : ""} onClick={() => setActiveChatFolder?.("all")}>
                    <span>All chats</span>
                    <small>{sessionItems.length}</small>
                  </button>
                  <button type="button" className={activeChatFolder === "unfiled" ? "is-active" : ""} onClick={() => setActiveChatFolder?.("unfiled")}>
                    <span>Unfiled</span>
                    <small>{chatFolders?.unfiledCount || 0}</small>
                  </button>
                  {folders.map((folder) => (
                    <button key={folder.id} type="button" className={activeChatFolder === folder.name ? "is-active" : ""} onClick={() => setActiveChatFolder?.(folder.name)}>
                      <span>{folder.name}</span>
                      <small>{folder.sessionCount || 0}</small>
                    </button>
                  ))}
                </div>

                <h2 className="mt-4">Chats</h2>
                <ListGroup className="runtime-list">
                  {filteredSessions.map((session) => (
                    <ListGroup.Item key={session.id} className="session-list-item">
                      <button type="button" className="session-open-button" onClick={() => loadSession(session.id)}>
                        <strong>{session.title}</strong>
                        <small>{session.status} / {session.mode} / {displayWorkspaceName(session.workspace)}</small>
                      </button>
                      <Form.Select
                        size="sm"
                        aria-label={`Move ${session.title} to folder`}
                        value={session.folder || ""}
                        onChange={(event) => assignSessionFolder?.(session.id, event.target.value || null)}
                      >
                        <option value="">Unfiled</option>
                        {folders.map((folder) => <option key={folder.id} value={folder.name}>{folder.name}</option>)}
                      </Form.Select>
                    </ListGroup.Item>
                  ))}
                  {!filteredSessions.length && (
                    <ListGroup.Item className="text-body-secondary">No chats in this folder.</ListGroup.Item>
                  )}
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
                    <p className="text-body-secondary mb-0">
                      {selectedSession?.session
                        ? `${sessionFolderName(selectedSession.session.folder)} / ${displayWorkspaceName(selectedSession.session.workspace)}`
                        : "Review messages, tasks, and saved context."}
                    </p>
                  </div>
                  {selectedSession?.session && (
                    <Stack direction="horizontal" gap={2}>
                      <Button variant="outline-secondary" onClick={() => resumeSession?.(selectedSession.session.id)}>Resume Chat</Button>
                      <Button variant="outline-secondary" onClick={() => createSkillFromSession(selectedSession.session.id)}>Preview Skill</Button>
                    </Stack>
                  )}
                </div>
                {selectedSession?.session && (
                  <div className="session-folder-control mt-3">
                    <Form.Label htmlFor="selectedSessionFolder">Folder</Form.Label>
                    <Form.Select
                      id="selectedSessionFolder"
                      value={selectedSession.session.folder || ""}
                      onChange={(event) => assignSessionFolder?.(selectedSession.session.id, event.target.value || null)}
                    >
                      <option value="">Unfiled</option>
                      {folders.map((folder) => <option key={folder.id} value={folder.name}>{folder.name}</option>)}
                    </Form.Select>
                  </div>
                )}
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

export function WarsatView({
  view,
  warsat,
  hardware,
  runtimes,
  plan,
  error,
  createPlan,
  deployPlan,
  deploying,
  deployment,
  operation,
  logs,
  loadLogs,
  runtimeAction,
  approvals,
  approveApproval,
  denyApproval,
  clearPlan,
  refresh,
  modelCatalog,
  modelCatalogLoading,
  modelCatalogError,
  loadModelCatalog,
  prepareCatalogModelForWarsat,
}) {
  const protocols = warsat?.protocols || [];
  const strengthProfiles = warsat?.strengthProfiles || {};
  const containers = runtimes?.containers || [];
  const catalogItems = modelCatalog?.items || [];
  const catalogCategories = modelCatalog?.categories || [];
  const firstProtocol = protocols[0];
  const [protocolId, setProtocolId] = useState(firstProtocol?.id || "");
  const [strengthProfile, setStrengthProfile] = useState("balanced");
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogPurpose, setCatalogPurpose] = useState("all");
  const [selectedCatalogId, setSelectedCatalogId] = useState(catalogItems[0]?.id || "");
  const selectedProtocol = protocols.find((protocol) => protocol.id === protocolId) || firstProtocol;
  const selectedProfile = strengthProfiles[strengthProfile] || strengthProfiles.balanced || {};
  const warsatCatalogItems = useMemo(() => {
    const search = catalogSearch.trim().toLowerCase();
    return catalogItems
      .filter((item) => item.deployable)
      .filter((item) => catalogPurpose === "all" || item.purpose === catalogPurpose)
      .filter((item) => {
        if (!search) return true;
        return [
          item.name,
          item.id,
          item.modelId,
          item.provider,
          item.purpose,
          ...(item.capabilities || []),
        ].join(" ").toLowerCase().includes(search);
      });
  }, [catalogItems, catalogPurpose, catalogSearch]);
  const selectedCatalogModel = warsatCatalogItems.find((item) => item.id === selectedCatalogId)
    || warsatCatalogItems[0]
    || null;
  const recipeCount = protocols.length * Math.max(Object.keys(strengthProfiles).length, 1);
  const canDeployPlan = !!plan?.executionEnabled && !!plan?.dockerControlEnabled && !!plan?.dockerCliAvailable;
  const deploymentApprovalId = deployment?.approval?.id || deployment?.approvalId;
  const currentApproval = (approvals?.approvals || []).find((item) => item.id === deploymentApprovalId) || deployment?.approval;
  const approvalStatus = currentApproval?.status;
  const approvalPending = deployment?.approvalRequired && (!approvalStatus || approvalStatus === "pending");
  const approvalApproved = deployment?.approvalRequired && approvalStatus === "approved";
  const approvalClosed = deployment?.approvalRequired && ["denied", "expired", "executed"].includes(approvalStatus);
  const approvalReady = !deployment?.approvalRequired || approvalApproved;
  const deployDisabled = !canDeployPlan || deploying || !approvalReady || approvalClosed;
  const lifecycle = deployment?.lifecycle || plan?.lifecycle || [];
  const deploymentFailed = deployment?.status === "failed";
  const deploymentRegistered = deployment?.status === "registered";
  const deployLabel = deploying
    ? "Deploying..."
    : deployment?.approvalRequired
      ? approvalStatus === "approved" ? "Run approved deploy" : approvalClosed ? "Approval closed" : "Waiting for approval"
      : deploymentFailed ? "Request retry approval"
      : deploymentRegistered ? "Request redeploy approval"
      : "Request deploy approval";
  const operationApproval = (approvals?.approvals || []).find((item) => item.id === (operation?.approval?.id || operation?.approvalId)) || operation?.approval;

  useEffect(() => {
    if (!protocolId && firstProtocol?.id) setProtocolId(firstProtocol.id);
  }, [firstProtocol?.id, protocolId]);

  function handleFormChange() {
    if (plan || error) clearPlan?.();
  }

  async function handleCreatePlan(event) {
    await createPlan(event);
  }

  return (
    <section className={`app-view ${view === "warsat" ? "active" : ""}`} id="warsatView" data-app-view="warsat" data-testid="warsat-view">
      <PageHeader
        title="Warsat"
        text="Runtime recipes for local model containers. Generate plans first; execution stays approval-gated."
        action={<Button variant="outline-secondary" size="sm" onClick={refresh}>Refresh Protocols</Button>}
      />
      <div className={`task-dashboard warsat-dashboard ${plan ? "has-plan" : ""}`}>
        <div className="warsat-summary-strip" aria-label="Warsat runtime status">
          <SummaryTile title="Runtime recipes" value={recipeCount || protocols.length} />
          <SummaryTile title="Managed containers" value={containers.length} />
          <SummaryTile title="Docker control" value={warsat?.dockerControlEnabled ? "Enabled" : "Off"} />
          <SummaryTile title="Execution" value={warsat?.executionEnabled ? "Enabled" : "Plan only"} />
        </div>

        <WarsatHardwarePanel hardware={hardware} refresh={refresh} />

        <Card className="settings-card warsat-panel warsat-model-finder shadow-sm" data-testid="warsat-model-finder">
          <Card.Body>
            <div className="section-row align-items-start">
              <div>
                <h2>Find A Model</h2>
                <p className="text-body-secondary mb-0">
                  Search deployable catalog entries and create a Warsat launch plan without leaving this screen.
                </p>
              </div>
              <Stack direction="horizontal" gap={2} className="warsat-model-finder-actions">
                <Button variant="outline-secondary" size="sm" onClick={() => loadModelCatalog?.(false)}>
                  Local catalog
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => loadModelCatalog?.(true)}
                  disabled={modelCatalogLoading}
                  data-testid="warsat-catalog-refresh"
                >
                  {modelCatalogLoading ? "Refreshing..." : "Refresh models.dev"}
                </Button>
              </Stack>
            </div>
            <div className="warsat-model-finder-meta" role="status">
              <span>{warsatCatalogItems.length} deployable shown</span>
              <span>{modelCatalog?.count || catalogItems.length || 0} catalog entries</span>
              <span>Source: {modelCatalog?.source?.status || "local fallback"}</span>
              {modelCatalogError && <strong>{modelCatalogError}</strong>}
            </div>
            <div className="warsat-model-finder-grid">
              <aside className="warsat-model-filters" aria-label="Warsat model filters">
                <label>
                  <span>Search</span>
                  <input
                    value={catalogSearch}
                    onChange={(event) => setCatalogSearch(event.target.value)}
                    placeholder="qwen, coder, 7b, vision"
                  />
                </label>
                <label>
                  <span>Use</span>
                  <select value={catalogPurpose} onChange={(event) => setCatalogPurpose(event.target.value)}>
                    <option value="all">All deployable</option>
                    {catalogCategories.map((category) => (
                      <option key={category.id} value={category.id}>{category.label}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="ras-button ghost"
                  onClick={() => {
                    setCatalogSearch("");
                    setCatalogPurpose("all");
                  }}
                >
                  Clear
                </button>
              </aside>
              <div className="warsat-model-result-list" aria-label="Deployable model results">
                {warsatCatalogItems.slice(0, 24).map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={`warsat-model-result ${selectedCatalogModel?.id === item.id ? "is-selected" : ""}`}
                    onClick={() => setSelectedCatalogId(item.id)}
                    data-testid="warsat-catalog-card"
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.modelId || item.id}</small>
                    </span>
                    <span className="warsat-model-result-tags">
                      <em>{labelize(item.purpose || "chat")}</em>
                      <em>{item.vramEstimateGb ? `${item.vramEstimateGb} GB` : "VRAM unknown"}</em>
                      <em>{item.recommendedProtocol || "Warsat"}</em>
                    </span>
                  </button>
                ))}
                {!warsatCatalogItems.length && (
                  <p className="workspace-help-text mb-0">
                    No deployable models match the current filters. Refresh models.dev or clear the filter.
                  </p>
                )}
              </div>
              <aside className="warsat-model-selected" aria-label="Selected deployable model">
                {selectedCatalogModel ? (
                  <>
                    <span className="eyebrow">{selectedCatalogModel.source || "catalog"}</span>
                    <h3>{selectedCatalogModel.name}</h3>
                    <p>{selectedCatalogModel.summary || "No summary available."}</p>
                    <dl className="detail-grid mb-0">
                      <dt>Model</dt><dd>{selectedCatalogModel.modelId || selectedCatalogModel.id}</dd>
                      <dt>Use</dt><dd>{labelize(selectedCatalogModel.purpose || "chat")}</dd>
                      <dt>Profile</dt><dd>{selectedCatalogModel.recommendedProfile || "balanced"}</dd>
                      <dt>Runtime</dt><dd>{selectedCatalogModel.recommendedProtocol || "vllmCudaOpenai"}</dd>
                    </dl>
                    <Button
                      type="button"
                      variant="primary"
                      onClick={() => prepareCatalogModelForWarsat?.(selectedCatalogModel)}
                      data-testid="warsat-catalog-create-plan"
                    >
                      Create Warsat plan
                    </Button>
                  </>
                ) : (
                  <p className="workspace-help-text mb-0">Select a deployable catalog model.</p>
                )}
              </aside>
            </div>
          </Card.Body>
        </Card>

        <Card className="settings-card warsat-panel shadow-sm">
          <Card.Body>
            <div className="section-row align-items-start">
              <div>
                <h2>Managed Runtimes</h2>
                <p className="text-body-secondary mb-0">
                  Containers started by Warsat appear here. Stop and restart are approval-gated because they change local runtime state.
                </p>
              </div>
              <Button variant="outline-secondary" size="sm" onClick={refresh}>Refresh</Button>
            </div>
            {!runtimes?.executionEnabled && (
              <p className="warsat-runtime-message mt-3 mb-0" role="status">
                {runtimes?.message || "Start Rasputin with Docker control and enable it in Safety settings to manage containers."}
              </p>
            )}
            {!!containers.length && (
              <div className="warsat-runtime-list mt-3" data-testid="warsat-runtime-list">
                {containers.map((container) => (
                  <article className="warsat-runtime-card" key={container.name || container.id}>
                    <div>
                      <strong>{container.name || "Unnamed container"}</strong>
                      <span>{container.image || "Unknown image"}</span>
                    </div>
                    <dl className="detail-grid mb-0">
                      <dt>Status</dt><dd>{container.status || container.state || "unknown"}</dd>
                      <dt>Runtime</dt><dd>{container.runtime || "unknown"}</dd>
                      <dt>Protocol</dt><dd>{container.protocolId || "unknown"}</dd>
                      <dt>Ports</dt><dd>{container.ports || "none"}</dd>
                    </dl>
                    <div className="warsat-runtime-actions">
                      <Button size="sm" variant="outline-secondary" onClick={() => loadLogs?.(container.name)}>Logs</Button>
                      <OperationButton
                        action="stop"
                        containerName={container.name}
                        operation={operation}
                        approval={operationApproval}
                        runtimeAction={runtimeAction}
                      />
                      <OperationButton
                        action="restart"
                        containerName={container.name}
                        operation={operation}
                        approval={operationApproval}
                        runtimeAction={runtimeAction}
                      />
                    </div>
                  </article>
                ))}
              </div>
            )}
            {!containers.length && (
              <p className="text-body-secondary mt-3 mb-0">No Warsat-managed model containers are currently visible.</p>
            )}
            {logs && (
              <details className="advanced-block mt-3" open>
                <summary>Logs for {logs.containerName}</summary>
                <pre className="log-box mt-3 mb-0">{logs.logs || "No logs returned."}</pre>
              </details>
            )}
          </Card.Body>
        </Card>

        <Card className="settings-card warsat-panel shadow-sm">
          <Card.Body>
            <div className="section-row">
              <div>
                <h2>Launch Recipe</h2>
                <p className="text-body-secondary mb-0">
                  Pick a runtime, choose the hardware profile, then override the specific Docker and model-server settings you care about.
                </p>
              </div>
              <span className="warsat-approval-pill">Approval required before deploy</span>
            </div>
            {warsat?.message && (
              <p className="warsat-runtime-message mt-3 mb-0" role="status">{warsat.message}</p>
            )}
            <Form className="mt-3 warsat-plan-form" data-testid="warsat-plan-form" onSubmit={handleCreatePlan} onChange={handleFormChange}>
              <div className="warsat-form-section">
                <div className="warsat-form-title">
                  <strong>Recipe source</strong>
                  <span>Choose the model server and the model reference it should expose.</span>
                </div>
                <Row className="g-3 align-items-start">
                  <Col xl={3} lg={6}>
                  <Form.Label htmlFor="warsatProtocolId">Protocol</Form.Label>
                  <Form.Select
                    id="warsatProtocolId"
                    name="protocolId"
                    value={protocolId}
                    onChange={(event) => setProtocolId(event.target.value)}
                    required
                  >
                    <option value="" disabled>Choose a protocol</option>
                    {protocols.map((protocol) => (
                      <option key={protocol.id} value={protocol.id}>{protocol.name}</option>
                    ))}
                  </Form.Select>
                  </Col>
                  <Col xl={3} lg={6}>
                  <Form.Label htmlFor="warsatModelRef">Model id</Form.Label>
                  <Form.Control id="warsatModelRef" name="modelRef" placeholder="Qwen/Qwen2.5-Coder-7B-Instruct" />
                  <Form.Text>Use this for vLLM or any Hugging Face based runtime.</Form.Text>
                  </Col>
                  <Col xl={3} lg={6}>
                  <Form.Label htmlFor="warsatModelPath">Mounted model path</Form.Label>
                  <Form.Control id="warsatModelPath" name="modelPath" placeholder="models/my-model.gguf" />
                  <Form.Text>Use this for GGUF protocols or mounted model folders.</Form.Text>
                  </Col>
                  <Col xl={3} lg={6}>
                  <Form.Label htmlFor="warsatHostPort">Host port</Form.Label>
                  <Form.Control id="warsatHostPort" name="hostPort" type="number" min="1024" max="65535" placeholder="Auto" />
                  <Form.Text>Leave blank to use the protocol default.</Form.Text>
                  </Col>
                  <Col md={3}>
                  <Form.Label htmlFor="warsatRole">Model role</Form.Label>
                  <Form.Select id="warsatRole" name="role" defaultValue={selectedProtocol?.defaultRole || "helper"} key={selectedProtocol?.id || "role"}>
                    <option value="main">Main model</option>
                    <option value="planner">Planner</option>
                    <option value="executor">Executor</option>
                    <option value="coder">Coder</option>
                    <option value="researcher">Researcher</option>
                    <option value="summarizer">Summarizer</option>
                    <option value="memory">Memory</option>
                    <option value="embeddings">Embeddings</option>
                    <option value="helper">Auxiliary</option>
                  </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label htmlFor="warsatContainerName">Container name</Form.Label>
                    <Form.Control id="warsatContainerName" name="containerName" placeholder="Auto" />
                  </Col>
                  <Col md={2} className="warsat-action-col">
                    <Button className="w-100" type="submit">Create plan</Button>
                    {(plan || error) && (
                      <Button className="w-100 mt-2" variant="outline-secondary" type="button" onClick={clearPlan}>
                        Clear plan
                      </Button>
                    )}
                  </Col>
                </Row>
              </div>

              <details className="warsat-tuning-panel" open>
                <summary>Hardware and runtime tuning</summary>
                <Row className="g-3 align-items-start mt-1">
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatStrengthProfile">Profile</Form.Label>
                    <Form.Select
                      id="warsatStrengthProfile"
                      name="strengthProfile"
                      value={strengthProfile}
                      onChange={(event) => setStrengthProfile(event.target.value)}
                    >
                    {Object.entries(strengthProfiles).map(([key, profile]) => (
                      <option key={key} value={key}>{profile.label || key}</option>
                    ))}
                    {!Object.keys(strengthProfiles).length && <option value="balanced">Balanced</option>}
                    </Form.Select>
                    <Form.Text>{selectedProfile.description || "Use profile defaults unless overridden."}</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatMaxModelLen">Max model length</Form.Label>
                    <Form.Control id="warsatMaxModelLen" name="maxModelLen" type="number" min="512" placeholder={selectedProfile.maxModelLen || 8192} />
                    <Form.Text>vLLM context ceiling.</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatContextWindow">GGUF context</Form.Label>
                    <Form.Control id="warsatContextWindow" name="contextWindow" type="number" min="512" placeholder={selectedProfile.contextWindow || 4096} />
                    <Form.Text>llama.cpp context size.</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatGpuMemoryUtilization">GPU utilization</Form.Label>
                    <Form.Control
                      id="warsatGpuMemoryUtilization"
                      name="gpuMemoryUtilization"
                      type="number"
                      min="0"
                      max="0.98"
                      step="0.01"
                      placeholder={selectedProfile.gpuMemoryUtilization ?? 0.82}
                    />
                    <Form.Text>vLLM VRAM fraction.</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatGpuLayers">GPU layers</Form.Label>
                    <Form.Control id="warsatGpuLayers" name="gpuLayers" type="number" min="0" placeholder={selectedProfile.gpuLayers ?? "auto"} />
                    <Form.Text>llama.cpp offload layers.</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatTensorParallelSize">Tensor parallel</Form.Label>
                    <Form.Control id="warsatTensorParallelSize" name="tensorParallelSize" type="number" min="1" max="16" placeholder="1" />
                    <Form.Text>Split vLLM across GPUs.</Form.Text>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatBatchSize">Batch size</Form.Label>
                    <Form.Control id="warsatBatchSize" name="batchSize" type="number" min="1" placeholder={selectedProfile.batchSize || 512} />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatMaxNumSeqs">Parallel sequences</Form.Label>
                    <Form.Control id="warsatMaxNumSeqs" name="maxNumSeqs" type="number" min="1" placeholder={selectedProfile.maxNumSeqs || 32} />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatDtype">Dtype</Form.Label>
                    <Form.Select id="warsatDtype" name="dtype" defaultValue="auto">
                      <option value="auto">Auto</option>
                      <option value="float16">float16</option>
                      <option value="bfloat16">bfloat16</option>
                      <option value="float32">float32</option>
                    </Form.Select>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatQuantization">Quantization</Form.Label>
                    <Form.Select id="warsatQuantization" name="quantization" defaultValue="">
                      <option value="">None / model default</option>
                      <option value="awq">AWQ</option>
                      <option value="gptq">GPTQ</option>
                      <option value="fp8">FP8</option>
                      <option value="bitsandbytes">bitsandbytes</option>
                    </Form.Select>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatKvCacheDtype">KV cache</Form.Label>
                    <Form.Select id="warsatKvCacheDtype" name="kvCacheDtype" defaultValue="auto">
                      <option value="auto">Auto</option>
                      <option value="fp8">FP8</option>
                      <option value="fp8_e5m2">FP8 E5M2</option>
                      <option value="fp8_e4m3">FP8 E4M3</option>
                    </Form.Select>
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatSwapSpaceGb">Swap space GB</Form.Label>
                    <Form.Control id="warsatSwapSpaceGb" name="swapSpaceGb" type="number" min="0" placeholder="0" />
                  </Col>
                </Row>
              </details>

              <details className="warsat-tuning-panel" open>
                <summary>Container limits</summary>
                <Row className="g-3 align-items-start mt-1">
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatMemoryLimitGb">Memory limit GB</Form.Label>
                    <Form.Control id="warsatMemoryLimitGb" name="memoryLimitGb" type="number" min="0" placeholder="No hard cap" />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatCpuLimit">CPU limit</Form.Label>
                    <Form.Control id="warsatCpuLimit" name="cpuLimit" type="number" min="0" step="0.25" placeholder="No hard cap" />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatCpuThreads">CPU threads</Form.Label>
                    <Form.Control id="warsatCpuThreads" name="cpuThreads" type="number" min="0" placeholder="Auto" />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatShmSizeGb">Shared memory GB</Form.Label>
                    <Form.Control id="warsatShmSizeGb" name="shmSizeGb" type="number" min="0" placeholder="2" />
                  </Col>
                  <Col lg={3} md={6}>
                    <Form.Label htmlFor="warsatGpuDevice">GPU device</Form.Label>
                    <Form.Control id="warsatGpuDevice" name="gpuDevice" placeholder="all, 0, 1, or none" />
                    <Form.Text>Optional NVIDIA_VISIBLE_DEVICES value.</Form.Text>
                  </Col>
                </Row>
              </details>
            </Form>
            {error && <p className="text-danger mt-3 mb-0" role="alert">{error}</p>}
          </Card.Body>
        </Card>

        <details className="warsat-library-panel">
          <summary>
            <span>Hardware profile presets</span>
            <small>{Object.keys(strengthProfiles).length || 0} presets. The selected preset is already applied in the Launch Recipe form.</small>
          </summary>
          <section className="warsat-profile-strip" aria-label="Warsat hardware profiles">
            {Object.entries(strengthProfiles).map(([key, profile]) => (
              <button
                className={`warsat-profile-card ${key === strengthProfile ? "is-selected" : ""}`}
                key={key}
                type="button"
                onClick={() => setStrengthProfile(key)}
              >
                <strong>{profile.label || key}</strong>
                <span>{profile.description}</span>
                <small>{profile.maxModelLen || profile.contextWindow} tokens / GPU {profile.gpuMemoryUtilization ?? "auto"}</small>
              </button>
            ))}
          </section>
        </details>

        <details className="warsat-library-panel">
          <summary>
            <span>Runtime protocol library</span>
            <small>{protocols.length} managed recipes. Use Models / Local Endpoint for servers you started yourself.</small>
          </summary>
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
                    {!!protocol.bestFor?.length && (
                      <div className="warsat-best-for mt-3">
                        {protocol.bestFor.map((item) => <span key={item}>{item}</span>)}
                      </div>
                    )}
                    <dl className="detail-grid mt-3 mb-0">
                      <dt>Image</dt><dd>{protocol.image}</dd>
                      <dt>Format</dt><dd>{protocol.modelFormat}</dd>
                      <dt>Default port</dt><dd>{protocol.defaultHostPort}</dd>
                      <dt>Minimum VRAM</dt><dd>{protocol.gpu?.minVramGb || 0} GB</dd>
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
        </details>

        {plan && (
          <Card className="settings-card warsat-plan-card shadow-sm mt-3" data-testid="warsat-launch-plan">
            <Card.Body>
              <div className="section-row">
                <div>
                  <span className="warsat-risk-pill">{plan.riskLevel}</span>
                  <h2 className="mt-2">{plan.protocolName}</h2>
                  <p className="text-body-secondary mb-0">
                    {plan.runtime} on port {plan.hostPort}. Execution is {plan.executionEnabled ? "enabled" : "disabled"}.
                  </p>
                </div>
                <Badge bg={plan.securityChecks?.localhostOnly ? "success" : "danger"}>
                  {plan.securityChecks?.localhostOnly ? "localhost only" : "review binding"}
                </Badge>
              </div>

              <div className="warsat-deploy-strip mt-3" role="region" aria-label="Warsat deployment controls">
                <div>
                  <strong>
                    {deployment?.approvalRequired
                      ? approvalClosed
                        ? `Approval ${approvalStatus}`
                        : `Approval ${approvalStatus || "pending"}`
                      : canDeployPlan
                        ? "Ready for approval"
                        : "Plan ready, execution unavailable"}
                  </strong>
                  <span>
                    {deployment?.approvalRequired
                      ? approvalStatus === "approved"
                        ? "Approval is ready. The next click will pull the image, start the container, and register the model."
                        : approvalClosed
                          ? "This approval can no longer be used. Clear the plan or request a new approval after reviewing the settings."
                          : `Approve code ${currentApproval?.code || "pending"} here or from Activity before Docker execution is allowed.`
                      : canDeployPlan
                        ? "The first click creates a redacted approval request. Docker will not run until that approval is approved."
                      : plan.dockerControlEnabled
                        ? "Restart Rasputin with the docker-control profile so the wrapper has Docker CLI access."
                        : "Enable Docker control in Safety settings before deploying model containers."}
                  </span>
                </div>
                <div className="warsat-deploy-actions">
                  {approvalPending && currentApproval?.id && (
                    <>
                      <Button
                        type="button"
                        variant="success"
                        onClick={() => approveApproval?.(currentApproval.id)}
                        data-testid="warsat-approve-deploy"
                      >
                        Approve deploy
                      </Button>
                      <Button
                        type="button"
                        variant="outline-danger"
                        onClick={() => denyApproval?.(currentApproval.id)}
                        data-testid="warsat-deny-deploy"
                      >
                        Deny
                      </Button>
                    </>
                  )}
                  <Button
                    type="button"
                    variant={canDeployPlan ? "primary" : "outline-secondary"}
                    disabled={deployDisabled}
                    onClick={deployPlan}
                    data-testid="warsat-deploy-button"
                    aria-describedby="warsatDeployHelp"
                  >
                    {deployLabel}
                  </Button>
                </div>
              </div>
              <p id="warsatDeployHelp" className="visually-hidden">
                Docker deployment requires Docker control enabled and the wrapper started with Docker CLI access.
              </p>

              {!!lifecycle.length && <WarsatLifecycle lifecycle={lifecycle} />}

              <div className="warsat-plan-summary" data-testid="warsat-plan-summary">
                <div>
                  <span>Model</span>
                  <strong>{plan.modelRef || plan.modelPath || plan.expectedModelRegistryEntry?.model || "Not set"}</strong>
                </div>
                <div>
                  <span>Container</span>
                  <strong>{plan.containerName}</strong>
                </div>
                <div>
                  <span>Endpoint</span>
                  <strong>{plan.expectedModelRegistryEntry?.baseUrl || plan.endpoint}</strong>
                </div>
                <div>
                  <span>Profile</span>
                  <strong>{plan.resourceProfile?.label || plan.strengthProfile}</strong>
                </div>
              </div>

              <Row className="g-3 mt-1">
                <Col lg={6}>
                  <h3>Model Registry Entry</h3>
                  <dl className="detail-grid">
                    <dt>Name</dt><dd>{plan.expectedModelRegistryEntry?.name}</dd>
                    <dt>Role</dt><dd>{plan.expectedModelRegistryEntry?.role}</dd>
                    <dt>Strength</dt><dd>{plan.resourceProfile?.label || plan.strengthProfile}</dd>
                    <dt>Endpoint</dt><dd>{plan.expectedModelRegistryEntry?.baseUrl}</dd>
                    <dt>Container</dt><dd>{plan.expectedModelRegistryEntry?.container}</dd>
                  </dl>
                </Col>
                <Col lg={6}>
                  <h3>Tuning And Limits</h3>
                  <dl className="detail-grid">
                    <dt>Max model length</dt><dd>{plan.tuning?.maxModelLen || "profile default"}</dd>
                    <dt>GGUF context</dt><dd>{plan.tuning?.contextWindow || "profile default"}</dd>
                    <dt>GPU utilization</dt><dd>{plan.tuning?.gpuMemoryUtilization ?? "profile default"}</dd>
                    <dt>GPU layers</dt><dd>{plan.tuning?.gpuLayers ?? "auto"}</dd>
                    <dt>Memory cap</dt><dd>{plan.containerLimits?.memoryLimitGb ? `${plan.containerLimits.memoryLimitGb} GB` : "none"}</dd>
                    <dt>CPU cap</dt><dd>{plan.containerLimits?.cpuLimit || "none"}</dd>
                  </dl>
                </Col>
                <Col xs={12}>
                  <h3>Safety Checks</h3>
                  <dl className="detail-grid warsat-safety-grid">
                    <dt>Approval</dt><dd>{plan.requiresApproval ? "Required" : "Not required"}</dd>
                    <dt>No new privileges</dt><dd>{plan.securityChecks?.noNewPrivileges ? "Yes" : "No"}</dd>
                    <dt>Host network</dt><dd>{plan.securityChecks?.hostNetwork ? "Requested" : "Blocked"}</dd>
                    <dt>Health</dt><dd>{plan.healthUrl}</dd>
                  </dl>
                </Col>
              </Row>

              <details className="advanced-block mt-3">
                <summary>Command Preview</summary>
                <pre className="log-box mt-3 mb-0">{formatCommandPreview(plan.commandPreview)}</pre>
              </details>

              <details className="advanced-block mt-3">
                <summary>Composefile Preview</summary>
                <p className="text-body-secondary mt-2 mb-2">
                  Standalone draft for review. The deploy button uses the generated Docker command directly after safety validation.
                </p>
                <pre className="log-box mb-0" data-testid="warsat-compose-preview">{plan.composePreview}</pre>
              </details>

              <details className="advanced-block mt-3">
                <summary>Generated Dockerfile Preview</summary>
                <pre className="log-box mt-3 mb-0" data-testid="warsat-dockerfile-preview">{plan.dockerfilePreview}</pre>
              </details>

              {!!plan.filesPreview?.length && (
                <div className="warsat-file-list mt-3">
                  {plan.filesPreview.map((file) => (
                    <span key={file.path}>{file.path}</span>
                  ))}
                </div>
              )}

              {!!plan.warnings?.length && (
                <div className="warsat-warning-list mt-3" role="status">
                  {plan.warnings.map((warning) => <p key={warning} className="mb-1">{warning}</p>)}
                </div>
              )}

              {deployment && (
                <div className="warsat-deployment-result mt-3" data-testid="warsat-deployment-result" role="status">
                  <div>
                    <strong>{deploymentTitle(deployment)}</strong>
                    <span>{deployment.containerName} / {labelize(deployment.status || deployment.phase)}</span>
                  </div>
                  <dl className="detail-grid mb-0">
                    {deployment.approvalRequired && <><dt>Approval code</dt><dd>{currentApproval?.code || deployment.approval?.code}</dd></>}
                    {deployment.approvalRequired && <><dt>Approval status</dt><dd>{approvalStatus || "pending"}</dd></>}
                    <dt>Model key</dt><dd>{deployment.modelKey}</dd>
                    <dt>Endpoint</dt><dd>{deployment.endpoint}</dd>
                    {!deployment.approvalRequired && <><dt>Health</dt><dd>{deployment.health?.status || deployment.healthUrl}</dd></>}
                    {deployment.failedPhase && <><dt>Failed phase</dt><dd>{labelize(deployment.failedPhase)}</dd></>}
                    {deployment.lastError && <><dt>Last error</dt><dd>{deployment.lastError}</dd></>}
                    {!deployment.approvalRequired && <><dt>Container id</dt><dd>{deployment.containerId || "pending"}</dd></>}
                  </dl>
                  {deployment.message && <p className="workspace-help-text mb-0">{deployment.message}</p>}
                  {!!deployment.logs?.length && (
                    <details className="advanced-block mt-3">
                      <summary>Deployment logs</summary>
                      <div className="warsat-deployment-log-list mt-3">
                        {deployment.logs.map((item, index) => (
                          <article className="warsat-deployment-log" key={`${item.phase}-${index}`}>
                            <span className={`status-pill status-${item.status}`}>{labelize(item.phase)} / {labelize(item.status)}</span>
                            {item.message && <p>{item.message}</p>}
                            {item.command && <code>{item.command}</code>}
                            {(item.stdout || item.stderr || item.error) && (
                              <pre className="log-box mb-0">{[item.stdout, item.stderr, item.error].filter(Boolean).join("\n")}</pre>
                            )}
                          </article>
                        ))}
                      </div>
                    </details>
                  )}
                  {!!deployment.nextSteps?.length && (
                    <ul className="warsat-note-list mt-3 mb-0">
                      {deployment.nextSteps.map((step) => <li key={step}>{step}</li>)}
                    </ul>
                  )}
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

function WarsatLifecycle({ lifecycle }) {
  return (
    <ol className="warsat-lifecycle" data-testid="warsat-lifecycle" aria-label="Warsat deployment lifecycle">
      {lifecycle.map((phase) => (
        <li className={`warsat-lifecycle-step is-${phase.status || "pending"}`} key={phase.id}>
          <span aria-hidden="true" />
          <div>
            <strong>{phase.label || labelize(phase.id)}</strong>
            <small>{labelize(phase.status || "pending")}</small>
            <p>{phase.message}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function deploymentTitle(deployment) {
  if (deployment.approvalRequired) return "Deploy approval requested";
  if (deployment.status === "failed") return "Deployment failed";
  if (deployment.status === "registered") return "Model registered";
  return "Deployment updated";
}

function WarsatHardwarePanel({ hardware, refresh }) {
  const status = hardware?.status || "unknown";
  const checks = hardware?.checks || [];
  const detected = hardware?.detectedHardware || {};
  return (
    <Card className="settings-card warsat-panel warsat-hardware-panel shadow-sm" data-testid="warsat-hardware-panel">
      <Card.Body>
        <div className="section-row align-items-start">
          <div>
            <h2>System Readiness</h2>
            <p className="text-body-secondary mb-0">
              Read-only checks for Docker, GPU visibility, model mounts, and Warsat-managed containers.
            </p>
          </div>
          <div className="warsat-readiness-actions">
            <span className={`warsat-readiness-pill is-${status}`}>{labelize(status)}</span>
            <Button variant="outline-secondary" size="sm" onClick={refresh}>Refresh checks</Button>
          </div>
        </div>
        {!hardware && <p className="warsat-runtime-message mt-3 mb-0">Open or refresh Warsat to run readiness checks.</p>}
        {!!hardware && (
          <>
            <div className="warsat-hardware-grid mt-3">
              {checks.map((check) => (
                <article className={`warsat-hardware-check is-${check.status}`} key={check.id} data-testid="warsat-hardware-check">
                  <span>{labelize(check.status)}</span>
                  <strong>{check.label}</strong>
                  <p>{check.message}</p>
                  {check.nextStep && <small>{check.nextStep}</small>}
                </article>
              ))}
            </div>
            <div className="warsat-hardware-details mt-3">
              <dl className="detail-grid mb-0">
                <dt>Runtime</dt><dd>{detected.runtime || "unknown"}</dd>
                <dt>Docker</dt><dd>{detected.dockerServerVersion || detected.dockerClientVersion || "not detected"}</dd>
                <dt>GPU Count</dt><dd>{(detected.gpus || []).length}</dd>
                <dt>Docker Runtimes</dt><dd>{(detected.dockerRuntimes || []).join(", ") || "none reported"}</dd>
              </dl>
              {!!(hardware.recommendations || []).length && (
                <details className="advanced-block mt-3">
                  <summary>Manual next steps</summary>
                  <ul className="warsat-note-list mt-3 mb-0">
                    {hardware.recommendations.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </details>
              )}
            </div>
          </>
        )}
      </Card.Body>
    </Card>
  );
}

function SummaryTile({ title, value }) {
  return (
    <article className="border rounded-2 bg-body p-3">
      <strong className="fs-4 lh-sm d-block text-break">{value}</strong>
      <span className="text-body-secondary d-block mt-1">{title}</span>
    </article>
  );
}

function OperationButton({ action, containerName, operation, approval, runtimeAction }) {
  const sameOperation = operation?.containerName === containerName && operation?.action === action;
  const status = sameOperation ? approval?.status || operation?.status : "";
  const waiting = sameOperation && operation?.approvalRequired && status !== "approved";
  const label = sameOperation && operation?.approvalRequired
    ? status === "approved"
      ? `Run approved ${action}`
      : `Waiting to ${action}`
    : action === "restart"
      ? "Restart"
      : "Stop";
  return (
    <Button
      size="sm"
      variant={action === "stop" ? "outline-danger" : "outline-secondary"}
      disabled={!containerName || waiting}
      onClick={() => runtimeAction?.(action, containerName)}
    >
      {label}
    </Button>
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

function sessionFolderName(folder) {
  return folder || "Unfiled";
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
