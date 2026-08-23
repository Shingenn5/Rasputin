import React, { useMemo, useState } from "react";
import {
  CheckCircle2,
  ExternalLink,
  Link2,
  Network,
  Play,
  RefreshCw,
  Server,
  ShieldAlert,
  Square,
  Trash2,
  Wrench,
} from "lucide-react";
import { Button } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";

const DEFAULT_FORM = {
  name: "",
  id: "",
  transport: "streamable_http",
  command: "",
  args: "",
  cwd: "",
  networkTarget: "",
  headerName: "Authorization",
  secretEnvName: "MCP_TOKEN",
};

function titleize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusVariant(server) {
  if (server.status === "running" || server.health === "running") return "up";
  if (server.status === "error" || server.health === "error") return "danger";
  if (server.status === "pending_approval" || server.compatibilityStatus === "approval_required") return "warn";
  return "muted";
}

function serverCommand(server) {
  const args = Array.isArray(server.args) ? server.args : [];
  return [server.command, ...args].filter(Boolean).join(" ");
}

export function McpSettings({
  mcpRelays = { servers: [] },
  workspaceRoots = [],
  registerMcpRelay,
  registerMcpFixture,
  startMcpRelay,
  stopMcpRelay,
  restartMcpRelay,
  removeMcpRelay,
  discoverMcpRelay,
  testMcpRelay,
  classifyMcpTool,
  callMcpTestTool,
  go,
}) {
  const servers = useMemo(() => mcpRelays?.servers || [], [mcpRelays]);
  const roots = useMemo(
    () => (workspaceRoots || []).filter((root) => root?.absolute_path),
    [workspaceRoots],
  );
  const [form, setForm] = useState(DEFAULT_FORM);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [expanded, setExpanded] = useState({});
  const [approvalCode, setApprovalCode] = useState("");

  function updateForm(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function openDialog(transport = "streamable_http") {
    setForm({
      ...DEFAULT_FORM,
      transport,
      cwd: roots[0]?.absolute_path || "",
    });
    setApprovalCode("");
    setStatus("");
    setDialogOpen(true);
  }

  async function submit(event) {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setStatus("A server name is required.");
      return;
    }
    const transport = form.transport;
    const payload = {
      id: form.id.trim() || undefined,
      name,
      transport,
      scope: "workspace",
      enabled: transport === "streamable_http",
    };
    if (transport === "stdio") {
      payload.command = form.command.trim();
      payload.args = form.args.trim();
      payload.cwd = form.cwd.trim();
    } else {
      payload.networkTarget = form.networkTarget.trim();
      if (form.headerName.trim() && form.secretEnvName.trim()) {
        payload.secretRefs = {};
        payload.secretRefs[form.headerName.trim()] = "$ENV:" + form.secretEnvName.trim();
      }
    }

    setBusy("register");
    setStatus("");
    try {
      const result = await registerMcpRelay(payload);
      if (result?.approval?.code) {
        setApprovalCode(result.approval.code);
        setStatus("Registration is waiting for administrator approval.");
      } else {
        setStatus("MCP server registered.");
        setDialogOpen(false);
      }
      setForm(DEFAULT_FORM);
    } catch (error) {
      setStatus(error.message || "MCP server registration failed.");
    } finally {
      setBusy("");
    }
  }

  async function runAction(label, callback) {
    if (!callback) return;
    setBusy(label);
    setStatus("");
    try {
      await callback();
      setStatus(label + " complete.");
    } catch (error) {
      setStatus(error.message || label + " failed.");
    } finally {
      setBusy("");
    }
  }

  async function remove(server) {
    if (server.id === "rasputin-tool-relay") return;
    if (!window.confirm("Remove " + (server.name || server.id) + "?")) return;
    await runAction(
      "Remove",
      () => removeMcpRelay(server),
    );
  }

  async function registerFixture() {
    setBusy("fixture");
    setStatus("");
    try {
      const result = await registerMcpFixture();
      if (result?.approval?.code) {
        setApprovalCode(result.approval.code);
        setStatus("The operator fixture is waiting for approval.");
      } else {
        setStatus("Operator fixture registered.");
      }
    } catch (error) {
      setStatus(error.message || "Fixture registration failed.");
    } finally {
      setBusy("");
    }
  }

  const hasExternalServer = servers.some((server) => server.transport !== "internal");

  return (
    <section className="settings-pane active tw space-y-5" data-testid="mcp-settings">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <Network className="text-primary" /> MCP Servers
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Register local Model Context Protocol servers and Streamable HTTP endpoints for agentic coding.
            Every local process requires explicit approval, and every discovered tool remains disabled until classified.
          </p>
        </div>
        <Badge variant="muted">{servers.length} registered</Badge>
      </header>

      {status && (
        <div className="rounded-xl border border-border bg-card p-3 text-sm" role="status" aria-live="polite">
          {status}
        </div>
      )}

      {approvalCode && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
          <div>
            <strong>Approval code: {approvalCode}</strong>
            <p className="mt-1 text-xs text-muted-foreground">
              Approve the registration from the approval inbox before starting the local process.
            </p>
          </div>
          <Button type="button" size="sm" variant="outline" onClick={() => go?.("approvals")}>
            Open approvals
          </Button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => openDialog("streamable_http")}>
          <Link2 size={15} /> Add Streamable HTTP
        </Button>
        <Button type="button" variant="outline" onClick={() => openDialog("stdio")}>
          <Server size={15} /> Add local stdio
        </Button>
        {!hasExternalServer && (
          <Button type="button" variant="ghost" onClick={registerFixture} disabled={busy === "fixture"}>
            <Wrench size={15} /> Register operator fixture
          </Button>
        )}
      </div>

      <div className="grid gap-4">
        {servers.map((server) => {
          const tools = server.tools || [];
          const isInternal = server.transport === "internal";
          const isRunning = server.status === "running" || server.health === "running";
          const isExpanded = Boolean(expanded[server.id]);
          return (
            <article
              key={server.id}
              className="glow-card rounded-2xl border border-border bg-card p-5"
              data-testid={"mcp-server-" + server.id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{server.name || server.id}</h3>
                    <Badge variant={statusVariant(server)}>{titleize(server.compatibilityStatus || server.status)}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {server.transport === "streamable_http"
                      ? server.networkTarget || "Streamable HTTP target missing"
                      : isInternal
                        ? "Built-in Rasputin Tool Relay"
                        : serverCommand(server) || "Local stdio command missing"}
                  </p>
                  {!isInternal && server.cwd && (
                    <p className="mt-1 text-xs text-muted-foreground">Working directory: {server.cwd}</p>
                  )}
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Badge variant="outline">{server.toolCount || tools.length} tools</Badge>
                  {server.resourcesCount > 0 && <Badge variant="outline">{server.resourcesCount} resources</Badge>}
                  {server.pendingApprovalCode && <Badge variant="accent">Approval {server.pendingApprovalCode}</Badge>}
                </div>
              </div>

              {server.lastError && (
                <div className="mt-4 flex gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                  <ShieldAlert size={15} className="mt-0.5 shrink-0" /> {server.lastError}
                </div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                {!isInternal && !isRunning && (
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => runAction("Start", () => startMcpRelay(server))}
                    disabled={busy !== ""}
                  >
                    <Play size={14} /> Start
                  </Button>
                )}
                {!isInternal && isRunning && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => runAction("Stop", () => stopMcpRelay(server))}
                    disabled={busy !== ""}
                  >
                    <Square size={14} /> Stop
                  </Button>
                )}
                {!isInternal && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => runAction("Restart", () => restartMcpRelay(server))}
                    disabled={busy !== ""}
                  >
                    <RefreshCw size={14} /> Restart
                  </Button>
                )}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => runAction("Discover", () => discoverMcpRelay(server))}
                  disabled={busy !== ""}
                >
                  <RefreshCw size={14} /> Discover
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => runAction("Test", () => testMcpRelay(server))}
                  disabled={busy !== ""}
                >
                  <CheckCircle2 size={14} /> Test connection
                </Button>
                {!isInternal && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(server)}
                    disabled={busy !== ""}
                  >
                    <Trash2 size={14} /> Remove
                  </Button>
                )}
                {tools.length > 0 && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setExpanded((current) => ({ ...current, [server.id]: !isExpanded }))}
                  >
                    <Wrench size={14} /> {isExpanded ? "Hide tools" : "Manage tools"}
                  </Button>
                )}
              </div>

              {isExpanded && tools.length > 0 && (
                <div className="mt-4 grid gap-3 border-t border-border pt-4">
                  {tools.map((tool) => (
                    <div key={tool.id} className="rounded-xl border border-border/70 bg-background/50 p-3">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">{tool.display_name || tool.mcpToolName || tool.id}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{tool.description}</p>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {tool.classified ? titleize(tool.risk) : "Needs classification"} -{" "}
                            {tool.enabled ? "enabled" : "disabled"}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            onClick={() =>
                              runAction(
                                "Classify",
                                () => classifyMcpTool(tool.id, { risk: "guarded", permissionFlag: "", enabled: true }),
                              )
                            }
                            disabled={busy !== ""}
                          >
                            Allow guarded
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              runAction(
                                "Disable",
                                () => classifyMcpTool(tool.id, { risk: "guarded", permissionFlag: "", enabled: false }),
                              )
                            }
                            disabled={busy !== ""}
                          >
                            Disable
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => runAction("Test tool", () => callMcpTestTool(tool.id))}
                            disabled={!tool.enabled || busy !== ""}
                          >
                            Test tool
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          );
        })}

        {servers.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No MCP servers are registered yet. Add a Streamable HTTP endpoint or a local stdio server.
          </div>
        )}
      </div>

      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-xs text-muted-foreground">
        Local stdio commands run on this computer only after approval and inside an approved Rasputin workspace.
        Streamable HTTP servers may be remote, but any secret header is read from the environment variable named during setup.
        The installer includes Rasputin, llama.cpp, and the Python runtime; third-party MCP server packages still need their own executable or an HTTP endpoint.
        <a className="ml-1 inline-flex items-center gap-1 text-primary hover:underline" href="https://modelcontextprotocol.io/" target="_blank" rel="noreferrer">
          MCP specification <ExternalLink size={12} />
        </a>
      </div>

      {dialogOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setDialogOpen(false);
          }}
        >
          <form
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-primary/30 bg-card p-5 shadow-2xl"
            onSubmit={submit}
            role="dialog"
            aria-modal="true"
            aria-labelledby="mcp-server-dialog-title"
            data-testid="mcp-server-dialog"
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 id="mcp-server-dialog-title" className="font-semibold">
                  Add {form.transport === "stdio" ? "local stdio" : "Streamable HTTP"} server
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  The server definition is saved locally. Credentials are represented only by environment references.
                </p>
              </div>
              <Button type="button" variant="ghost" onClick={() => setDialogOpen(false)}>Cancel</Button>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm">
                <span className="mb-1.5 block font-medium">Display name</span>
                <input
                  className="w2-input w-full"
                  autoFocus
                  required
                  value={form.name}
                  onChange={(event) => updateForm("name", event.target.value)}
                  placeholder="Filesystem MCP"
                />
              </label>
              <label className="text-sm">
                <span className="mb-1.5 block font-medium">Stable ID (optional)</span>
                <input
                  className="w2-input w-full"
                  value={form.id}
                  onChange={(event) => updateForm("id", event.target.value)}
                  placeholder="filesystem-mcp"
                />
              </label>

              {form.transport === "stdio" ? (
                <>
                  <label className="text-sm md:col-span-2">
                    <span className="mb-1.5 block font-medium">Executable</span>
                    <input
                      className="w2-input w-full"
                      required
                      value={form.command}
                      onChange={(event) => updateForm("command", event.target.value)}
                      placeholder="npx, uvx, python, or an installed MCP executable"
                    />
                  </label>
                  <label className="text-sm md:col-span-2">
                    <span className="mb-1.5 block font-medium">Arguments</span>
                    <input
                      className="w2-input w-full"
                      value={form.args}
                      onChange={(event) => updateForm("args", event.target.value)}
                      placeholder="-y @modelcontextprotocol/server-filesystem C:\\workspace"
                    />
                  </label>
                  <label className="text-sm md:col-span-2">
                    <span className="mb-1.5 block font-medium">Approved working directory</span>
                    <input
                      className="w2-input w-full"
                      required
                      list="mcp-workspace-roots"
                      value={form.cwd}
                      onChange={(event) => updateForm("cwd", event.target.value)}
                      placeholder="Select an approved Rasputin workspace"
                    />
                    <datalist id="mcp-workspace-roots">
                      {roots.map((root) => <option key={root.id} value={root.absolute_path}>{root.name}</option>)}
                    </datalist>
                  </label>
                  {roots.length === 0 && (
                    <div className="md:col-span-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
                      Approve a workspace folder before registering a local stdio server.
                    </div>
                  )}
                </>
              ) : (
                <>
                  <label className="text-sm md:col-span-2">
                    <span className="mb-1.5 block font-medium">Streamable HTTP URL</span>
                    <input
                      className="w2-input w-full"
                      type="url"
                      required
                      value={form.networkTarget}
                      onChange={(event) => updateForm("networkTarget", event.target.value)}
                      placeholder="http://127.0.0.1:9000/mcp"
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1.5 block font-medium">Secret header (optional)</span>
                    <input
                      className="w2-input w-full"
                      value={form.headerName}
                      onChange={(event) => updateForm("headerName", event.target.value)}
                      placeholder="Authorization"
                    />
                  </label>
                  <label className="text-sm">
                    <span className="mb-1.5 block font-medium">Environment variable</span>
                    <input
                      className="w2-input w-full"
                      value={form.secretEnvName}
                      onChange={(event) => updateForm("secretEnvName", event.target.value)}
                      placeholder="MCP_TOKEN"
                    />
                  </label>
                  <div className="md:col-span-2 rounded-xl border border-border bg-background/50 p-3 text-xs text-muted-foreground">
                    Set the environment variable before launching Rasputin. The app never stores the secret itself.
                  </div>
                </>
              )}
            </div>

            <div className="mt-5 flex justify-end">
              <Button type="submit" disabled={busy === "register"}>
                <CheckCircle2 size={15} /> Register server
              </Button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
