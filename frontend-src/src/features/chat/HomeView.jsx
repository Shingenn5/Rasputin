import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  BookOpen,
  Box,
  Brain,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileText,
  ListPlus,
  Laptop,
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
import {
  deleteAttachment,
  readableAttachmentSize,
  updateAttachmentRetention,
  uploadAttachment,
} from "../../lib/fileExtraction.js";
import { Avatar } from "../../components/Avatar.jsx";
import { CodeSandbox } from "../../components/CodeSandbox.jsx";
import { PromptRecipePanel } from "./PromptRecipePanel.jsx";
import { featuredRecipes, recipesForMode } from "./promptRecipes.js";

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

const featuredPromptRecipes = featuredRecipes()
  .filter((item) => ["analyze", "research", "code", "write"].includes(item.mode));

export function HomeView(props) {
  const {
    view,
    selectedModel,
    selectedModelObject,
    models,
    visibleModels,
    activeWorkspaceName,
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
  const recipeButtonRef = useRef(null);
  const previousThreadVersionRef = useRef("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [hasNewActivity, setHasNewActivity] = useState(false);
  const [modePanelOpen, setModePanelOpen] = useState(false);
  const [modelPanelOpen, setModelPanelOpen] = useState(false);
  const [recipePanelOpen, setRecipePanelOpen] = useState(false);
  const [recipePanelMode, setRecipePanelMode] = useState(taskMode);
  const [recipePanelRecipeId, setRecipePanelRecipeId] = useState(null);

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
    () => orderedHomeTasks.map((task) => `${task.id}:${task.status}:${task.progress}:${String(task.streamText || "").length}:${String(task.result || "").length}:${(task.logs || []).join("").length}`).join("|"),
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

  const openRecipePanel = useCallback((mode = taskMode, recipeId = null) => {
    setCmd(null);
    setCmdIndex(0);
    setModePanelOpen(false);
    setModelPanelOpen(false);
    setRecipePanelMode(mode);
    setRecipePanelRecipeId(recipeId);
    setRecipePanelOpen(true);
  }, [taskMode]);

  const applyRecipe = useCallback(({ recipe: selectedRecipe, objective: nextObjective }) => {
    setTaskMode(selectedRecipe.mode);
    if (selectedRecipe.reasoning && selectedRecipe.reasoning !== "auto") {
      setReasoningMode(selectedRecipe.reasoning);
    }
    setObjective(nextObjective);
    setRecipePanelOpen(false);
    setRecipePanelRecipeId(null);
    window.requestAnimationFrame(() => {
      composerRef.current?.focus();
      resizeComposer();
    });
  }, [resizeComposer, setObjective, setReasoningMode, setTaskMode]);

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function queueCurrentDraft() {
    if (attachments.length) {
      setUiState({ status: "failed", message: "Send attachments directly; attachment-aware queueing is not available yet." });
      return;
    }
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
      items = modeOptions.map((mode) => ({
        id: `prompt-mode-${mode.value}`,
        name: mode.label,
        hint: `${recipesForMode(mode.value).length} guided recipes - ${mode.description}`,
        run: () => openRecipePanel(mode.value),
      }));
    } else {
      items = [
        { id: "mode", name: "/mode", hint: `Switch task mode - now ${activeMode.label}.`, submenu: "mode" },
        { id: "model", name: "/model", hint: `Switch model - now ${displayModelName(selectedModelObject, models)}.`, submenu: "model" },
        { id: "reasoning", name: "/reasoning", hint: `Reasoning effort - now ${activeReasoning.label}.`, submenu: "reasoning" },
        { id: "attach", name: "/attach", hint: "Attach files to the next message.", run: openFilePicker },
        { id: "queue", name: "/queue", hint: "Queue the current draft to run after the active task.", run: queueCurrentDraft },
        ...(queuedMessages.length ? [{ id: "clear-queue", name: "/clear-queue", hint: `Remove ${queuedMessages.length} queued message${queuedMessages.length === 1 ? "" : "s"}.`, run: clearQueuedMessages }] : []),
        { id: "prompts", name: "/prompts", hint: "Guided prompt recipes for each mode.", submenu: "prompts" },
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
  }, [cmd, cmdQuery, taskMode, reasoningMode, selectedModel, selectedModelObject, models, visibleModels, queuedMessages.length, latestActiveTask?.id, openRecipePanel]);

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
      if (event.key === "Tab" && event.shiftKey) {
        setCmd(null);
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
    const combined = objective.trim();
    if (combined.startsWith("/")) return "";
    return combined || (attachments.length ? "Analyze the attached files." : "");
  }

  const handleSendTask = async (e) => {
    e.preventDefault();
    if (cmd) return; // Enter inside the command menu never submits.
    const combinedMessage = buildOutgoingMessage();
    if (!combinedMessage) return;

    if (composerBusy) {
      if (attachments.length) {
        setUiState({ status: "failed", message: "Wait for the active task to finish before sending attachments." });
        return;
      }
      queueMessage(combinedMessage);
      setObjective("");
      setAttachments([]);
      return;
    }

    try {
      await executeAction("SendTask", taskMode, async () => {
        const sent = await sendTask(null, combinedMessage, {
          attachmentIds: attachments.map((attachment) => attachment.id),
        });
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
    const availableSlots = Math.max(0, 8 - attachments.length);
    if (!availableSlots) {
      setUiState({ status: "failed", message: "A task can include at most 8 attachments." });
      return;
    }
    setUiState({ status: 'running', message: 'Validating and extracting attachments locally...' });
    const newAttachments = [];
    const failures = files.length > availableSlots ? [`Only the first ${availableSlots} files were attached; the limit is 8 per task.`] : [];
    for (const file of files.slice(0, availableSlots)) {
      try {
        newAttachments.push(await uploadAttachment(file));
      } catch (err) {
        console.error("Failed to parse file", file.name, err);
        failures.push(`${file.name}: ${err.message}`);
      }
    }
    if (newAttachments.length > 0) {
      setAttachments(prev => [...prev, ...newAttachments]);
      setUiState({
        status: failures.length ? 'failed' : 'success',
        message: failures.length
          ? `Attached ${newAttachments.length}; ${failures.join(" ")}`
          : `Attached ${newAttachments.length} file(s) with provenance`,
      });
      setTimeout(() => setUiState({ status: 'idle', message: '' }), 3000);
    } else {
      setUiState({ status: 'failed', message: failures.join(" ") || 'Failed to extract any supported file content.' });
    }
  };

  const changeAttachmentRetention = async (index, retention) => {
    const attachment = attachments[index];
    if (!attachment) return;
    try {
      const updated = await updateAttachmentRetention(attachment.id, retention);
      setAttachments((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...updated } : item));
      setUiState({ status: "success", message: retention === "save_artifact" ? `${attachment.name} will be saved as an artifact.` : `${attachment.name} will expire after this task.` });
    } catch (error) {
      setUiState({ status: "failed", message: error.message });
    }
  };

  const removeAttachment = async (index) => {
    const attachment = attachments[index];
    if (!attachment) return;
    try {
      await deleteAttachment(attachment.id);
      setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index));
    } catch (error) {
      setUiState({ status: "failed", message: error.message });
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

  return (
    <section className={`cc-layout app-view home-view tw ${view === "chat" ? "active" : ""}`} id="chatView" data-app-view="chat" tabIndex="-1">
      {/* Header */}
      <header className="cc-header">
        <div className="cc-header-left">
          <button className="icon-button cc-nav-trigger" type="button" aria-label="Toggle navigation" onClick={toggleSidebar}>
            <PanelLeftOpen size={19} />
          </button>
          <div className="cc-logo">
            <span className="ras-brand-sigil ras-brand-sigil-sm" aria-hidden="true"><span>R</span><i /></span>
            <span><strong>Rasputin</strong><small>{activeWorkspaceName || "No workspace selected"}</small></span>
          </div>
        </div>
        <div className="cc-status-area">
          <button
            className="cc-model-indicator"
            data-testid="header-model-indicator"
            type="button"
            onClick={() => {
              setRecipePanelOpen(false);
              setModelPanelOpen(true);
            }}
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
          <div className="cc-status-item cc-runtime-status" title={security?.native ? "Native workstation runtime" : "Docker server runtime"}>
            {security?.native ? <Laptop size={14} aria-hidden="true" /> : <Box size={14} aria-hidden="true" />}
            <span>{security?.native ? "Native" : "Docker"}</span>
          </div>
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
          <div className="cc-chat-column">
            {orderedHomeTasks.length === 0 ? (
              <div className="cc-quick-action-center">
                <div className="cc-empty-mark" aria-hidden="true"><span>R</span><i /><b /></div>
                <p className="cc-empty-kicker">READY · PRIVATE · LOCAL</p>
                <h1 className="cc-objective-title">What should we tackle?</h1>
                <p className="cc-objective-subtitle">Start with a goal, or choose a direction. Rasputin will keep the work grounded in your active workspace.</p>
                <div className="cc-quick-actions" aria-label="Featured prompt recipes">
                  {featuredPromptRecipes.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="cc-quick-action-chip"
                      data-testid="featured-prompt-recipe"
                      onClick={() => openRecipePanel(item.mode, item.id)}
                    >
                      <span><small>{labelize(item.mode)} recipe</small>{item.title}</span>
                      <BookOpen size={14} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="cc-thread-scroll" aria-live="polite" ref={threadScrollRef} onScroll={handleThreadScroll}>
                <div className="thread-list">
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
                  <button type="button" className="cc-jump-latest" onClick={jumpToLatest}>
                    Jump to latest
                  </button>
                )}
              </div>
            )}

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
                <div className="attachment-strip" data-testid="attachment-strip" aria-label="Attached files">
                  {attachments.map((att, idx) => (
                    <div key={att.id} className="attachment-chip" data-testid="attachment-chip">
                      <FileText size={14} color="var(--ras-primary)" />
                      <span className="attachment-chip-detail">
                        <span className="attachment-chip-name">{att.name}</span>
                        <small>{readableAttachmentSize(att.sizeBytes)} · {att.parser === "image_metadata" ? "image metadata" : att.parser} · {att.provenance?.length || 1} source chunk{att.provenance?.length === 1 ? "" : "s"}</small>
                      </span>
                      <label className="attachment-retention">
                        <span className="visually-hidden">Retention for {att.name}</span>
                        <select
                          data-testid="attachment-retention"
                          value={att.retention}
                          onChange={(event) => changeAttachmentRetention(idx, event.target.value)}
                          aria-label={`Retention for ${att.name}`}
                        >
                          <option value="use_once">Use once</option>
                          <option value="save_artifact">Save as artifact</option>
                          <option value="workspace_knowledge" disabled>Add to knowledge (next)</option>
                        </select>
                      </label>
                      <button type="button" aria-label={`Remove ${att.name}`} onClick={() => removeAttachment(idx)}>
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
                          onClick={() => {
                            setCmd((current) => ({ ...current, path: null }));
                            setCmdIndex(0);
                          }}
                        >
                          <ChevronLeft size={14} /> Commands
                        </button>
                        <span>{cmd.path === "mode" ? "Mode" : cmd.path === "model" ? "Model" : cmd.path === "reasoning" ? "Reasoning" : "Quick prompts"}</span>
                      </div>
                    )}
                    <div className="cmd-menu-list" id="composer-command-list" role="listbox" aria-label="Commands">
                      {cmdItems.length === 0 && <div className="cmd-menu-empty">No matching commands</div>}
                      {cmdItems.map((item, index) => (
                        <button
                          key={item.id}
                          type="button"
                          id={`composer-command-${index}`}
                          role="option"
                          aria-selected={index === cmdIndex}
                          data-testid="command-item"
                          className={index === cmdIndex ? "cmd-item is-active" : "cmd-item"}
                          onClick={() => runCmdItem(item)}
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
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={Boolean(cmd)}
                  aria-controls={cmd ? "composer-command-list" : undefined}
                  aria-activedescendant={cmd && cmdItems.length ? `composer-command-${cmdIndex}` : undefined}
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
                      ref={recipeButtonRef}
                      className="composer-chip"
                      data-testid="prompt-recipe-trigger"
                      title={`Browse guided prompts for ${activeMode.label} mode`}
                      onClick={() => (recipePanelOpen ? setRecipePanelOpen(false) : openRecipePanel(taskMode))}
                    >
                      <BookOpen size={14} />
                      <span>Recipes</span>
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
                <div className={`composer-feedback ${uiState.status !== 'idle' ? `is-${uiState.status}` : "is-failed"}`} role="status" aria-live="polite">
                  {uiState.status !== 'idle' ? uiState.message : composerStatus}
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".txt,.md,.csv,.tsv,.json,.yml,.yaml,.toml,.ini,.sql,.xml,.html,.css,.js,.py,.pdf,.docx,.xlsx,.png,.jpg,.jpeg,.gif,.webp"
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
              {recipePanelOpen && (
                <PromptRecipePanel
                  modes={modeOptions}
                  initialMode={recipePanelMode}
                  initialRecipeId={recipePanelRecipeId}
                  models={models}
                  modeModelOverrides={modeModelOverrides || {}}
                  modelKeyForMode={modelKeyForMode}
                  allowWebSearch={security.allowWebSearch !== false}
                  returnFocusRef={recipeButtonRef}
                  onApply={applyRecipe}
                  onClose={() => {
                    setRecipePanelOpen(false);
                    setRecipePanelRecipeId(null);
                  }}
                />
              )}
            </form>
          </div>
        </div>
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
  const status = task.status || "queued";
  const active = ["queued", "running", "paused"].includes(status);
  const runningPhase = [...(task.steps || [])].reverse().find((step) => step.kind === "phase" && step.status === "running")?.name;
  // Planning/execution streams remain available in task details; the chat
  // bubble presents only a direct chat reply or the final reflection so it
  // never flashes internal intermediate drafts as if they were the answer.
  const presentsAnswer = task.mode === "chat" || runningPhase === "chat" || runningPhase === "reflection";
  const liveText = presentsAnswer ? String(task.streamText || "") : "";
  const streaming = status === "running" && Boolean(liveText);
  const response = task.result || liveText || task.logs?.slice(-4).join("\n") || "Working...";
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
            <span className="status-pill status-running">
              {streaming ? "Generating…" : `${Number(task.progress || 0)}%`}
            </span>
          )}
        </div>
        <div
          className={`markdown-body${streaming ? " is-streaming" : ""}`}
          data-testid="chat-assistant-response"
          data-streaming={streaming ? "true" : "false"}
        >
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
