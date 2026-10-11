import { api, postJson } from "../api/client.js";

export function useApprovalMemoryActions(context) {
  const {
    setApprovals,
    selectedTaskIdRef,
    loadTaskDetails,
    setGlobalStatus,
    setMemorySearchResults,
    setMemoryItems,
    setMemoryExpiredItems,
    setMemoryReview,
  } = context;

  async function refreshApprovals() {
    setApprovals(await api("/api/approvals"));
  }

  async function approveApproval(id) {
    const approval = await postJson(`/api/approvals/${id}/approve`, {});
    await refreshApprovals();
    if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });

    // Auto-resume Warsat deployments
    if (approval.action_type === "warsat_deploy" || approval.actionType === "warsat_deploy") {
      setGlobalStatus("Approval accepted. Starting deployment...");
      context.deployWarsatPlan();
    } else {
      setGlobalStatus("Approval accepted.");
    }
  }

  async function denyApproval(id) {
    await postJson(`/api/approvals/${id}/deny`, {});
    await refreshApprovals();
    if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    setGlobalStatus("Approval denied.");
  }

  async function searchMemory(query) {
    if (!query.trim()) return;
    setMemorySearchResults(await postJson("/api/memory/search", { query, limit: 10 }));
  }

  async function refreshMemoryItems() {
    const [saved, expired] = await Promise.all([
      api("/api/memory/items?status=saved&limit=200"),
      api("/api/memory/items?status=expired&limit=200"),
    ]);
    setMemoryItems(saved);
    setMemoryExpiredItems(expired);
  }

  async function addMemory(payload) {
    const result = await postJson("/api/memory", payload);
    await refreshMemoryItems();
    setGlobalStatus("Memory saved.");
    return result;
  }

  async function updateMemory(id, payload) {
    const result = await api(`/api/memory/items/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    await refreshMemoryItems();
    setMemorySearchResults((current) => ({
      ...current,
      items: (current.items || []).map((item) => item.id === id ? result : item),
    }));
    setGlobalStatus("Memory updated.");
    return result;
  }

  async function deleteMemory(id) {
    await api(`/api/memory/items/${id}`, { method: "DELETE" });
    await refreshMemoryItems();
    setMemorySearchResults((current) => ({ ...current, items: (current.items || []).filter((item) => item.id !== id) }));
    setGlobalStatus("Memory deleted.");
  }

  async function approveMemory(id) {
    await postJson("/api/memory/review", { id, action: "approve" });
    setMemoryReview(await api("/api/memory/review"));
    setGlobalStatus("Memory saved.");
  }

  async function rejectMemory(id) {
    await postJson("/api/memory/review", { id, action: "reject" });
    setMemoryReview(await api("/api/memory/review"));
    setGlobalStatus("Memory rejected.");
  }

  return { refreshApprovals, approveApproval, denyApproval, searchMemory, addMemory, updateMemory, deleteMemory, approveMemory, rejectMemory };
}
