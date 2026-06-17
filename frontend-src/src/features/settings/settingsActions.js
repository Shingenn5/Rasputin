import { api, postJson } from "../../api/client.js";
import { useSettingsStore } from "./settingsStore.js";

// Helper to quickly access store setters
const { setLoading, setError, clearError, setDomainSettings, setAllSettings } = useSettingsStore.getState();

/**
 * Loads all settings from the backend.
 */
export async function loadSettings() {
  setLoading(true);
  clearError("global");
  try {
    const data = await api("/api/settings");
    if (data) {
      setAllSettings(data);
    }
  } catch (err) {
    setError("global", "Failed to load settings from server.");
    console.error("loadSettings error:", err);
  } finally {
    setLoading(false);
  }
}

/**
 * Updates a specific setting domain.
 */
export async function updateSetting(domain, key, value) {
  setLoading(true);
  clearError(domain);
  try {
    const res = await postJson(`/api/settings/${domain}`, { key, value });
    if (res.error) throw new Error(res.error);
    
    // Optimistic update or refresh from response
    if (res.updatedSettings) {
      setDomainSettings(domain, res.updatedSettings);
    }
    return true;
  } catch (err) {
    setError(domain, err.message || `Failed to update ${key}`);
    console.error(`updateSetting error [${domain}]:`, err);
    return false;
  } finally {
    setLoading(false);
  }
}

/**
 * Validates a configuration before saving.
 */
export async function validateSetting(domain, config) {
  try {
    const res = await postJson(`/api/settings/validate/${domain}`, config);
    return res.valid;
  } catch (err) {
    console.error(`validateSetting error [${domain}]:`, err);
    return false;
  }
}

/**
 * Exports all settings.
 */
export async function exportSettings() {
  try {
    const data = await api("/api/settings/export");
    // Trigger download in browser
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rasputin-settings-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    return true;
  } catch (err) {
    setError("global", "Failed to export settings.");
    console.error("exportSettings error:", err);
    return false;
  }
}

/**
 * Imports settings from a JSON configuration.
 */
export async function importSettings(jsonConfig) {
  setLoading(true);
  clearError("global");
  try {
    const res = await postJson("/api/settings/import", jsonConfig);
    if (res.error) throw new Error(res.error);
    await loadSettings();
    return true;
  } catch (err) {
    setError("global", err.message || "Failed to import settings.");
    console.error("importSettings error:", err);
    return false;
  } finally {
    setLoading(false);
  }
}

/**
 * Restores defaults for a specific domain or all settings.
 */
export async function restoreDefaults(domain = "all") {
  setLoading(true);
  clearError(domain === "all" ? "global" : domain);
  try {
    const res = await postJson("/api/settings/restore", { domain });
    if (res.error) throw new Error(res.error);
    await loadSettings();
    return true;
  } catch (err) {
    setError(domain === "all" ? "global" : domain, "Failed to restore defaults.");
    console.error("restoreDefaults error:", err);
    return false;
  } finally {
    setLoading(false);
  }
}

/**
 * Runs diagnostics on a specific subsystem or overall.
 */
export async function runDiagnostics(category = "all") {
  setLoading(true);
  try {
    const res = await api(`/api/settings/diagnostics?category=${category}`);
    setDomainSettings("diagnostics", { ...useSettingsStore.getState().diagnostics, lastRun: res });
    return res;
  } catch (err) {
    setError("diagnostics", "Diagnostics run failed.");
    console.error("runDiagnostics error:", err);
    return null;
  } finally {
    setLoading(false);
  }
}

/**
 * Tests an integration connection.
 */
export async function testIntegration(integrationId) {
  try {
    return await postJson(`/api/settings/integrations/test`, { integrationId });
  } catch (err) {
    console.error("testIntegration error:", err);
    return { success: false, error: err.message };
  }
}

/**
 * Saves deployment governance policy.
 */
export async function saveDeploymentPolicy(policy) {
  return updateSetting("deployments", "policy", policy);
}

/**
 * Rotates secrets/API keys.
 */
export async function rotateSecrets(secretType) {
  setLoading(true);
  try {
    const res = await postJson("/api/settings/security/rotate", { secretType });
    if (res.error) throw new Error(res.error);
    return true;
  } catch (err) {
    setError("security", `Failed to rotate secret: ${err.message}`);
    console.error("rotateSecrets error:", err);
    return false;
  } finally {
    setLoading(false);
  }
}
