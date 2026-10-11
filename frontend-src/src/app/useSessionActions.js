import { api, postJson } from "../api/client.js";

export function useSessionActions(context) {
  const {
    setSessions,
    setChatFolders,
    selectedSession,
    setSelectedSession,
    activeChatSessionId,
    setActiveChatSessionId,
    setHomeTaskIds,
    setObjective,
    setGlobalStatus,
    setTasks,
    go,
  } = context;

  async function loadChatFolders() {
    const [nextSessions, nextFolders] = await Promise.all([
      api("/api/sessions"),
      api("/api/chat-folders"),
    ]);
    setSessions(nextSessions);
    setChatFolders(nextFolders);
    return { sessions: nextSessions, chatFolders: nextFolders };
  }

  function clearDeletedSessionSelection(sessionIds) {
    if (sessionIds.includes(selectedSession?.session?.id)) setSelectedSession(null);
    if (!sessionIds.includes(activeChatSessionId)) return;
    setActiveChatSessionId(null);
    setHomeTaskIds(new Set());
    setObjective("");
  }

  async function deleteSession(sessionItem) {
    const sessionId = sessionItem?.id;
    if (!sessionId) return null;
    try {
      const result = await postJson(`/api/sessions/${sessionId}/delete`, {});
      clearDeletedSessionSelection([sessionId]);
      await loadChatFolders();
      return result;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function cleanupEmptySessions() {
    try {
      const result = await postJson("/api/sessions/cleanup-empty", {});
      clearDeletedSessionSelection(result.sessionIds || []);
      await loadChatFolders();
      return result;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function createChatFolder(event) {
    event.preventDefault();
    // currentTarget is nulled once the handler's synchronous phase ends, so
    // grab the form element before any await.
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const name = String(form.get("name") || "").trim();
    if (!name) {
      setGlobalStatus("Enter a folder name.");
      return null;
    }
    const nextFolders = await postJson("/api/chat-folders", { name });
    setChatFolders(nextFolders);
    formElement.reset();
    setGlobalStatus("Chat folder created.");
    return nextFolders;
  }

  async function assignSessionFolder(sessionId, folder) {
    if (!sessionId) return null;
    const detail = await postJson(`/api/sessions/${sessionId}/folder`, { folder: folder || "" });
    await loadChatFolders();
    if (selectedSession?.session?.id === sessionId) setSelectedSession(detail);
    setGlobalStatus(folder ? "Chat moved to folder." : "Chat moved to Unfiled.");
    return detail;
  }

  async function loadSession(sessionId) {
    try {
      setSelectedSession(await api(`/api/sessions/${sessionId}`));
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function resumeSession(sessionId) {
    try {
      const detail = await api(`/api/sessions/${sessionId}`);
      const sessionTasks = detail.tasks || [];
      setSelectedSession(detail);
      setActiveChatSessionId(sessionId);
      setHomeTaskIds(new Set(sessionTasks.filter((task) => !task.parentId).map((task) => task.id)));
      setTasks((current) => {
        const next = new Map(current.map((task) => [task.id, task]));
        sessionTasks.forEach((task) => next.set(task.id, task));
        return Array.from(next.values()).sort((a, b) => Number(b.createdAt || 0) - Number(a.createdAt || 0));
      });
      setObjective("");
      go("chat");
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  return { loadChatFolders, deleteSession, cleanupEmptySessions, createChatFolder, assignSessionFolder, loadSession, resumeSession };
}
