import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Nav, Row, Stack } from "react-bootstrap";
import { CheckCircle2, Moon, Play, RotateCcw, Save, ShieldAlert, ShieldCheck, Square, Sun, Wrench } from "lucide-react";
import { settingsItems } from "../../lib/constants.js";
import { displayWorkspaceName } from "../../lib/display.js";

export function SettingsView(props) {
  const { view, section, setSection } = props;
  return (
    <section className={`app-view settings-view ${view === "settings" ? "active" : ""}`} id="settingsShell" data-app-view="settings">
      <header className="page-header border-bottom bg-body">
        <div>
          <h1 className="mb-0">Settings</h1>
          <p className="text-body-secondary mb-0">Runtime defaults, approved folders, model workflows, safety, and appearance.</p>
        </div>
      </header>
      <div className="settings-layout">
        <Nav className="settings-nav flex-column bg-body-tertiary" aria-label="Settings sections">
          {settingsItems.map(([id, label, small]) => (
            <Button
              key={id}
              type="button"
              variant={section === id ? "primary" : "light"}
              className="settings-tab text-start"
              data-testid={`settings-${id}`}
              onClick={() => setSection(id)}
            >
              <span className="d-block fw-semibold">{label}</span>
              <small>{small}</small>
            </Button>
          ))}
        </Nav>
        <div className="settings-panels">
          {section === "general" && <GeneralSettings />}
          {section === "workspaces" && <WorkspaceSettings {...props} />}
          {section === "safety" && <SafetySettings {...props} />}
          {section === "tool-relays" && <ToolRelaySettings {...props} />}
          {section === "knowledge" && <KnowledgeSettings {...props} />}
          {section === "output" && <OutputSettings {...props} />}
          {section === "appearance" && <AppearanceSettings {...props} />}
          {section === "admin" && <AdminSettings {...props} />}
        </div>
      </div>
    </section>
  );
}

function GeneralSettings() {
  return (
    <section className="settings-pane active" id="settings-general">
      <PaneTitle title="General" text="Defaults for the next task you start." />
      <Card className="settings-card shadow-sm">
        <Card.Body>
          <Row className="g-3">
            <Col md={6}>
              <Form.Group>
                <Form.Label>Skill</Form.Label>
                <Form.Select id="skill"><option>general</option><option>folder_organizer</option><option>paper_writer</option></Form.Select>
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group>
                <Form.Label>Mode</Form.Label>
                <Form.Select id="taskMode"><option>chat</option><option>research</option><option>code</option><option>write</option><option>organize</option></Form.Select>
              </Form.Group>
            </Col>
          </Row>
        </Card.Body>
      </Card>
    </section>
  );
}

function WorkspaceSettings({ workspace, workspaceRoots, workspaceBrowse, browseWorkspace, approvePath, loadWorkspaceRoots, previewMount, mountPlan }) {
  const rootName = workspaceBrowse?.root?.displayName || workspaceBrowse?.root?.name || "Approved Folder";
  const crumb = workspaceBrowse?.root?.path === workspaceBrowse?.path ? rootName : `${rootName} / ${workspaceBrowse?.path || ""}`;
  return (
    <section className="settings-pane active" id="settings-workspaces">
      <PaneTitle title="Workspaces" text={`Active: ${workspace.activeName || "Project Root"}`} />
      <Row className="g-3">
        <Col lg={5}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div><h3>Approved Folders</h3><p className="text-body-secondary mb-0">Folders Rasputin can already see.</p></div>
                <Button variant="outline-secondary" size="sm" onClick={loadWorkspaceRoots}>Refresh</Button>
              </div>
              <div id="workspaceRootList" className="workspace-root-list mt-3">
                {workspaceRoots.map((root) => (
                  <Button
                    key={root.id}
                    variant={root.path === workspace.activePath ? "primary" : "outline-secondary"}
                    className="workspace-root-card text-start"
                    type="button"
                    onClick={() => browseWorkspace(root.id)}
                  >
                    <strong>{root.displayName || root.name}</strong>
                    <span>{displayWorkspaceName(root.path)}</span>
                    <small>{root.path === workspace.activePath ? "Active" : root.readOnly ? "Read-only" : "Read/write"}</small>
                  </Button>
                ))}
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={7}>
          <Card className="settings-card h-100 shadow-sm" data-testid="workspace-browser">
            <Card.Body>
              <div className="section-row">
                <div><h3>Folder Browser</h3><p className="text-body-secondary mb-0">Choose a folder with the GUI instead of typing a path.</p></div>
                <Button variant="outline-secondary" size="sm" type="button" onClick={() => approvePath(workspaceBrowse?.path || ".")}>Use This Folder</Button>
              </div>
              <div id="workspaceBreadcrumb" className="breadcrumb-line">{crumb}</div>
              <ListGroup id="workspaceEntries" className="workspace-browser-list">
                {(workspaceBrowse?.entries || []).map((entry) => (
                  <ListGroup.Item className="workspace-entry" key={entry.path}>
                    <Button
                      variant="link"
                      className="entry-name text-start"
                      type="button"
                      disabled={entry.kind === "file"}
                      onClick={() => browseWorkspace(workspaceBrowse?.root?.id, entry.path)}
                    >
                      {entry.displayName || entry.name}
                    </Button>
                    {entry.kind === "folder" && <Button variant="outline-secondary" size="sm" type="button" onClick={() => approvePath(entry.path)}>Use</Button>}
                  </ListGroup.Item>
                ))}
              </ListGroup>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={12}>
          <Card className="settings-card shadow-sm">
            <Card.Body>
              <h3>Add Folder</h3>
              <p className="text-body-secondary">Preview a new Docker mount. New mounts default to read-only.</p>
              <form id="workspaceMountForm" onSubmit={previewMount}>
                <Row className="g-3 align-items-end">
                  <Col md={5}><Form.Label htmlFor="mountHostPath">Host folder</Form.Label><Form.Control id="mountHostPath" name="hostPath" placeholder="C:\\Users\\you\\Project or /home/you/project" /></Col>
                  <Col md={4}><Form.Label>Name</Form.Label><Form.Control name="name" placeholder="Project Documents" /></Col>
                  <Col md={3}><Form.Check type="switch" name="readOnly" defaultChecked label="Read-only mount" /></Col>
                  <Col xs={12}><Button variant="outline-secondary" type="submit">Preview Mount</Button></Col>
                </Row>
              </form>
              <div id="workspaceMountPlan" className="mount-plan mt-3" data-testid="workspace-mount-plan">
                {mountPlan && (mountPlan.error ? mountPlan.error : (
                  <Card className="mount-plan-card">
                    <Card.Body>
                      <strong>{mountPlan.displayName}</strong>
                      <span>{mountPlan.hostPath}</span>
                      <Badge bg={mountPlan.readOnly ? "secondary" : "warning"}>{mountPlan.readOnly ? "Read-only" : "Read/write"}</Badge>
                    </Card.Body>
                  </Card>
                ))}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}

function ToolRelaySettings({
  mcpRelays,
  tools,
  registerMcpRelay,
  startMcpRelay,
  stopMcpRelay,
  discoverMcpRelay,
  classifyMcpTool,
  approveApproval,
}) {
  const [status, setStatus] = useState("");
  const servers = mcpRelays?.servers || [];
  const externalTools = (tools?.tools || []).filter((tool) => tool.external);

  async function submit(event) {
    event.preventDefault();
    setStatus("Registering MCP server...");
    const form = new FormData(event.currentTarget);
    try {
      await registerMcpRelay({
        id: form.get("id"),
        name: form.get("name"),
        transport: "stdio",
        command: form.get("command"),
        cwd: form.get("cwd") || ".",
      });
      event.currentTarget.reset();
      setStatus("Registration preview created. Approve before starting.");
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function run(label, action) {
    setStatus(`${label}...`);
    try {
      await action();
      setStatus(`${label} complete.`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <section className="settings-pane active" id="settings-tool-relays">
      <PaneTitle title="Tool Relays" text="Register local stdio MCP servers. Commands require approval before Rasputin can start them." />
      <Row className="g-3">
        <Col lg={5}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div>
                  <h3>Add Local MCP Server</h3>
                  <p className="text-body-secondary mb-0">Use commands visible inside the Rasputin container or local runtime.</p>
                </div>
                <Wrench size={20} aria-hidden="true" />
              </div>
              <form className="mt-3" data-testid="mcp-register-form" onSubmit={submit}>
                <Stack gap={3}>
                  <Form.Group>
                    <Form.Label htmlFor="mcpServerId">Server id</Form.Label>
                    <Form.Control id="mcpServerId" name="id" placeholder="filesystem-local" required />
                  </Form.Group>
                  <Form.Group>
                    <Form.Label htmlFor="mcpServerName">Display name</Form.Label>
                    <Form.Control id="mcpServerName" name="name" placeholder="Filesystem MCP" />
                  </Form.Group>
                  <Form.Group>
                    <Form.Label htmlFor="mcpServerCommand">Command</Form.Label>
                    <Form.Control id="mcpServerCommand" name="command" placeholder="npx -y @modelcontextprotocol/server-filesystem ." required />
                    <Form.Text>Rasputin uses shell-free stdio execution. Package-manager commands are approval-gated per server.</Form.Text>
                  </Form.Group>
                  <Form.Group>
                    <Form.Label htmlFor="mcpServerCwd">Working directory</Form.Label>
                    <Form.Control id="mcpServerCwd" name="cwd" placeholder="." />
                  </Form.Group>
                  <Button type="submit" variant="primary">Preview Registration</Button>
                </Stack>
              </form>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={7}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div>
                  <h3>Registered Relays</h3>
                  <p className="text-body-secondary mb-0">Start only approved local stdio servers, then discover and classify tools.</p>
                </div>
                <Badge bg="secondary">{servers.length} server{servers.length === 1 ? "" : "s"}</Badge>
              </div>
              <div className="mcp-server-list mt-3" data-testid="mcp-server-list">
                {servers.map((server) => (
                  <article className="mcp-server-card" key={server.id} data-testid="mcp-server-card">
                    <div className="section-row">
                      <div>
                        <strong>{server.name || server.id}</strong>
                        <p className="text-body-secondary mb-0">{server.transport} / {server.status} / {server.health}</p>
                      </div>
                      <Badge bg={server.commandApproved ? "success" : "warning"}>{server.commandApproved ? "Approved" : "Approval required"}</Badge>
                    </div>
                    {server.command && <code className="mcp-command">{server.command}</code>}
                    {server.lastError && <p className="text-danger mb-0">{server.lastError}</p>}
                    {server.pendingApprovalId && (
                      <p className="text-body-secondary mb-0">Approval code: <strong>{server.pendingApprovalCode}</strong></p>
                    )}
                    <Stack direction="horizontal" gap={2} className="flex-wrap">
                      {server.pendingApprovalId && (
                        <Button
                          size="sm"
                          variant="warning"
                          type="button"
                          onClick={() => run("Approve and start MCP server", async () => {
                            await approveApproval(server.pendingApprovalId);
                            await startMcpRelay(server);
                          })}
                        >
                          <Play size={14} />
                          Approve + Start
                        </Button>
                      )}
                      {!server.pendingApprovalId && server.transport !== "internal" && (
                        <Button size="sm" variant="outline-primary" type="button" onClick={() => run("Start MCP server", () => startMcpRelay(server))}>
                          <Play size={14} />
                          Start
                        </Button>
                      )}
                      {server.transport !== "internal" && (
                        <Button size="sm" variant="outline-secondary" type="button" onClick={() => run("Stop MCP server", () => stopMcpRelay(server))}>
                          <Square size={14} />
                          Stop
                        </Button>
                      )}
                      <Button size="sm" variant="outline-secondary" type="button" onClick={() => run("Discover MCP tools", () => discoverMcpRelay(server))}>
                        Discover Tools
                      </Button>
                    </Stack>
                    {!!server.logs?.length && <pre className="log-box mt-2 mb-0">{server.logs.join("\n")}</pre>}
                  </article>
                ))}
                {!servers.length && <p className="text-body-secondary mb-0">No MCP relays are registered yet.</p>}
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col xs={12}>
          <Card className="settings-card shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div>
                  <h3>Discovered MCP Tools</h3>
                  <p className="text-body-secondary mb-0">External tools stay disabled until you classify their risk and permission.</p>
                </div>
                <Badge bg="secondary">{externalTools.length} tool{externalTools.length === 1 ? "" : "s"}</Badge>
              </div>
              <div className="tool-relay-grid mt-3">
                {externalTools.map((tool) => (
                  <article className="tool-relay-card" key={tool.id}>
                    <div className="tool-relay-card-head">
                      <div>
                        <span className={`status-pill risk-${tool.risk}`}>{labelize(tool.risk)}</span>
                        <h4>{tool.displayName || tool.id}</h4>
                      </div>
                      <span className={`status-pill ${tool.available ? "status-done" : "status-error"}`}>{tool.available ? "Available" : "Blocked"}</span>
                    </div>
                    <p>{tool.description}</p>
                    {tool.disabledReason && <p className="tool-relay-reason">{tool.disabledReason}</p>}
                    <Stack direction="horizontal" gap={2} className="flex-wrap">
                      <Button size="sm" variant="outline-secondary" type="button" onClick={() => run("Classify guarded read tool", () => classifyMcpTool(tool.id, { risk: "guarded", permissionFlag: "allow_file_read", enabled: true }))}>
                        Guarded Read
                      </Button>
                      <Button size="sm" variant="outline-warning" type="button" onClick={() => run("Classify approval tool", () => classifyMcpTool(tool.id, { risk: "approval_required", permissionFlag: "", enabled: true }))}>
                        Approval Required
                      </Button>
                    </Stack>
                  </article>
                ))}
                {!externalTools.length && <p className="text-body-secondary mb-0">No external MCP tools discovered yet.</p>}
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
      <p className="settings-status mt-3" role="status" aria-live="polite">{status}</p>
    </section>
  );
}

function SafetySettings({ security, saveSafety }) {
  const [draft, setDraft] = useState(() => security || {});
  const [status, setStatus] = useState("");
  const groups = [
    ["Local file access", "Controls what approved workspaces can expose to tools.", [
      ["privacyLock", "Privacy lock", "Blocks non-local model endpoints while enabled."],
      ["allowFileRead", "File read", "Allows local browsing, RAG, Graphify, and file previews."],
      ["allowFileWrite", "File write", "Required before Markdown exports or future file edits can save."],
      ["allowFileReorganize", "Reorganize", "Future folder move plans still require approval."],
    ]],
    ["Tools and runtime", "High-impact capabilities stay intentionally obvious.", [
      ["allowShellExecution", "Shell execution", "Runs local commands. Keep off unless you are testing coding workflows."],
      ["allowWebSearch", "Brokered web search", "Lets only the MCP broker reach the internet after query checks."],
      ["allowDockerControl", "Docker control", "Lets Rasputin request model container operations."],
      ["allowModelTests", "Model health tests", "Allows tiny local test prompts against model endpoints."],
      ["allowModelRegistryEdit", "Registry edits", "Allows model registry changes from the UI."],
      ["allowRemoteModels", "Remote models", "Allows non-local model endpoints. Usually keep off."],
    ]],
    ["Approvals and audit", "Risky actions should leave a local trail.", [
      ["approvalRequiredFileWrite", "Approve writes", "User approval before writing files."],
      ["approvalRequiredFileMove", "Approve moves", "User approval before moving or reorganizing files."],
      ["approvalRequiredWebSearch", "Approve web", "User approval before brokered internet search."],
      ["auditEnabled", "Audit log", "Records sensitive local operations."],
    ]],
  ];
  const dirty = useMemo(() => JSON.stringify(normalizeSecurityDraft(draft)) !== JSON.stringify(normalizeSecurityDraft(security || {})), [draft, security]);

  useEffect(() => {
    setDraft(security || {});
    setStatus("");
  }, [security]);

  function updateFlag(key, value) {
    setDraft((current) => ({ ...current, [key]: value }));
    setStatus("Unsaved changes. Review and press Save Safety to apply.");
  }

  async function submit(event) {
    event.preventDefault();
    setStatus("Saving safety settings...");
    try {
      await saveSafety(normalizeSecurityDraft(draft));
      setStatus("Safety settings saved.");
    } catch (error) {
      setStatus(error.message);
    }
  }

  function reset() {
    setDraft(security || {});
    setStatus("Changes reset.");
  }

  return (
    <section className="settings-pane active" id="settings-safety">
      <PaneTitle title="Safety" text="Local-only protections and sensitive permissions. Switches are drafts until saved." />
      <form id="securityForm" className="safety-form" onSubmit={submit}>
        <div className={`settings-save-strip ${dirty ? "is-dirty" : "is-clean"}`} role="status" aria-live="polite">
          <div>
            <strong>{dirty ? "Unsaved safety changes" : "Safety settings are saved"}</strong>
            <span>{dirty ? "Nothing changes on the backend until you press Save Safety." : "Current permissions match the saved configuration."}</span>
          </div>
          <Stack direction="horizontal" gap={2}>
            <Button variant="outline-secondary" type="button" onClick={reset} disabled={!dirty}>
              <RotateCcw size={16} />
              Reset
            </Button>
            <Button type="submit" disabled={!dirty} data-testid="save-safety">
              <Save size={16} />
              Save Safety
            </Button>
          </Stack>
        </div>
        <Row className="g-3">
          {groups.map(([title, text, items]) => (
            <Col lg={4} key={title}>
              <Card className="settings-card safety-card h-100 shadow-sm">
                <Card.Body>
                  <h3>{title}</h3>
                  <p className="text-body-secondary">{text}</p>
                  <div className="safety-switch-list">
                    {items.map(([key, label, help]) => (
                      <label className={`safety-switch ${draft[key] ? "is-on" : "is-off"}`} key={key}>
                        <span>
                          <strong>{label}</strong>
                          <small>{help}</small>
                        </span>
                        <input
                          type="checkbox"
                          name={key}
                          checked={!!draft[key]}
                          onChange={(event) => updateFlag(key, event.target.checked)}
                        />
                        <em>{draft[key] ? "On" : "Off"}</em>
                      </label>
                    ))}
                  </div>
                </Card.Body>
              </Card>
            </Col>
          ))}
          <Col xs={12}>
            <Card className="settings-card shadow-sm">
              <Card.Body>
                <Row className="g-3 align-items-end">
                  <Col md={4}>
                    <Form.Label htmlFor="webSearchMaxChars">Web query character limit</Form.Label>
                    <Form.Control
                      id="webSearchMaxChars"
                      type="number"
                      name="webSearchMaxChars"
                      min="40"
                      max="2000"
                      value={draft.webSearchMaxChars || 180}
                      onChange={(event) => updateFlag("webSearchMaxChars", Number(event.target.value || 180))}
                    />
                  </Col>
                  <Col md={8}>
                    <div className="safety-state-note">
                      {dirty ? <ShieldAlert size={18} /> : <CheckCircle2 size={18} />}
                      <span>{status || "Review changes carefully before saving."}</span>
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </form>
    </section>
  );
}

function normalizeSecurityDraft(value) {
  const keys = [
    "privacyLock", "allowFileRead", "allowFileWrite", "allowFileReorganize", "allowShellExecution",
    "allowWebSearch", "allowDockerControl", "allowModelTests", "allowModelRegistryEdit", "allowRemoteModels",
    "approvalRequiredFileWrite", "approvalRequiredFileMove", "approvalRequiredWebSearch", "auditEnabled",
  ];
  const out = Object.fromEntries(keys.map((key) => [key, !!value?.[key]]));
  out.webSearchMaxChars = Number(value?.webSearchMaxChars || 180);
  return out;
}

function KnowledgeSettings({ workspace, ragStats, graphStats, indexWorkspaceKnowledge, searchWorkspaceKnowledge, refreshKnowledgeStats }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [results, setResults] = useState(null);
  const activePath = workspace?.activePath || ".";

  async function indexActiveWorkspace() {
    try {
      setStatus("Indexing active workspace...");
      const result = await indexWorkspaceKnowledge?.(activePath);
      setStatus(`Indexed ${result?.ragResult?.docsIndexed || 0} docs for ${displayWorkspaceName(activePath)}.`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function searchKnowledge(event) {
    event.preventDefault();
    if (!query.trim()) return;
    try {
      setStatus("Searching local knowledge...");
      const found = await searchWorkspaceKnowledge?.(query.trim(), activePath);
      setResults(found);
      setStatus(`${found?.ragResult?.hits?.length || 0} retrieval hits and ${found?.graphResult?.nodes?.length || 0} graph nodes.`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <section className="settings-pane active" id="settings-knowledge">
      <PaneTitle title="Knowledge" text="Workspace-aware retrieval, Graphify relationships, and local citation search." />
      <Row className="g-3">
        <Col lg={7}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div>
                  <h3>Active Workspace Knowledge</h3>
                  <p className="text-body-secondary mb-0">{displayWorkspaceName(activePath)} is the current indexing scope.</p>
                </div>
                <Stack direction="horizontal" gap={2}>
                  <Button variant="outline-secondary" onClick={refreshKnowledgeStats}>Refresh</Button>
                  <Button id="ragIngestForm" variant="outline-secondary" onClick={indexActiveWorkspace}>Index Active Workspace</Button>
                </Stack>
              </div>
              <dl className="detail-grid mt-3 mb-0">
                <dt>Documents</dt><dd>{ragStats?.docs ?? 0}</dd>
                <dt>Chunks</dt><dd>{ragStats?.chunks ?? 0}</dd>
                <dt>Graph nodes</dt><dd>{graphStats?.nodes ?? 0}</dd>
                <dt>Graph edges</dt><dd>{graphStats?.edges ?? 0}</dd>
                <dt>Parsers</dt><dd>{parserStatusLine(ragStats?.parserStatus)}</dd>
              </dl>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <h3>Search Knowledge</h3>
              <form className="inline-form" onSubmit={searchKnowledge}>
                <Form.Control value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search indexed local context" />
                <Button variant="outline-secondary" type="submit">Search</Button>
              </form>
              {status && <p className="text-body-secondary mt-3 mb-0" role="status">{status}</p>}
              {results && (
                <Stack gap={2} className="mt-3">
                  {(results.ragResult?.hits || []).slice(0, 3).map((hit) => (
                    <Card className="message-card" key={`${hit.source}-${hit.chunk}`}>
                      <Card.Body>
                        <strong>{hit.path}</strong>
                        <small className="d-block text-body-secondary">{citationLabel(hit)}</small>
                      </Card.Body>
                    </Card>
                  ))}
                </Stack>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}

function OutputSettings({ output, saveOutputConfig, security }) {
  const [folder, setFolder] = useState(output?.markdownFolder || "workspace/markdown-output");
  const [status, setStatus] = useState("");
  const canWrite = !!security?.allowFileWrite;

  useEffect(() => {
    setFolder(output?.markdownFolder || "workspace/markdown-output");
  }, [output?.markdownFolder]);

  async function submit(event) {
    event.preventDefault();
    if (!canWrite) {
      setStatus("File write is disabled in Safety. Enable it before changing output folders.");
      return;
    }
    try {
      setStatus("Saving output folder...");
      const saved = await saveOutputConfig?.({ markdownFolder: folder });
      setStatus(`Output folder saved: ${saved?.markdownFolder || folder}`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <section className="settings-pane active" id="settings-output">
      <PaneTitle title="Output" text="Control where generated Markdown exports are written locally." />
      <Row className="g-3">
        <Col lg={7}>
          <Card className="settings-card output-card shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div>
                  <h3>Markdown Export Folder</h3>
                  <p className="text-body-secondary mb-0">Exports stay inside Rasputin-visible folders. The backend rejects paths outside the project root.</p>
                </div>
                <Badge bg={canWrite ? "success" : "secondary"}>{canWrite ? "Write enabled" : "Write disabled"}</Badge>
              </div>
              <form className="output-settings-form mt-3" data-testid="output-settings-form" onSubmit={submit}>
                <Form.Label htmlFor="markdownFolder">Relative folder</Form.Label>
                <div className="output-folder-row">
                  <Form.Control
                    id="markdownFolder"
                    value={folder}
                    onChange={(event) => {
                      setFolder(event.target.value);
                      setStatus("Unsaved output folder.");
                    }}
                    placeholder="workspace/markdown-output"
                  />
                  <Button type="submit" disabled={!canWrite}>
                    <Save size={16} />
                    Save Output
                  </Button>
                </div>
                <Form.Text>
                  Use an approved workspace subfolder when you want exported summaries to be easy to find.
                </Form.Text>
              </form>
              {status && <p className="settings-inline-status mt-3 mb-0" role="status">{status}</p>}
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <Card className="settings-card output-card h-100 shadow-sm">
            <Card.Body>
              <h3>Current Output State</h3>
              <dl className="detail-grid mt-3 mb-0">
                <dt>Folder</dt><dd>{output?.markdownFolder || "workspace/markdown-output"}</dd>
                <dt>Resolved path</dt><dd>{output?.absolutePath || "Not loaded"}</dd>
                <dt>Export format</dt><dd>Markdown task summaries</dd>
                <dt>Permission</dt><dd>{canWrite ? "Allowed by Safety" : "Blocked by Safety"}</dd>
              </dl>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}

function parserStatusLine(status = {}) {
  const enabled = Object.entries(status)
    .filter(([, value]) => value === "enabled")
    .map(([key]) => key.toUpperCase());
  return enabled.length ? enabled.join(", ") : "Text only";
}

function citationLabel(hit = {}) {
  if (hit.pageStart) return `Page ${hit.pageStart}${hit.pageEnd && hit.pageEnd !== hit.pageStart ? `-${hit.pageEnd}` : ""}`;
  if (hit.sheetName) return `${hit.sheetName} rows ${hit.rowStart || hit.lineStart || "?"}-${hit.rowEnd || hit.lineEnd || "?"}`;
  if (hit.lineStart) return `Lines ${hit.lineStart}-${hit.lineEnd || hit.lineStart}`;
  return "Citation metadata unavailable";
}

function AppearanceSettings({ theme, setTheme, themeOptions = [] }) {
  return (
    <section className="settings-pane active" id="settings-appearance">
      <PaneTitle title="Appearance" text="Saved to Rasputin preferences and restored after sign-in." />
      <Card className="settings-card shadow-sm">
        <Card.Body>
          <Form.Label htmlFor="themeSelect">Theme</Form.Label>
          <Form.Select id="themeSelect" data-testid="theme-select" value={theme} onChange={(event) => setTheme(event.target.value)}>
            {themeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Form.Select>
        </Card.Body>
      </Card>
      <Row className="g-3 theme-grid">
        {themeOptions.map(([value, label, description]) => (
          <Col md={4} key={value}>
            <Button
              variant={theme === value ? "primary" : "outline-secondary"}
              className="theme-card"
              data-testid={`theme-card-${value}`}
              onClick={() => setTheme(value)}
            >
              {value === "contrast" ? <ShieldCheck size={18} /> : value.includes("dark") || value.includes("slate") || value.includes("cyborg") || value.includes("solar") || value.includes("superhero") ? <Moon size={18} /> : <Sun size={18} />}
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </Button>
          </Col>
        ))}
      </Row>
    </section>
  );
}

function AdminSettings({ logout }) {
  return (
    <section className="settings-pane active" id="settings-admin">
      <PaneTitle title="Admin" text="Local session and server identity." />
      <Card className="settings-card shadow-sm"><Card.Body><Button variant="outline-secondary" onClick={logout}>Logout</Button></Card.Body></Card>
    </section>
  );
}

function PaneTitle({ title, text }) {
  return (
    <div className="pane-title">
      <h2>{title}</h2>
      <p className="text-body-secondary mb-0">{text}</p>
    </div>
  );
}

function labelize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
