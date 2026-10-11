import { useCallback, useEffect, useMemo } from "react";

import { displayModelName, displayModelSecondary, runtimeStatus } from "../../lib/display.js";

import { recipesForMode } from "./promptRecipes.js";

export function useChatCommands(context) {
  const {
    setCmd,
    setCmdIndex,
    setSlashMenuDismissed,
    setObjective,
    composerRef,
    taskMode,
    setModePanelOpen,
    setModelPanelOpen,
    setRecipePanelMode,
    setRecipePanelRecipeId,
    setRecipePanelOpen,
    setTaskMode,
    setReasoningMode,
    resizeComposer,
    fileInputRef,
    attachments,
    setUiState,
    queueMessage,
    setAttachments,
    cmd,
    visibleModels,
    models,
    selectedModel,
    setSelectedModel,
    go,
    reasoningMode,
    activeMode,
    selectedModelObject,
    activeReasoning,
    queuedMessages,
    clearQueuedMessages,
    startNewChat,
    latestActiveTask,
    cancelTask,
    cmdQuery,
    cmdMenuRef,
    slashMenuDismissed,
    cmdIndex,
    modeOptions,
    reasoningOptions,
  } = context;

const closeCmd = useCallback((consumeSlashText = false) => {
    setCmd(null);
    setCmdIndex(0);
    setSlashMenuDismissed(false);
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
    setSlashMenuDismissed(false);
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
    const text = context.buildOutgoingMessage();
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
      items = visibleModels.map((model) => ({
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

  useEffect(() => {
    if (!cmd) return undefined;
    function closeOnOutsideClick(event) {
      if (cmdMenuRef.current && !cmdMenuRef.current.contains(event.target)) {
        setCmd(null);
        setCmdIndex(0);
        if (cmd.source === "typed") setSlashMenuDismissed(true);
      }
    }
    const attachTimer = window.setTimeout(() => {
      document.addEventListener("mousedown", closeOnOutsideClick);
    }, 0);
    return () => {
      window.clearTimeout(attachTimer);
      document.removeEventListener("mousedown", closeOnOutsideClick);
    };
  }, [cmd]);

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
      if (!cmd && !slashMenuDismissed) {
        setCmd({ path: null, source: "typed" });
        setCmdIndex(0);
      }
    } else {
      setSlashMenuDismissed(false);
      if (cmd?.source === "typed") setCmd(null);
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

  return { closeCmd, openCmd, openRecipePanel, applyRecipe, openFilePicker, cmdItems, runCmdItem, handleComposerChange, handleComposerKeyDown };
}
