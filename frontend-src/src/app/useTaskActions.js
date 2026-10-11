import { api, postJson } from "../api/client.js";

import { isModelHealthy } from "../lib/display.js";

export function useTaskActions(context) {
  const {
    sessions,
    activeChatSessionId,
    selectedSession,
    setObjective,
    go,
    setGlobalStatus,
    workspace,
    selectedModel,
    taskMode,
    activeChatFolder,
    setHomeTaskIds,
    setSelectedSession,
    setActiveChatSessionId,
    objective,
    memoryMode,
    reasoningMode,
    selectedTaskContextCapsuleId,
    models,
    setComposerStatus,
    isolateWorkspace,
    setTasks,
    subagentCount,
    queryClient,
    setSessions,
    queuedMessages,
    loadTasks,
    selectedTaskIdRef,
    loadTaskDetails,
    supportsAgenticMode,
    reconcileCreatedTaskSnapshot,
  } = context;

  async function startNewChat() {
    try {
      const listedSession = (sessions?.sessions || []).find((item) => item.id === activeChatSessionId);
      const selectedIsEmpty = selectedSession?.session?.id === activeChatSessionId
        && !(selectedSession?.messages || []).some((message) => String(message.content || "").trim())
        && !(selectedSession?.tasks || []).length;
      if (activeChatSessionId && (listedSession?.isEmpty || selectedIsEmpty)) {
        setObjective("");
        go("chat");
        setGlobalStatus("The current chat is already empty and ready.");
        return selectedSession || { session: listedSession, messages: [], tasks: [] };
      }
      const detail = await postJson("/api/sessions", {
        title: "New chat",
        workspace: workspace.activePath || ".",
        model: selectedModel,
        mode: taskMode,
        skill: "general",
        folder: activeChatFolder && !["all", "unfiled"].includes(activeChatFolder) ? activeChatFolder : "",
      });
      const sessionId = detail?.session?.id;
      setHomeTaskIds(new Set());
      setSelectedSession(detail);
      setActiveChatSessionId(sessionId || null);
      setObjective("");
      go("chat");
      context.loadChatFolders().catch((error) => setGlobalStatus(error.message));
      setGlobalStatus("New chat created.");
      return detail;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function sendTask(event, customMessage = null, options = {}) {
    if (event) event.preventDefault();
    const message = customMessage || objective.trim();
    const mode = options.mode || taskMode;
    const requestedMemoryMode = options.memoryMode || memoryMode;
    const reasoning = options.reasoning || reasoningMode;
    const modelKey = options.model || selectedModel;
    const contextCapsuleId = options.contextCapsuleId || selectedTaskContextCapsuleId || undefined;
    const requestedModel = models.find((model) => model.key === modelKey) || null;
    if (mode !== "chat" && !supportsAgenticMode(requestedModel, mode)) {
      setComposerStatus("This workflow requires a healthy, tool-capable model certified for the selected mode.");
      return false;
    }
    if (!isModelHealthy(requestedModel)) {
      setComposerStatus("Select Testing Mode or test a healthy local model before sending.");
      return false;
    }
    if (!message) {
      setComposerStatus("Write a message first.");
      return false;
    }
    const tempId = `pending-${Date.now()}`;
    const tempTask = {
      id: tempId,
      sessionId: activeChatSessionId,
      objective: message,
      model: modelKey,
      skill: "general",
      mode,
      memoryMode: requestedMemoryMode,
      reasoning,
      isolateWorkspace: Boolean(isolateWorkspace && mode === "code"),
      contextCapsuleId,
      status: "queued",
      progress: 0,
      logs: ["queued"],
      result: "",
      outputs: [],
      sources: [],
      graph: [],
      trace: [],
      workspace: workspace.activePath || ".",
      parentId: null,
      createdAt: Date.now() / 1000,
    };
    setTasks((current) => [tempTask, ...current.filter((item) => item.id !== tempId)]);
    setHomeTaskIds((current) => new Set([...current, tempId]));
    if (!options.fromQueue) setObjective("");
    try {
      setComposerStatus("");
      const task = await postJson("/api/tasks", {
        objective: message,
        model: modelKey,
        deploymentFingerprint: requestedModel?.deployment_fingerprint || requestedModel?.deploymentFingerprint || undefined,
        skill: "general",
        mode,
        memoryMode: requestedMemoryMode,
        reasoning,
        subagents: subagentCount,
        workspacePath: workspace.activePath || ".",
        sessionId: activeChatSessionId || undefined,
        priority: options.priority || 0,
        scheduledFor: options.scheduledFor || undefined,
        maxAttempts: options.maxAttempts || 1,
        attachmentIds: options.attachmentIds || [],
        isolateWorkspace: Boolean(isolateWorkspace && mode === "code"),
        contextCapsuleId,
      });
      setTasks((current) => reconcileCreatedTaskSnapshot(current, task, tempId));
      queryClient.setQueryData(["tasks"], (current = []) => reconcileCreatedTaskSnapshot(current, task, tempId));
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setHomeTaskIds((current) => {
        const next = new Set(current);
        next.delete(tempId);
        next.add(task.id);
        return next;
      });
      setActiveChatSessionId(task.sessionId || activeChatSessionId);
      api("/api/sessions").then(setSessions).catch(() => {});
      setGlobalStatus(subagentCount ? `Agent run started with ${subagentCount} sub-agent${subagentCount === 1 ? "" : "s"}.` : "Task started.");
      return true;
    } catch (error) {
      setTasks((current) => current.filter((item) => item.id !== tempId));
      setHomeTaskIds((current) => {
        const next = new Set(current);
        next.delete(tempId);
        return next;
      });
      if (!options.fromQueue) setObjective(message);
      setComposerStatus(error.message);
      return false;
    }
  }

  async function queueMessage(text, options = {}) {
    const trimmed = String(text || "").trim();
    if (!trimmed) return null;
    const sent = await sendTask(null, trimmed, {
      ...options,
      mode: options.mode || taskMode,
      memoryMode: options.memoryMode || memoryMode,
      reasoning: options.reasoning || reasoningMode,
      fromQueue: true,
    });
    if (!sent) setObjective((current) => current || trimmed);
    return sent;
  }

  async function removeQueuedMessage(id) {
    await cancelTask(id);
  }

  async function clearQueuedMessages() {
    await Promise.all(queuedMessages.map((entry) => postJson(`/api/tasks/${entry.id}/cancel`, {})));
    await loadTasks();
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
    setGlobalStatus("Queued tasks cleared.");
  }

  async function cancelTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/cancel`, {});
      setGlobalStatus("Task stop requested.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function pauseTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/pause`, {});
      setGlobalStatus("Task paused.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function resumeTask(taskId) {
    try {
      await postJson(`/api/tasks/${taskId}/resume`, {});
      setGlobalStatus("Task resumed.");
      await loadTasks();
      if (selectedTaskIdRef.current) await loadTaskDetails(selectedTaskIdRef.current, { silent: true });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function retryTask(taskId) {
    try {
      const task = await postJson(`/api/tasks/${taskId}/retry`, {});
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
      setGlobalStatus("Task queued for retry.");
      return task;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function setTaskPriority(taskId, priority) {
    try {
      const task = await postJson(`/api/tasks/${taskId}/priority`, { priority });
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
      return task;
    } catch (error) {
      setGlobalStatus(error.message);
      return null;
    }
  }

  async function updateInboxEvent(eventId, action) {
    try {
      await postJson(`/api/inbox/${eventId}/${action}`, {});
      await queryClient.invalidateQueries({ queryKey: ["inbox"] });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  async function markAllInboxRead() {
    try {
      await postJson("/api/inbox/read-all", {});
      await queryClient.invalidateQueries({ queryKey: ["inbox"] });
    } catch (error) {
      setGlobalStatus(error.message);
    }
  }

  return { startNewChat, sendTask, queueMessage, removeQueuedMessage, clearQueuedMessages, cancelTask, pauseTask, resumeTask, retryTask, setTaskPriority, updateInboxEvent, markAllInboxRead };
}
