import { useEffect } from "react";

import { api, postJson } from "../../api/client.js";
import { displayWorkspaceName } from "../../lib/display.js";

export function useWorkspaceMountActions(context) {
  const {
    approvePath,
    executeAction,
    loadWorkspaceRoots,
    setUiState,
    setKnowledgeStatus,
    setPrompt,
    currentPath,
    setShowAddModal,
    setMountHostPath,
    setMountReadOnly,
    setMountStatus,
    setMountSuccess,
    setMountWorkflowStep,
    setMountWorkflowPath,
    setMountWorkflowItem,
    setRecheckBusy,
    setRecheckStatus,
    setIsMounting,
    setCopied,
    setHostListing,
    setHostBrowseError,
    setHostBrowseLoading,
    setHostPathDraft,
    showAddModal,
    native,
    security,
    setHostRoots,
    setHostRootsMessage,
    hostBrowseLoading,
    mountHostPath,
    mountReadOnly,
    previewMount,
    requestMount,
    selectWorkspace,
    activeId,
    activeTrusted,
    setShowTrustModal,
    setWorkspaceTrust,
    setTrustBusy,
    hostShellUnavailable,
    activeHostShell,
    setShowShellModal,
    setWorkspaceHostShell,
    setShellBusy,
    mountPlan,
    setCopiedPendingPath,
    setPendingMountsOverride,
    mountWorkflowPath,
    approvePendingMount,
    removePendingMount,
    normalizePath,
  } = context;

  async function approveSubfolder(path) {
    if (!approvePath || !path) return;
    try {
      await executeAction("ApproveSubfolder", path, async () => {
        await approvePath(path);
        await loadWorkspaceRoots();
      }, setUiState);
    } catch (error) {
      setKnowledgeStatus(error.message);
    }
  }

  function launchTask(type) {
    if (!setPrompt) return;
    const folderName = displayWorkspaceName(currentPath);
    const path = currentPath;

    switch(type) {
      case 'summarize':
        setPrompt(`Summarize the contents and purpose of the approved workspace "${folderName}" at ${path}.`, "write");
        break;
      case 'analyze':
        setPrompt(`Analyze the approved workspace "${folderName}" at ${path}. Use local files, RAG citations, and Graphify evidence to summarize what the folder contains, call out important files, and list any uncertainty.`, "analyze");
        break;
      case 'search':
        setPrompt(`Search the workspace "${folderName}" for any security vulnerabilities or API keys left in the code.`, "analyze");
        break;
      case 'graph':
        setPrompt(`Review the Graphify relationships for the workspace "${folderName}". Identify any disjoint nodes or missing documentation links.`, "research");
        break;
      case 'docs':
        setPrompt(`Generate comprehensive documentation for the workspace "${folderName}" based on its indexed files.`, "write");
        break;
      case 'review':
        setPrompt(`Perform a code review on the active workspace "${folderName}". Point out any style violations or performance issues.`, "code");
        break;
      default:
        break;
    }
  }

  // --- Guided Mount Workflow (Streamlined Modal) ---
  const resetMountModal = () => {
    setShowAddModal(false);
    setMountHostPath("");
    setMountReadOnly(true);
    setMountStatus("");
    setMountSuccess(false);
    setMountWorkflowStep("saved");
    setMountWorkflowPath("");
    setMountWorkflowItem(null);
    setRecheckBusy(false);
    setRecheckStatus("");
    setIsMounting(false);
    setCopied(false);
    setHostListing(null);
    setHostBrowseError("");
    setHostBrowseLoading(false);
    setHostPathDraft("");
  };

  // Load host starting points (project folder, home, drive) when the picker opens.
  useEffect(() => {
    if (!showAddModal || (!native && !security?.allowDockerControl)) return;
    postJson("/api/workspace/host-browse", {})
      .then((data) => {
        const roots = data.roots || [];
        setHostRoots(roots);
        setHostRootsMessage(data.message || "");
        if (roots[0]?.path) browseHost(roots[0].path);
      })
      .catch((error) => setHostRootsMessage(error.message));
  }, [showAddModal, native, security?.allowDockerControl]);

  async function browseHost(path) {
    const target = String(path || "").trim();
    if (!target || hostBrowseLoading) return;
    setHostBrowseLoading(true);
    setHostBrowseError("");
    try {
      const listing = await postJson("/api/workspace/host-browse", { path: target });
      setHostListing(listing);
      setMountHostPath(listing.path);
      setHostPathDraft(listing.path);
    } catch (error) {
      setHostBrowseError(error.message);
    } finally {
      setHostBrowseLoading(false);
    }
  }

  async function handleAddFolderSubmit(e) {
    e.preventDefault();
    if (!mountHostPath) {
      setMountStatus("Host path is required.");
      return;
    }

    setIsMounting(true);
    setMountStatus("");

    try {
      await executeAction("MountFolder", mountHostPath, async () => {
        const formData = new FormData();
        formData.append("hostPath", mountHostPath);
        formData.append("name", displayWorkspaceName(mountHostPath));
        if (mountReadOnly) formData.append("readOnly", "on");

        // Linear chain: plan, then save the request exactly once. (This used
        // to hand off to a useEffect keyed on the parent's mountPlan state;
        // requestMount's own setMountPlan(...) call retriggered that same
        // effect, so every submit re-saved the same mount request in a tight
        // loop until the modal closed.)
        const plan = await previewMount({ preventDefault: () => {}, currentTarget: formData });
        if (plan?.error) throw new Error(plan.error);
        const saved = await requestMount(plan);
        if (native) {
          await selectWorkspace?.(saved?.workspace?.id || saved?.workspace?.path || plan.hostPath);
        }
        await loadWorkspaceRoots();
      }, setUiState);

      setMountSuccess(true);
      setMountWorkflowPath(mountHostPath);
      setMountWorkflowStep(native ? "ready" : "restart");
      setRecheckStatus(native ? "Folder is ready immediately." : "Restart Rasputin, then recheck this page.");
    } catch (error) {
      setMountStatus(error.message);
    } finally {
      setIsMounting(false);
    }
  }

  // --- Trusted Dev Mode ---
  function handleTrustToggleClick() {
    if (!activeId) return;
    if (activeTrusted) {
      revokeTrust();
    } else {
      setShowTrustModal(true);
    }
  }

  async function confirmEnableTrust() {
    if (!setWorkspaceTrust || !activeId) return;
    setTrustBusy(true);
    try {
      await setWorkspaceTrust(activeId, true);
      setShowTrustModal(false);
    } finally {
      setTrustBusy(false);
    }
  }

  async function revokeTrust() {
    if (!setWorkspaceTrust || !activeId) return;
    setTrustBusy(true);
    try {
      await setWorkspaceTrust(activeId, false);
    } finally {
      setTrustBusy(false);
    }
  }

  // --- Host Shell capability ---
  function handleShellToggleClick() {
    if (!activeId || hostShellUnavailable) return;
    if (activeHostShell) {
      revokeShell();
    } else {
      setShowShellModal(true);
    }
  }

  async function confirmEnableShell() {
    if (!setWorkspaceHostShell || !activeId) return;
    setShellBusy(true);
    try {
      await setWorkspaceHostShell(activeId, true);
      setShowShellModal(false);
    } finally {
      setShellBusy(false);
    }
  }

  async function revokeShell() {
    if (!setWorkspaceHostShell || !activeId) return;
    setShellBusy(true);
    try {
      await setWorkspaceHostShell(activeId, false);
    } finally {
      setShellBusy(false);
    }
  }

  async function copyMountVolume() {
    if (!mountPlan?.composeVolume) return;
    try {
      await navigator.clipboard.writeText(mountPlan.composeVolume);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setMountStatus("Copy failed. Select and copy the volume line manually.");
    }
  }

  // --- Pending Mounts panel ---
  async function copyPendingVolume(item) {
    if (!item?.composeVolume) return;
    try {
      await navigator.clipboard.writeText(item.composeVolume);
      setCopiedPendingPath(item.hostPath);
      setTimeout(() => setCopiedPendingPath(""), 2000);
    } catch (error) {
      console.error("Clipboard copy failed", error);
    }
  }

  async function refreshPendingMounts() {
    const payload = await api("/api/workspace/mount-requests");
    const requests = payload.requests || [];
    setPendingMountsOverride(requests);
    await loadWorkspaceRoots?.();
    return requests;
  }

  async function recheckMountWorkflow() {
    if (native) {
      await loadWorkspaceRoots?.();
      setMountWorkflowStep("ready");
      setRecheckStatus("Native folders are available immediately.");
      return;
    }
    setRecheckBusy(true);
    setRecheckStatus("Checking whether the restarted mount is available...");
    try {
      const requests = await refreshPendingMounts();
      const matching = requests.find((item) => normalizePath(item.hostPath) === normalizePath(mountWorkflowPath));
      setMountWorkflowItem(matching || null);
      if (matching?.ready) {
        setMountWorkflowStep("approve");
        setRecheckStatus("The mount is ready. Approve it to start working.");
      } else {
        setMountWorkflowStep("restart");
        setRecheckStatus("The mount is not ready yet. Restart Rasputin, then check again.");
      }
    } catch (error) {
      setRecheckStatus(`Recheck failed: ${error.message}`);
    } finally {
      setRecheckBusy(false);
    }
  }

  function handleApprovePendingMount(item) {
    return executeAction("ApprovePendingMount", item.hostPath, async () => {
      await approvePendingMount?.(item);
      await loadWorkspaceRoots?.();
    }, setUiState);
  }

  function handleRemovePendingMount(item) {
    return executeAction("RemovePendingMount", item.hostPath, async () => {
      await removePendingMount?.(item.hostPath);
    }, setUiState);
  }

  return { approveSubfolder, launchTask, resetMountModal, browseHost, handleAddFolderSubmit, handleTrustToggleClick, confirmEnableTrust, handleShellToggleClick, confirmEnableShell, copyMountVolume, copyPendingVolume, refreshPendingMounts, recheckMountWorkflow, handleApprovePendingMount, handleRemovePendingMount };
}
