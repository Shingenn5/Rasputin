import { api, postJson } from "../api/client.js";

export function useMcpActions(context) {
  const {
    setMcpRelays,
    setGlobalStatus,
    loadTools,
    loadTasks,
    openTaskDetails,
  } = context;

  async function loadMcpRelays() {
    const nextRelays = await api("/api/mcp/servers");
    setMcpRelays(nextRelays || { servers: [] });
    return nextRelays;
  }

  async function registerMcpRelay(payload) {
    const registered = await postJson("/api/mcp/servers", payload);
    await Promise.allSettled([loadMcpRelays(), context.refreshApprovals()]);
    setGlobalStatus(registered.approval?.code ? `MCP registration approval ${registered.approval.code} created.` : "MCP server registered.");
    return registered;
  }

  async function registerMcpFixture() {
    const registered = await postJson("/api/mcp/fixtures/operator/register", {});
    await Promise.allSettled([loadMcpRelays(), context.refreshApprovals()]);
    setGlobalStatus(registered.approval?.code ? `Operator fixture approval ${registered.approval.code} created.` : "Operator MCP fixture registered.");
    return registered;
  }

  async function startMcpRelay(server) {
    const approvalId = server?.pendingApprovalId || "";
    const started = await postJson(`/api/mcp/servers/${server.id}/start`, { approvalId });
    await Promise.allSettled([loadMcpRelays(), loadTools(), context.refreshApprovals()]);
    setGlobalStatus(`${started.name || server.id} started.`);
    return started;
  }

  async function stopMcpRelay(server) {
    const stopped = await postJson(`/api/mcp/servers/${server.id}/stop`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(`${stopped.name || server.id} stopped.`);
    return stopped;
  }

  async function restartMcpRelay(server) {
    const restarted = await postJson(`/api/mcp/servers/${server.id}/restart`, { approvalId: server?.pendingApprovalId || "" });
    await Promise.allSettled([loadMcpRelays(), loadTools(), context.refreshApprovals()]);
    setGlobalStatus(`${restarted.name || server.id} restarted.`);
    return restarted;
  }

  async function removeMcpRelay(server) {
    const removed = await api(`/api/mcp/servers/${encodeURIComponent(server.id)}`, { method: "DELETE" });
    await Promise.allSettled([loadMcpRelays(), loadTools(), context.refreshApprovals()]);
    setGlobalStatus(`${server.name || server.id} removed.`);
    return removed;
  }

  async function discoverMcpRelay(server) {
    const discovered = await postJson(`/api/mcp/servers/${server.id}/discover`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(discovered.message || `Discovered tools for ${server.name || server.id}.`);
    return discovered;
  }

  async function testMcpRelay(server) {
    const tested = await postJson(`/api/mcp/servers/${server.id}/test`, {});
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(tested.message || `${server.name || server.id} initialized.`);
    return tested;
  }

  async function classifyMcpTool(toolId, payload) {
    const classified = await postJson(`/api/mcp/tools/${encodeURIComponent(toolId)}/classify`, payload);
    await Promise.allSettled([loadMcpRelays(), loadTools()]);
    setGlobalStatus(`${classified.displayName || classified.id} classified.`);
    return classified;
  }

  async function callMcpTestTool(toolId, message = "operator fixture ok") {
    const detail = await postJson(`/api/mcp/tools/${encodeURIComponent(toolId)}/test-call`, { message });
    await Promise.allSettled([loadTasks(), loadTools(), loadMcpRelays()]);
    const taskId = detail?.task?.id;
    if (taskId) openTaskDetails(taskId);
    setGlobalStatus("MCP fixture tool call recorded in task details.");
    return detail;
  }

  return { loadMcpRelays, registerMcpRelay, registerMcpFixture, startMcpRelay, stopMcpRelay, restartMcpRelay, removeMcpRelay, discoverMcpRelay, testMcpRelay, classifyMcpTool, callMcpTestTool };
}
