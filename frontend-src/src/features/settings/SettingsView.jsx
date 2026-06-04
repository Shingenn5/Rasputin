import React from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Nav, Row, Stack } from "react-bootstrap";
import { Moon, ShieldCheck, Sun } from "lucide-react";
import { settingsItems } from "../../lib/constants.js";
import {
  displayModelName,
  displayWorkspaceName,
  isModelHealthy,
  runtimeStatus,
} from "../../lib/display.js";

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
          {section === "models" && <ModelsSettings {...props} />}
          {section === "safety" && <SafetySettings {...props} />}
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
                    <Button variant="link" className="entry-name text-start" type="button" onClick={() => browseWorkspace(workspaceBrowse?.root?.id, entry.path)}>
                      {entry.displayName || entry.name}
                    </Button>
                    {entry.kind === "dir" && <Button variant="outline-secondary" size="sm" type="button" onClick={() => approvePath(entry.path)}>Use</Button>}
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
                  <Col md={5}><Form.Label htmlFor="mountHostPath">Host folder</Form.Label><Form.Control id="mountHostPath" name="hostPath" placeholder="C:\\Users\\you\\Documents\\Project" /></Col>
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

function ModelsSettings({ models, selectedModelObject, testingMode, setTestingMode, runModelAction, loadModels, scanGguf }) {
  return (
    <section className="settings-pane active" id="settings-models">
      <div className="section-row">
        <div><h2>Models</h2><p className="text-body-secondary mb-0">Choose and test the model Rasputin uses for chat.</p></div>
        <Button variant="outline-secondary" onClick={loadModels}>Refresh Registry</Button>
      </div>
      <Card className="settings-card active-model-card shadow-sm" data-testid="active-model-card">
        <Card.Body>
          <div className="section-row">
            <div>
              <span className="eyebrow">Active Model</span>
              <h3>{displayModelName(selectedModelObject, models)}</h3>
              <p className="text-body-secondary mb-0">{isModelHealthy(selectedModelObject) ? "Ready for local chat tasks." : "Needs discovery or test."}</p>
            </div>
            <Stack direction="horizontal" gap={2} className="model-actions">
              <Button variant="outline-secondary" onClick={() => runModelAction("test")}>Test</Button>
              <Button variant="outline-secondary" onClick={() => runModelAction("discover")}>Discover</Button>
              <Button variant="outline-secondary" onClick={() => runModelAction("repair")}>Use Found Model</Button>
            </Stack>
          </div>
        </Card.Body>
      </Card>
      <Row className="g-3 workflow-grid mt-1">
        <Col lg={6}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <div className="section-row">
                <div><h3>GGUF Library</h3><p className="text-body-secondary mb-0">Scan mounted model files.</p></div>
                <Button variant="outline-secondary" data-testid="gguf-scan" onClick={scanGguf}>Scan GGUF Library</Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={6}>
          <details className="settings-card advanced-block card shadow-sm" data-testid="advanced-model-registry">
            <summary>Advanced model registry</summary>
            <div id="modelRegistry" className="model-list">
              {models.map((model) => (
                <Card className="model-row" key={model.key}>
                  <Card.Body>
                    <strong>{displayModelName(model, models)}</strong>
                    <dl className="model-meta-grid mb-0">
                      <dt>Purpose</dt><dd>{model.role || "chat"}</dd>
                      <dt>Runtime</dt><dd>{model.runtime || model.provider || "local"}</dd>
                      <dt>Health</dt><dd>{runtimeStatus(model)}</dd>
                    </dl>
                  </Card.Body>
                </Card>
              ))}
            </div>
          </details>
        </Col>
      </Row>
      <details className="settings-card advanced-block card shadow-sm mt-3" data-testid="advanced-model-controls">
        <summary>Advanced model controls</summary>
        <Form.Check type="switch">
          <Form.Check.Input
            data-testid="testing-mode-toggle"
            checked={testingMode}
            onChange={(event) => setTestingMode(event.target.checked)}
          />
          <Form.Check.Label><strong>Testing Mode</strong> <small className="text-body-secondary">Show dry-run in the model picker.</small></Form.Check.Label>
        </Form.Check>
      </details>
      <pre id="modelLogs" className="log-box mt-3" hidden />
    </section>
  );
}

function SafetySettings({ security, saveSafety }) {
  const groups = [
    ["Local file access", [["privacyLock", "Privacy lock"], ["allowFileRead", "File read"], ["allowFileWrite", "File write"], ["allowFileReorganize", "Reorganize"]]],
    ["Tools and runtime", [["allowShellExecution", "Shell execution"], ["allowWebSearch", "Web search"], ["allowDockerControl", "Docker control"], ["allowModelTests", "Model tests"], ["allowModelRegistryEdit", "Registry edits"], ["allowRemoteModels", "Remote models"]]],
    ["Approvals and audit", [["approvalRequiredFileWrite", "Approve writes"], ["approvalRequiredFileMove", "Approve moves"], ["approvalRequiredWebSearch", "Approve web"], ["auditEnabled", "Audit log"]]],
  ];
  return (
    <section className="settings-pane active" id="settings-safety">
      <PaneTitle title="Safety" text="Local-only protections and sensitive permissions." />
      <form id="securityForm" onSubmit={saveSafety}>
        <Row className="g-3">
          {groups.map(([title, items]) => (
            <Col lg={4} key={title}>
              <Card className="settings-card h-100 shadow-sm">
                <Card.Body>
                  <h3>{title}</h3>
                  <Stack gap={2}>
                    {items.map(([key, label]) => <Form.Check key={key} type="switch" name={key} defaultChecked={!!security[key]} label={label} />)}
                  </Stack>
                </Card.Body>
              </Card>
            </Col>
          ))}
          <Col xs={12}>
            <Card className="settings-card shadow-sm">
              <Card.Body>
                <Row className="g-3 align-items-end">
                  <Col md={4}><Form.Label>Query chars</Form.Label><Form.Control type="number" name="webSearchMaxChars" defaultValue={security.webSearchMaxChars || 180} /></Col>
                  <Col md={8}><Button type="submit">Save Safety</Button></Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </form>
    </section>
  );
}

function KnowledgeSettings({ ragStats, graphStats }) {
  return (
    <section className="settings-pane active" id="settings-knowledge">
      <PaneTitle title="Knowledge" text="Local retrieval and graph tools." />
      <Row className="g-3">
        <Col lg={6}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body>
              <h3>RAG Index</h3>
              <form id="ragIngestForm" className="inline-form">
                <Form.Control defaultValue="." />
                <Button variant="outline-secondary">Index</Button>
              </form>
              <p className="text-body-secondary mt-3 mb-0">{ragStats ? `${ragStats.docs} docs, ${ragStats.chunks} chunks` : "No index loaded."}</p>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={6}>
          <Card className="settings-card h-100 shadow-sm">
            <Card.Body><h3>Graphify</h3><p className="text-body-secondary mb-0">{graphStats ? `${graphStats.nodes} nodes, ${graphStats.edges} edges` : "No graph yet."}</p></Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}

function OutputSettings({ output }) {
  return (
    <section className="settings-pane active" id="settings-output">
      <PaneTitle title="Output" text="Completed task results can be written as Markdown." />
      <Card className="settings-card shadow-sm"><Card.Body><p className="mb-0">{output?.markdownFolder || "workspace/markdown-output"}</p></Card.Body></Card>
    </section>
  );
}

function AppearanceSettings({ theme, setTheme }) {
  return (
    <section className="settings-pane active" id="settings-appearance">
      <PaneTitle title="Appearance" text="Saved to Rasputin preferences and restored after sign-in." />
      <Card className="settings-card shadow-sm">
        <Card.Body>
          <Form.Label htmlFor="themeSelect">Theme</Form.Label>
          <Form.Select id="themeSelect" data-testid="theme-select" value={theme} onChange={(event) => setTheme(event.target.value)}>
            <option value="rasputin-light">Rasputin Light</option>
            <option value="rasputin-dark">Rasputin Dark</option>
            <option value="contrast">High Contrast</option>
          </Form.Select>
        </Card.Body>
      </Card>
      <Row className="g-3 theme-grid">
        <Col md={4}><Button variant="outline-secondary" className="theme-card" onClick={() => setTheme("rasputin-light")}><Sun size={18} />Rasputin Light</Button></Col>
        <Col md={4}><Button variant="outline-secondary" className="theme-card" onClick={() => setTheme("rasputin-dark")}><Moon size={18} />Rasputin Dark</Button></Col>
        <Col md={4}><Button variant="outline-secondary" className="theme-card" onClick={() => setTheme("contrast")}><ShieldCheck size={18} />High Contrast</Button></Col>
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
