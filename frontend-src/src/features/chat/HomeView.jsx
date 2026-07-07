import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Brain,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileText,
  ListPlus,
  Paperclip,
  Pause,
  PanelLeftOpen,
  Play,
  Settings,
  ShieldCheck,
  SquareSlash,
  Square,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import {
  displayModelName,
  displayModelSecondary,
  displayWorkspaceName,
  labelize,
  modelHealthLine,
  runtimeStatus,
} from "../../lib/display.js";
import { useReliableAction } from "../../lib/actionRegistry.js";
import { extractFileContent } from "../../lib/fileExtraction.js";
import { Avatar } from "../../components/Avatar.jsx";
import { CodeSandbox } from "../../components/CodeSandbox.jsx";

const modeOptions = [
  {
    value: "chat",
    label: "Chat",
    role: "main",
    description: "General conversation and local problem solving.",
    permission: "Uses the active workspace only when a task needs it.",
  },
  {
    value: "analyze",
    label: "Analyze",
    role: "executor",
    description: "Inspect mounted files, summarize structure, and compare evidence.",
    permission: "Read-only unless you approve a later mutation.",
  },
  {
    value: "research",
    label: "Research",
    role: "researcher",
    description: "Brokered research workflows with approval-gated web tools.",
    permission: "Models stay offline; only approved tools can reach out.",
  },
  {
    value: "code",
    label: "Code",
    role: "coder",
    description: "Repo analysis, patch planning, test guidance, and coding tasks.",
    permission: "Writes and shell execution remain approval-gated.",
  },
  {
    value: "write",
    label: "Write",
    role: "summarizer",
    description: "Draft Markdown, notes, summaries, and document outlines.",
    permission: "Exports only go to approved output folders.",
  },
  {
    value: "organize",
    label: "Organize",
    role: "executor",
    description: "Plan folder cleanup and file organization from mounted roots.",
    permission: "Folder changes require preview and approval.",
  },
  {
    value: "review",
    label: "Review",
    role: "summarizer",
    description: "Check prior output, summarize risk, and prepare follow-up edits.",
    permission: "Review uses local task history and approved workspace evidence.",
  },
];

const reasoningOptions = [
  { value: "auto", label: "Auto", description: "Use the model's default thinking behavior." },
  { value: "off", label: "Off", description: "Skip extended thinking for fast answers." },
  { value: "low", label: "Low", description: "Brief reasoning for simple tasks." },
  { value: "medium", label: "Medium", description: "Balanced reasoning depth." },
  { value: "high", label: "High", description: "Deep reasoning for hard problems." },
];

const modePlaceholders = {
  chat: "Message Rasputin...  ( / for commands )",
  analyze: "Ask about your documents or draft new ones...",
  research: "What are we researching?",
  code: "Describe the coding task...",
  write: "What should we draft?",
  organize: "Describe the folder cleanup or file organization job...",
  review: "What output should we review?",
};

const quickPrompts = [
  { text: "Deep dive a topic", mode: "research" },
  { text: "Find latest references", mode: "research" },
  { text: "Summarize active workspace", mode: "analyze" },
  { text: "Organize files", mode: "organize" },
  { text: "Review code", mode: "code" },
  { text: "Plan next feature", mode: "code" },
  { text: "Find bugs", mode: "code" },
  { text: "Brainstorm ideas", mode: "chat" },
];

export function HomeView(props) {
  const {
    activeWorkspaceName,
    view,
    selectedModel,
    selectedModelObject,
    models,
    visibleModels,
    setSelectedModel,
    security,
    go,
    toggleSidebar,
    homeTasks,
    objective,
    setObjective,
    sendTask,
    healthy,
    composerStatus,
    cancelTask,
    pauseTask,
    resumeTask,
    taskMode,
    setTaskMode,
    reasoningMode,
    setReasoningMode,
    queuedMessages,
    queueMessage,
    removeQueuedMessage,
    clearQueuedMessages,
    startNewChat,
    modeModelOverrides,
    setModeModelOverride,
    modelKeyForMode,
    subagentCount,
    setSubagentCount,
    runningTasks,
    openTaskDetails,
  } = props;

  const threadScrollRef = useRef(null);
  const composerRef = useRef(null);
  const fileInputRef = useRef(null);
  const modeButtonRef = useRef(null);
  const modePanelRef = useRef(null);
  const modelButtonRef = useRef(null);
  const modelPanelRef = useRef(null);
  const previousThreadVersionRef = useRef("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  const [modePanelOpen, setModePanelOpen] = useState(false);
  const [modelPanelOpen, setModelPanelOpen] = useState(false);

  // Phase 10: Button Reliability Framework State
  const [uiState, setUiState] = useState({ status: 'idle', message: '' });
  const executeAction = useReliableAction("HomeView");

  // Auto-grow the composer between its min (rows) and CSS max-height.
  const resizeComposer = useCallback(() => {
    const node = composerRef.current;
    if (!node) return;
    node.style.height = "auto";
    const max = parseFloat(getComputedStyle(node).maxHeight) || 220;
    const next = Math.min(node.scrollHeight, max);
    node.style.height = `${next}px`;
    node.style.overflowY = node.scrollHeight > max ? "auto" : "hidden";
  }, []);

  // Re-grow whenever the bound value changes (typing, paste, prompt-fill, clear).
  useEffect(() => { resizeComposer(); }, [objective, resizeComposer]);

  // Attachments (drag-and-drop or file picker)
  const [attachments, setAttachments] = useState([]);
  const [isDragging, setIsDragging] = useState(false);

  const orderedHomeTasks = useMemo(
    () => [...homeTasks].sort((a, b) => Number(a.createdAt || 0) - Number(b.createdAt || 0)),
    [homeTasks],
  );
  const threadVersion = useMemo(
    () => orderedHomeTasks.map((task) => `${task.id}:${task.status}:${task.progress}:${String(task.result || "").length}:${(task.logs || []).join("").length}`).join("|"),
    [orderedHomeTasks],
  );
  const activeHomeTasks = orderedHomeTasks.filter((task) => ["queued", "running", "paused"].includes(task.status));
  const latestActiveTask = activeHomeTasks[activeHomeTasks.length - 1] || runningTasks?.[0];
  const composerBusy = activeHomeTasks.length > 0;
  const privacyTitle = security.privacyLock ? "Local-only" : "Review mode";
  const privacyDetail = security.privacyLock ? "Models offline" : "Safety relaxed";
  const selectedModelHealthLine = modelHealthLine(selectedModelObject, models);
  const disabledReason = healthy ? "" : `${selectedModelHealthLine} Use Models to test or repair the local runtime, or enable Testing Mode.`;
  const activeMode = modeOptions.find((mode) => mode.value === taskMode) || modeOptions[0];
  const activeReasoning = reasoningOptions.find((option) => option.value === reasoningMode) || reasoningOptions[0];
  const objectivePlaceholder = modePlaceholders[activeMode.value] || modePlaceholders.chat;

  // Live header indicator: what model is routed and whether it is running.
  const modelIsMock = selectedModelObject?.key === "dry-run" || selectedModelObject?.provider === "mock";
  const modelRuntimeStatus = modelIsMock ? "reachable" : runtimeStatus(selectedModelObject);
  const modelStateLabel = !selectedModelObject
    ? "No model"
    : composerBusy && healthy
      ? "Generating"
      : modelIsMock
        ? "Testing"
        : modelRuntimeStatus === "reachable"
          ? "Running"
          : modelRuntimeStatus === "unknown"
            ? "Not checked"
            : "Stopped";

  // ---- Command menu (Claude Code style) -------------------------------
  // source "typed": opened by a leading "/" in the composer; the composer
  // text after "/" filters the list. source "button": opened from a toolbar
  // chip; browse with arrows/mouse, composer draft is left alone.
  const [cmd, setCmd] = useState(null); // null | { path, source }
  const [cmdIndex, setCmdIndex] = useState(0);

  const cmdQuery = cmd?.source === "typed" && objective.startsWith("/")
    ? objective.slice(1).trim().toLowerCase()
    : "";

  const closeCmd = useCallback((consumeSlashText = false) => {
    setCmd(null);
    setCmdIndex(0);
    if (consumeSlashText) {
      setObjective((current) => (typeof current === "string" && current.startsWith("/") ? "" : current));
    }
    window.requestAnimationFrame(() => composerRef.current?.focus());
  }, [setObjective]);

  const openCmd = useCallback((path = null) => {
    // With an empty composer, seed a "/" so typing filters the menu just like
    // a typed slash command; with a draft in progress, leave the text alone.
    const draft = composerRef.current?.value ?? "";
    if (!draft.trim()) {
      setObjective("/");
      setCmd({ path, source: "typed" });
    } else {
      setCmd({ path, source: "button" });
    }
    setCmdIndex(0);
    window.requestAnimationFrame(() => composerRef.current?.focus());
  }, [setObjective]);

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function queueCurrentDraft() {
    const text = buildOutgoingMessage();
    if (!text) return;
    queueMessage(text);
    setObjective("");
    setAttachments([]);
  }

  const cmdItems = useMemo(() => {
    let items = [];
    if (cmd?.path === "mode") {
      items = modeOptions.map((mode) => ({
        id: `mode-${mode.value}`,
        name: mode.label,
        hint: mode.description,
        active: taskMode === mode.value,
        run: () => setTaskMode(mode.value),
      }));
      items.push({
        id: "configure-modes",
        name: "Configure modes...",
        hint: "Per-mode model overrides and parallel sub-agents.",
        run: () => setModePanelOpen(true),
      });
    } else if (cmd?.path === "model") {
      const list = visibleModels.length ? visibleModels : models;
      items = list.map((model) => ({
        id: `model-${model.key}`,
        name: displayModelName(model, models),
        hint: displayModelSecondary(model, models) || model.key,
        dotStatus: model.key === "dry-run" || model.provider === "mock" ? "reachable" : runtimeStatus(model),
        active: model.key === selectedModel,
        run: () => setSelectedModel(model.key),
      }));
      items.push({
        id: "manage-models",
        name: "Manage models...",
        hint: "Deploy, test, and register models.",
        run: () => go("models"),
      });
    } else if (cmd?.path === "reasoning") {
      items = reasoningOptions.map((option) => ({
        id: `reasoning-${option.value}`,
        name: option.label,
        hint: option.description,
        active: reasoningMode === option.value,
        run: () => setReasoningMode(option.value),
      }));
    } else if (cmd?.path === "prompts") {
      items = quickPrompts.map((prompt, index) => ({
        id: `prompt-${index}`,
        name: prompt.text,
        hint: `${labelize(prompt.mode)} mode`,
        keepText: prompt.text,
        run: () => setTaskMode(prompt.mode),
      }));
    } else {
      items = [
        { id: "mode", name: "/mode", hint: `Switch task mode - now ${activeMode.label}.`, submenu: "mode" },
        { id: "model", name: "/model", hint: `Switch model - now ${displayModelName(selectedModelObject, models)}.`, submenu: "model" },
        { id: "reasoning", name: "/reasoning", hint: `Reasoning effort - now ${activeReasoning.label}.`, submenu: "reasoning" },
        { id: "attach", name: "/attach", hint: "Attach files to the next message.", run: openFilePicker },
        { id: "queue", name: "/queue", hint: "Queue the current draft to run after the active task.", run: queueCurrentDraft },
        ...(queuedMessages.length ? [{ id: "clear-queue", name: "/clear-queue", hint: `Remove ${queuedMessages.length} queued message${queuedMessages.length === 1 ? "" : "s"}.`, run: clearQueuedMessages }] : []),
        { id: "prompts", name: "/prompts", hint: "Starter prompts for each mode.", submenu: "prompts" },
        { id: "new", name: "/new", hint: "Start a new chat session.", run: () => startNewChat?.() },
        ...(latestActiveTask ? [{ id: "stop", name: "/stop", hint: "Stop the latest running task.", run: () => cancelTask(latestActiveTask.id) }] : []),
        { id: "models-view", name: "/models", hint: "Open the Models view.", run: () => go("models") },
        { id: "workspaces-view", name: "/workspaces", hint: "Open the Workspaces view.", run: () => go("workspaces") },
        { id: "activity-view", name: "/activity", hint: "Open the Activity view.", run: () => go("activity") },
        { id: "settings-view", name: "/settings", hint: "Open Settings.", run: () => go("settings", "general") },
      ];
    }
    if (!cmdQuery) return items;
    return items.filter((item) =>
      `${item.name} ${item.hint || ""}`.toLowerCase().includes(cmdQuery));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cmd, cmdQuery, taskMode, reasoningMode, selectedModel, selectedModelObject, models, visibleModels, queuedMessages.length, latestActiveTask?.id]);

  useEffect(() => { setCmdIndex(0); }, [cmdQuery, cmd?.path]);

  function runCmdItem(item) {
    if (!item) return;
    if (item.submenu) {
      setCmd((current) => ({ path: item.submenu, source: current?.source || "button" }));
      setCmdIndex(0);
      if (cmd?.source === "typed") setObjective("/");
      return;
    }
    closeCmd(true);
    item.run?.();
    if (item.keepText) setObjective(item.keepText);
  }

  function handleComposerChange(event) {
    const value = event.target.value;
    setObjective(value);
    if (value.startsWith("/")) {
      if (!cmd) {
        setCmd({ path: null, source: "typed" });
        setCmdIndex(0);
      }
    } else if (cmd?.source === "typed") {
      setCmd(null);
    }
  }

  function handleComposerKeyDown(event) {
    if (cmd) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setCmdIndex((index) => Math.min(index + 1, Math.max(cmdItems.length - 1, 0)));
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setCmdIndex((index) => Math.max(index - 1, 0));
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        runCmdItem(cmdItems[cmdIndex]);
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        runCmdItem(cmdItems[cmdIndex]);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        if (cmd.path) {
          setCmd((current) => ({ ...current, path: null }));
          setCmdIndex(0);
          return;
        }
        closeCmd(true);
        return;
      }
      if (event.key === "Backspace" && cmd.path && !cmdQuery) {
        event.preventDefault();
        setCmd((current) => ({ ...current, path: null }));
        setCmdIndex(0);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  }

  // ---- Sending / queueing ---------------------------------------------
  function buildOutgoingMessage() {
    let combined = objective.trim();
    if (combined.startsWith("/")) return "";
    if (attachments.length > 0) {
      const attachStr = attachments.map((a) => `<document name="${a.name}">\n${a.content}\n</document>`).join("\n\n");
      combined = combined ? `${combined}\n\n${attachStr}` : attachStr;
    }
    return combined;
  }

  const handleSendTask = async (e) => {
    e.preventDefault();
    if (cmd) return; // Enter inside the command menu never submits.
    const combinedMessage = buildOutgoingMessage();
    if (!combinedMessage) return;

    if (composerBusy) {
      queueMessage(combinedMessage);
      setObjective("");
      setAttachments([]);
      return;
    }

    try {
      await executeAction("SendTask", taskMode, async () => {
        const sent = await sendTask(null, combinedMessage);
        if (sent === false) throw new Error("Send failed. Check the model status.");
        setAttachments([]);
        setObjective("");
      }, setUiState);
    } catch (error) {
      console.error(error);
    }
  };

  const handleCancelTask = (id) => executeAction("CancelTask", id, async () => cancelTask(id), setUiState);
  const handlePauseTask = (id) => executeAction("PauseTask", id, async () => pauseTask(id), setUiState);
  const handleResumeTask = (id) => executeAction("ResumeTask", id, async () => resumeTask(id), setUiState);

  useEffect(() => {
    if (view !== "chat" || !threadScrollRef.current) return;
    const target = threadScrollRef.current;
    if (autoScroll) {
      window.requestAnimationFrame(() => {
        target.scrollTop = target.scrollHeight;
      });
    } else if (previousThreadVersionRef.current && previousThreadVersionRef.current !== threadVersion) {
      setHasNewActivity(true);
    }
    previousThreadVersionRef.current = threadVersion;
  }, [threadVersion, view, autoScroll]);

  useEffect(() => {
    if (!modePanelOpen) return undefined;
    const firstControl = modePanelRef.current?.querySelector("button, select, input");
    firstControl?.focus();
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setModePanelOpen(false);
        window.requestAnimationFrame(() => modeButtonRef.current?.focus());
      }
    }
    function closeOnOutsideClick(event) {
      if (modePanelRef.current && !modePanelRef.current.contains(event.target)) {
        setModePanelOpen(false);
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    // Some triggers open the panel from a mousedown handler (e.g. the command
    // menu's "Configure modes..." item), so that same native mousedown is
    // still bubbling toward document when this effect runs. Attaching the
    // outside-click listener on the next tick keeps it from catching the
    // tail of the very click that opened the panel.
    const attachTimer = window.setTimeout(() => {
      document.addEventListener("mousedown", closeOnOutsideClick);
    }, 0);
    return () => {
      window.clearTimeout(attachTimer);
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("mousedown", closeOnOutsideClick);
    };
  }, [modePanelOpen]);

  useEffect(() => {
    if (!modelPanelOpen) return undefined;
    const firstControl = modelPanelRef.current?.querySelector("button, select, input");
    firstControl?.focus();
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setModelPanelOpen(false);
        window.requestAnimationFrame(() => modelButtonRef.current?.focus());
      }
    }
    function closeOnOutsideClick(event) {
      if (modelPanelRef.current && !modelPanelRef.current.contains(event.target)) {
        setModelPanelOpen(false);
      }
    }
    document.addEventListener("keydown", closeOnEscape);
    const attachTimer = window.setTimeout(() => {
      document.addEventListener("mousedown", closeOnOutsideClick);
    }, 0);
    return () => {
      window.clearTimeout(attachTimer);
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("mousedown", closeOnOutsideClick);
    };
  }, [modelPanelOpen]);

  function handleThreadScroll(event) {
    const target = event.currentTarget;
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
    const atBottom = distanceFromBottom < 84;
    setAutoScroll(atBottom);
    if (atBottom) setHasNewActivity(false);
  }

  function jumpToLatest() {
    const target = threadScrollRef.current;
    if (!target) return;
    target.scrollTo({ top: target.scrollHeight, behavior: "smooth" });
    setAutoScroll(true);
    setHasNewActivity(false);
  }

  // ---- Attachments ------------------------------------------------------
  const addFiles = async (files) => {
    if (!files.length) return;
    setUiState({ status: 'running', message: 'Extracting file content...' });
    const newAttachments = [];
    for (const file of files) {
      try {
        const content = await extractFileContent(file);
        newAttachments.push({ name: file.name, content });
      } catch (err) {
        console.error("Failed to parse file", file.name, err);
      }
    }
    if (newAttachments.length > 0) {
      setAttachments(prev => [...prev, ...newAttachments]);
      setUiState({ status: 'success', message: `Attached ${newAttachments.length} file(s)` });
      setTimeout(() => setUiState({ status: 'idle', message: '' }), 3000);
    } else {
      setUiState({ status: 'failed', message: 'Failed to extract any text from files.' });
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    await addFiles(Array.from(e.dataTransfer.files));
  };

  const handleFileInput = async (e) => {
    await addFiles(Array.from(e.target.files || []));
    e.target.value = "";
  };

  const canSubmit = (objective.trim() && !objective.trim().startsWith("/")) || attachments.length > 0;
  const knowledgeGroup = activeMode.value === "research"
    ? "research"
    : ["analyze", "organize", "write"].includes(activeMode.value)
      ? "documents"
      : activeMode.value === "code"
        ? "coding"
        : "general";

  return (
    <section className={`cc-layout app-view home-view tw ${view === "chat" ? "active" : ""}`} id="chatView" data-app-view="chat" tabIndex="-1">
      {/* Header */}
      <header className="cc-header">
        <div className="cc-header-left">
          <button className="icon-button" type="button" aria-label="Open navigation" onClick={toggleSidebar}>
            <PanelLeftOpen size={19} />
          </button>
          <div className="cc-logo">
            <span className="brand-mark" aria-hidden="true">R</span>
            Rasputin
          </div>
        </div>
        <div className="cc-status-area">
          <button
            className="cc-model-indicator"
            data-testid="header-model-indicator"
            type="button"
            onClick={() => setModelPanelOpen(true)}
            title={`${selectedModelHealthLine} Click to change model.`}
          >
            <span
              className={`cc-model-dot status-${modelRuntimeStatus}${composerBusy && healthy ? " is-busy" : ""}`}
              aria-hidden="true"
            />
            <Cpu size={14} />
            <span className="cc-model-name">{displayModelName(selectedModelObject, models)}</span>
            <span className={`cc-model-state state-${modelRuntimeStatus}`}>{modelStateLabel}</span>
          </button>
          <div className="cc-status-item" title={`${privacyTitle}: ${privacyDetail}`}>
            <ShieldCheck size={14} /> <span>{privacyTitle}</span>
          </div>
          <button className="icon-button" type="button" aria-label="Open settings" onClick={() => go("settings", "general")}>
            <Settings size={18} />
          </button>
        </div>
      </header>

      <div className="cc-main-container" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
        {isDragging && (
          <div className="cc-drag-overlay" style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0, 196, 179, 0.1)', border: '2px dashed var(--ras-primary)',
            zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.5rem', color: 'var(--ras-primary)', fontWeight: 'bold'
          }}>
            Drop files to attach to context
          </div>
        )}
        {/* Content Area */}
        <div className="cc-content-area">
          {/* Quick Action Center */}
          <div className="cc-quick-action-center">
            <h1 className="cc-objective-title">What is our objective?</h1>

            <form id="taskForm" className="cc-input-container" onSubmit={handleSendTask}>
              {queuedMessages.length > 0 && (
                <div className="queue-strip" data-testid="queue-strip" aria-label="Queued messages">
                  <span className="queue-strip-label">{queuedMessages.length} queued</span>
                  {queuedMessages.map((entry) => (
                    <span key={entry.id} className="queued-chip" data-testid="queued-message" title={entry.text}>
                      <em>{labelize(entry.mode)}</em>
                      <span className="queued-chip-text">{entry.text}</span>
                      <button type="button" aria-label="Remove queued message" onClick={() => removeQueuedMessage(entry.id)}>
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                  <button type="button" className="tiny-action" onClick={clearQueuedMessages}>Clear all</button>
                </div>
              )}
              {attachments.length > 0 && (
                <div className="attachment-strip">
                  {attachments.map((att, idx) => (
                    <div key={idx} className="attachment-chip">
                      <FileText size={14} color="var(--ras-primary)" />
                      <span className="attachment-chip-name">{att.name}</span>
                      <button type="button" aria-label="Remove attachment" onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}>
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="composer-box">
                {cmd && (
                  <div className="cmd-menu" data-testid="command-menu">
                    {cmd.path && (
                      <div className="cmd-menu-crumb">
                        <button
                          type="button"
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setCmd((current) => ({ ...current, path: null }));
                            setCmdIndex(0);
                          }}
                        >
                          <ChevronLeft size={14} /> Commands
                        </button>
                        <span>{cmd.path === "mode" ? "Mode" : cmd.path === "model" ? "Model" : cmd.path === "reasoning" ? "Reasoning" : "Quick prompts"}</span>
                      </div>
                    )}
                    <div className="cmd-menu-list" role="listbox" aria-label="Commands">
                      {cmdItems.length === 0 && <div className="cmd-menu-empty">No matching commands</div>}
                      {cmdItems.map((item, index) => (
                        <button
                          key={item.id}
                          type="button"
                          role="option"
                          aria-selected={index === cmdIndex}
                          data-testid="command-item"
                          className={index === cmdIndex ? "cmd-item is-active" : "cmd-item"}
                          onMouseDown={(event) => {
                            event.preventDefault();
                            runCmdItem(item);
                          }}
                          onMouseEnter={() => setCmdIndex(index)}
                        >
                          {item.dotStatus && <span className={`model-choice-status status-${item.dotStatus}`} aria-hidden="true" />}
                          <span className="cmd-item-name">{item.name}</span>
                          <span className="cmd-item-hint">{item.hint}</span>
                          {item.active && <Check size={14} className="cmd-item-check" aria-hidden="true" />}
                          {item.submenu && <ChevronRight size={14} className="cmd-item-more" aria-hidden="true" />}
                        </button>
                      ))}
                    </div>
                    <footer className="cmd-menu-foot">
                      <span><kbd>Up</kbd><kbd>Down</kbd> navigate</span>
                      <span><kbd>Enter</kbd> select</span>
                      <span><kbd>Esc</kbd> close</span>
                    </footer>
                  </div>
                )}
                <label className="visually-hidden" htmlFor="objective">Message Rasputin</label>
                <textarea
                  id="objective"
                  ref={composerRef}
                  className="composer-input ras-autogrow"
                  rows={2}
                  placeholder={objectivePlaceholder}
                  value={objective}
                  onChange={handleComposerChange}
                  onInput={resizeComposer}
                  onKeyDown={handleComposerKeyDown}
                />
                <div className="composer-toolbar">
                  <div className="composer-tools">
                    <button type="button" className="composer-icon-button" aria-label="Attach files" title="Attach files" onClick={openFilePicker}>
                      <Paperclip size={16} />
                    </button>
                    <button type="button" className="composer-icon-button" aria-label="Open command menu" title="Commands ( / )" onClick={() => (cmd ? closeCmd(true) : openCmd(null))}>
                      <SquareSlash size={16} />
                    </button>
                    <button
                      type="button"
                      ref={modeButtonRef}
                      className="composer-chip"
                      data-testid="chat-mode-chip"
                      title={`${activeMode.label}: ${activeMode.description}`}
                      onClick={() => (cmd?.path === "mode" ? closeCmd(true) : openCmd("mode"))}
                    >
                      <Bot size={14} />
                      <span>{activeMode.label}</span>
                      <ChevronDown size={12} />
                    </button>
                    <button
                      type="button"
                      className="composer-chip"
                      data-testid="chat-reasoning-chip"
                      title={`Reasoning effort: ${activeReasoning.label}. ${activeReasoning.description}`}
                      onClick={() => (cmd?.path === "reasoning" ? closeCmd(true) : openCmd("reasoning"))}
                    >
                      <Brain size={14} />
                      <span>{activeReasoning.label}</span>
                      <ChevronDown size={12} />
                    </button>
                  </div>
                  <div className="composer-actions">
                    {latestActiveTask && (
                      <button type="button" className="composer-icon-button composer-stop-round" aria-label="Stop latest task" title="Stop the running task" onClick={() => handleCancelTask(latestActiveTask.id)}>
                        <Square size={14} />
                      </button>
                    )}
                    <button
                      type="button"
                      ref={modelButtonRef}
                      className="composer-chip composer-model-chip"
                      data-testid="chat-model-chip"
                      title={selectedModelHealthLine}
                      onClick={() => (cmd?.path === "model" ? closeCmd(true) : openCmd("model"))}
                    >
                      <span className={`cc-model-dot status-${modelRuntimeStatus}`} aria-hidden="true" />
                      <span className="composer-chip-model-name">{displayModelName(selectedModelObject, models)}</span>
                      <ChevronDown size={12} />
                    </button>
                    <button
                      id="sendBtn"
                      className="composer-send-round"
                      type="submit"
                      disabled={!canSubmit || (!composerBusy && !healthy)}
                      aria-disabled={!canSubmit || (!composerBusy && !healthy)}
                      aria-label={composerBusy ? "Queue message" : "Send message"}
                      title={!canSubmit ? "Enter a message" : composerBusy ? "A task is running - this message will queue and send when it finishes" : (disabledReason || "Send message")}
                    >
                      {composerBusy ? <ListPlus size={16} /> : <ArrowUp size={16} />}
                    </button>
                  </div>
                </div>
              </div>
              {(uiState.status !== 'idle' || composerStatus) && (
                <div className={`composer-feedback ${uiState.status !== 'idle' ? `is-${uiState.status}` : "is-failed"}`}>
                  {uiState.status !== 'idle' ? uiState.message : composerStatus}
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="visually-hidden"
                aria-label="Attach files"
                tabIndex={-1}
                onChange={handleFileInput}
              />

              {/* Render panels if open */}
              {modePanelOpen && (
                <ModeSidePanel
                  panelRef={modePanelRef}
                  modes={modeOptions}
                  activeMode={taskMode}
                  models={models}
                  visibleModels={visibleModels}
                  modeModelOverrides={modeModelOverrides || {}}
                  setModeModelOverride={setModeModelOverride}
                  modelKeyForMode={modelKeyForMode}
                  setTaskMode={(nextMode) => {
                    setTaskMode(nextMode);
                    setModePanelOpen(false);
                    window.requestAnimationFrame(() => modeButtonRef.current?.focus());
                  }}
                  subagentCount={subagentCount}
                  setSubagentCount={setSubagentCount}
                  close={() => {
                    setModePanelOpen(false);
                    window.requestAnimationFrame(() => modeButtonRef.current?.focus());
                  }}
                />
              )}
              {modelPanelOpen && (
                <ModelSidePanel
                  panelRef={modelPanelRef}
                  models={models}
                  visibleModels={visibleModels}
                  selectedModel={selectedModel}
                  setSelectedModel={(key) => {
                    setSelectedModel(key);
                    setModelPanelOpen(false);
                    window.requestAnimationFrame(() => modelButtonRef.current?.focus());
                  }}
                  close={() => {
                    setModelPanelOpen(false);
                    window.requestAnimationFrame(() => modelButtonRef.current?.focus());
                  }}
                />
              )}
            </form>
          </div>
        </div>

        {/* Context Sidebar */}
        <aside className="cc-sidebar">
          <div className="cc-sidebar-section">
            <h3 className="cc-sidebar-section-title">Recent Activity</h3>
            <div className="thread-list" aria-live="polite" style={{ padding: 0 }} ref={threadScrollRef} onScroll={handleThreadScroll}>
              {orderedHomeTasks.length === 0 && (
                <div className="cc-sidebar-item">
                  <p>No recent activity in this chat.</p>
                </div>
              )}
              {orderedHomeTasks.map((task) => (
                <TaskThread
                  key={task.id}
                  task={task}
                  models={models}
                  cancelTask={handleCancelTask}
                  pauseTask={handlePauseTask}
                  resumeTask={handleResumeTask}
                  openTaskDetails={openTaskDetails}
                />
              ))}
            </div>
            {hasNewActivity && (
              <button type="button" className="tiny-action" onClick={jumpToLatest}>
                Jump to latest
              </button>
            )}
          </div>

          <div className="cc-sidebar-section">
            <h3 className="cc-sidebar-section-title">Active Knowledge</h3>
            {knowledgeGroup === "research" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Graph Status</h4>
                  <p>Knowledge graph active and indexing...</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Web Access</h4>
                  <p>Enabled for deep research tasks.</p>
                </div>
              </>
            ) : knowledgeGroup === "documents" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Mounted Workspace</h4>
                  <p>{activeWorkspaceName || "No workspace selected"}</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Document Index</h4>
                  <p>Ready for summarization.</p>
                </div>
              </>
            ) : knowledgeGroup === "coding" ? (
              <>
                <div className="cc-sidebar-item">
                  <h4>Target Repository</h4>
                  <p>{activeWorkspaceName || "None"}</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Code Tools</h4>
                  <p>Read/Write enabled.</p>
                </div>
              </>
            ) : (
              <>
                <div className="cc-sidebar-item">
                  <h4>Current Mode</h4>
                  <p>{activeMode.label}</p>
                </div>
                <div className="cc-sidebar-item">
                  <h4>Local Context</h4>
                  <p>{activeWorkspaceName || "None"}</p>
                </div>
              </>
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

function ModelSidePanel({ panelRef, models, visibleModels, selectedModel, setSelectedModel, close }) {
  const items = visibleModels.length ? visibleModels : models;
  return (
    <aside
      ref={panelRef}
      className="model-side-panel"
      data-testid="model-side-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="modelPanelTitle"
    >
      <header className="mode-panel-head">
        <div>
          <span className="eyebrow">Runtime routing</span>
          <h2 id="modelPanelTitle">Choose model</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close model panel" onClick={close}>
          <X size={18} />
        </button>
      </header>
      <div className="model-panel-list">
        {items.map((model) => {
          const selected = model.key === selectedModel;
          const status = runtimeStatus(model);
          return (
            <button
              key={model.key}
              type="button"
              className={selected ? "model-choice is-active" : "model-choice"}
              data-testid="model-option"
              aria-pressed={selected}
              onClick={() => setSelectedModel(model.key)}
            >
              <span className={`model-choice-status status-${status}`} aria-hidden="true" />
              <span>
                <strong>{displayModelName(model, models)}</strong>
                <small>{displayModelSecondary(model, models) || model.key}</small>
              </span>
              <em>{status}</em>
            </button>
          );
        })}
      </div>
      <footer className="model-panel-footer">
        <p>Only user-facing chat models appear here. Embeddings and raw registry entries stay in Models settings.</p>
      </footer>
    </aside>
  );
}

function ModeSidePanel({
  panelRef,
  modes,
  activeMode,
  models,
  visibleModels,
  modeModelOverrides,
  setModeModelOverride,
  modelKeyForMode,
  setTaskMode,
  subagentCount,
  setSubagentCount,
  close,
}) {
  function modelForMode(mode) {
    const key = modelKeyForMode?.(mode.value, modeModelOverrides);
    return models.find((model) => model.key === key) || models.find((model) => model.role === mode.role) || null;
  }

  return (
    <aside
      ref={panelRef}
      className="mode-side-panel"
      data-testid="mode-side-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="modePanelTitle"
    >
      <header className="mode-panel-head">
        <div>
          <span className="eyebrow">Task routing</span>
          <h2 id="modePanelTitle">Choose mode</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Close mode panel" onClick={close}>
          <X size={18} />
        </button>
      </header>

      <div className="mode-panel-list">
        {modes.map((mode) => {
          const routed = modelForMode(mode);
          const override = modeModelOverrides?.[mode.value] || "";
          return (
            <article className={activeMode === mode.value ? "mode-card is-active" : "mode-card"} key={mode.value} data-testid="mode-option">
              <button type="button" className="mode-card-main" aria-pressed={activeMode === mode.value} onClick={() => setTaskMode(mode.value)}>
                <Bot size={18} aria-hidden="true" />
                <span>
                  <strong>{mode.label}</strong>
                  <small>{mode.description}</small>
                </span>
              </button>
              <dl className="mode-route-grid">
                <dt>Role</dt>
                <dd>{labelize(mode.role)}</dd>
                <dt>Model</dt>
                <dd>{routed ? displayModelName(routed, models) : "No routed model"}</dd>
                {routed && displayModelSecondary(routed, models) && (
                  <>
                    <dt>Registry</dt>
                    <dd>{displayModelSecondary(routed, models)}</dd>
                  </>
                )}
              </dl>
              <label className="mode-model-override">
                <span>Override model</span>
                <select
                  value={override}
                  aria-label={`${mode.label} model override`}
                  onChange={(event) => setModeModelOverride(mode.value, event.target.value)}
                >
                  <option value="">Use {labelize(mode.role)} route</option>
                  {visibleModels.map((model) => (
                    <option key={model.key} value={model.key}>{displayModelName(model, models)}</option>
                  ))}
                </select>
              </label>
              <p>{mode.permission}</p>
            </article>
          );
        })}
      </div>

      <section className="mode-subagent-panel" aria-label="Parallel sub-agent controls">
        <div>
          <h3>Parallel sub-agents</h3>
          <p>Use these for larger non-chat jobs. Normal chat messages can already run at the same time.</p>
        </div>
        <label>
          <span>Count</span>
          <input
            type="number"
            min="0"
            max="4"
            value={subagentCount}
            onChange={(event) => setSubagentCount(Math.max(0, Math.min(Number(event.target.value || 0), 4)))}
          />
        </label>
      </section>
    </aside>
  );
}

function TaskThread({ task, models, cancelTask, pauseTask, resumeTask, openTaskDetails }) {
  const response = task.result || task.logs?.slice(-4).join("\n") || "Working...";
  const status = task.status || "queued";
  const active = ["queued", "running", "paused"].includes(status);
  return (
    <article className="thread-item">
      <div className="message user-message">
        <div className="message-label">
          <Avatar kind="user" name="You" size="sm" />
          <span>You</span>
        </div>
        <div className="message-body user-bubble">{task.objective}</div>
      </div>
      <div className="message assistant-message">
        <div className="message-label assistant-label">
          <Avatar kind="model" name={displayModelName(task.model, models) || "Rasputin"} size="sm" />
          <span>Rasputin</span>
          <span className={`status-pill status-${status}`}>{status}</span>
          {active && (
            <span className="status-pill status-running">{Number(task.progress || 0)}%</span>
          )}
        </div>
        <div className="markdown-body">
          <ReactMarkdown
            rehypePlugins={[rehypeSanitize]}
            components={{
              code: CodeSandbox
            }}
          >
            {response}
          </ReactMarkdown>
        </div>
        <details className="runtime-details" data-testid="runtime-details-toggle">
          <summary>Details</summary>
          <dl className="detail-grid">
            <dt>Model</dt><dd>{displayModelName(task.model, models)}</dd>
            <dt>Mode</dt><dd>{task.mode || "chat"}</dd>
            {task.reasoning && task.reasoning !== "auto" && (
              <>
                <dt>Reasoning</dt><dd>{labelize(task.reasoning)}</dd>
              </>
            )}
            <dt>Workspace</dt><dd>{displayWorkspaceName(task.workspace)}</dd>
            <dt>Status</dt><dd>{status}</dd>
          </dl>
          <div className="task-inline-actions" aria-label="Task details">
            <button type="button" className="tiny-action" data-testid="activity-task-details" onClick={() => openTaskDetails(task.id)}>
              Open details
            </button>
          </div>
          {active && (
            <div className="task-inline-actions" aria-label="Task controls">
              {status === "paused" ? (
                <button type="button" className="tiny-action" onClick={() => resumeTask(task.id)}>
                  <Play size={13} />
                  Resume
                </button>
              ) : (
                <button type="button" className="tiny-action" onClick={() => pauseTask(task.id)}>
                  <Pause size={13} />
                  Pause
                </button>
              )}
              <button type="button" className="tiny-action danger" onClick={() => cancelTask(task.id)}>
                <Square size={13} />
                Stop
              </button>
            </div>
          )}
        </details>
      </div>
    </article>
  );
}
