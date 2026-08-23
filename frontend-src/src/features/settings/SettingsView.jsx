import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Bell,
  BrainCircuit,
  CheckCircle2,
  Download,
  FileWarning,
  Info,
  Plug,
  Network,
  RefreshCw,
  Rocket,
  Search,
  Server as ServerIcon,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Stethoscope,
  Upload,
  Users,
} from "lucide-react";
import { GeneralSettings } from "./GeneralSettings.jsx";
import { settingsEssentialIds, settingsItems } from "../../lib/constants.js";
import { useSettingsStore } from "./settingsStore.js";
import { loadSettings, exportSettings, importSettings, restoreDefaults } from "./settingsActions.js";
import { SecuritySettings } from "./SecuritySettings.jsx";
import { DeploymentSettings } from "./DeploymentSettings.jsx";
import { RuntimeSettings } from "./RuntimeSettings.jsx";
import { ModelSettings } from "./ModelSettings.jsx";
import { IntegrationSettings } from "./IntegrationSettings.jsx";
import { McpSettings } from "./McpSettings.jsx";
import { ResourceSettings } from "./ResourceSettings.jsx";
import { NotificationSettings } from "./NotificationSettings.jsx";
import { AuditSettings } from "./AuditSettings.jsx";
import { DiagnosticsSettings } from "./DiagnosticsSettings.jsx";
import { AboutSettings } from "./AboutSettings.jsx";
import { AccountsSettings } from "./AccountsSettings.jsx";

const iconMap = {
  general: Settings2,
  runtime: Activity,
  security: ShieldCheck,
  accounts: Users,
  models: BrainCircuit,
  deployments: Rocket,
  integrations: Plug,
  mcp: Network,
  resources: ServerIcon,
  notifications: Bell,
  audit: FileWarning,
  diagnostics: Stethoscope,
  about: Info,
};

const settingGroups = [
  { label: "Experience", ids: ["general", "notifications"] },
  { label: "Intelligence", ids: ["models", "runtime", "resources"] },
  { label: "Governance", ids: ["security", "accounts", "audit", "diagnostics"] },
  { label: "Platform", ids: ["deployments", "integrations", "mcp", "about"] },
];

function isPlainSettingsObject(value) {
  return value !== null
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.getPrototypeOf(value) === Object.prototype;
}

export function SettingsView(props) {
  const {
    view,
    section,
    setSection,
    theme,
    setTheme,
    motionMode,
    setMotionMode,
    models,
    modeModelOverrides,
    setModeModelOverride,
    testingMode,
    updateTestingMode,
    security,
    session,
    workspaceRoots,
    mcpRelays,
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
  } = props;
  const isAdmin = session?.role === "admin";
  const desktopOnly = Boolean(security?.desktopOnly);
  const allowedSettings = useMemo(
    () => {
      const allowed = isAdmin ? settingsItems : settingsItems.filter(([id]) => ["accounts", "about"].includes(id));
      return desktopOnly ? allowed.filter(([id]) => id !== "deployments") : allowed;
    },
    [desktopOnly, isAdmin],
  );
  const effectiveSection = allowedSettings.some(([id]) => id === section)
    ? section
    : allowedSettings[0]?.[0] || "general";
  const activeSetting = allowedSettings.find(([id]) => id === effectiveSection) || allowedSettings[0] || settingsItems[0];
  const activeInspector = getInspectorText(activeSetting[0]);
  const ActiveIcon = iconMap[activeSetting[0]] || Settings2;
  const [searchQuery, setSearchQuery] = useState("");
  const [searchEditable, setSearchEditable] = useState(false);
  const [settingsScope, setSettingsScope] = useState(isAdmin ? "essentials" : "advanced");
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [importError, setImportError] = useState("");
  const importInputRef = useRef(null);
  const loading = useSettingsStore((state) => state.loading);
  const settingsErrors = useSettingsStore((state) => state.errors);
  const settingsError = Object.values(settingsErrors || {}).find(Boolean);
  const statusError = importError || settingsError;

  const settingsStatus = loading
    ? { tone: "loading", label: "Settings action in progress…", icon: <RefreshCw size={14} className="settings-status-spinner" aria-hidden="true" /> }
    : statusError
      ? { tone: "error", label: statusError, icon: <ShieldAlert size={14} aria-hidden="true" /> }
      : settingsLoaded
        ? { tone: "ready", label: "Settings loaded", icon: <CheckCircle2 size={14} aria-hidden="true" /> }
        : { tone: "loading", label: "Settings not loaded", icon: <RefreshCw size={14} aria-hidden="true" /> };

  const navigationSettings = useMemo(() => {
    const query = searchQuery.trim();
    if (!isAdmin || settingsScope === "advanced" || query) return allowedSettings;
    const essentials = allowedSettings.filter(([id]) => settingsEssentialIds.includes(id));
    return essentials.length ? essentials : allowedSettings;
  }, [allowedSettings, isAdmin, searchQuery, settingsScope]);

  const visibleGroups = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return settingGroups
      .map((group) => ({
        ...group,
        items: navigationSettings.filter(([id, label, small]) =>
          group.ids.includes(id) && (!query || `${label} ${small}`.toLowerCase().includes(query))
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [navigationSettings, searchQuery]);

  useEffect(() => {
    if (view === "settings" && isAdmin) {
      setSettingsLoaded(false);
      loadSettings().finally(() => setSettingsLoaded(true));
    }
  }, [isAdmin, view]);

  useEffect(() => {
    if (!resetDialogOpen) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setResetDialogOpen(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [resetDialogOpen]);

  const handleResetConfirm = async () => {
    setResetDialogOpen(false);
    await restoreDefaults("all");
  };

  const handleImportClick = () => {
    setImportError("");
    importInputRef.current?.click();
  };

  const handleImportFile = async (event) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;

    try {
      const parsed = JSON.parse(await file.text());
      if (!isPlainSettingsObject(parsed)) {
        throw new Error("Import file must contain a JSON object.");
      }
      const imported = await importSettings(parsed);
      if (!imported) setImportError("Failed to import settings.");
    } catch (error) {
      setImportError(error instanceof SyntaxError
        ? "Import file is empty or invalid JSON."
        : error?.message || "Import file could not be imported.");
    }
  };

  useEffect(() => {
    if (view === "settings" && !allowedSettings.some(([id]) => id === section)) {
      setSection(allowedSettings[0]?.[0] || "accounts");
    }
  }, [allowedSettings, section, setSection, view]);

  useEffect(() => {
    if (!isAdmin) {
      setSettingsScope("advanced");
    } else if (section && !settingsEssentialIds.includes(section)) {
      // Direct links to less-frequently-used sections remain valid and reveal
      // the full navigation automatically.
      setSettingsScope("advanced");
    }
  }, [isAdmin, section]);

  // Section changes must always restore the full navigation rail. In
  // particular, credential managers can mistake the first text-like control
  // left behind after Accounts unmounts for a username field and inject
  // "admin" into this filter.
  useEffect(() => {
    setSearchQuery("");
    setSearchEditable(false);
  }, [section]);

  return (
    <section className={`app-view settings-view tw ${view === "settings" ? "active" : ""}`} id="settingsShell" data-app-view="settings">
      <header className="settings-command-hero">
        <div className="settings-hero-copy">
          <span className="control-eyebrow"><span className="signal-dot" /> System control</span>
          <h1>Shape your Rasputin.</h1>
          <p>One control plane for local intelligence, runtime policy, and the boundaries your agents operate within.</p>
        </div>
        <div className="settings-posture" aria-label="Current system posture">
          <div><span>Runtime</span><strong>{security?.native ? "Native" : "Container"}</strong></div>
          <div><span>Models</span><strong>{models?.length || 0} ready</strong></div>
          <div><span>Guardrails</span><strong className="is-safe">Enforced</strong></div>
        </div>
        {isAdmin && <div className="settings-hero-actions" aria-label="Configuration actions">
          <button type="button" onClick={handleImportClick} disabled={loading}><Upload size={15} /> Import</button>
          <input
            ref={importInputRef}
            className="settings-import-input"
            type="file"
            accept="application/json"
            aria-label="Choose settings JSON file"
            onChange={handleImportFile}
            tabIndex={-1}
          />
          <button type="button" onClick={exportSettings} disabled={loading}><Download size={15} /> Export</button>
          <button type="button" className="is-danger" onClick={() => setResetDialogOpen(true)} disabled={loading}><RefreshCw size={15} /> Reset</button>
        </div>}
      </header>

      {resetDialogOpen && (
        <div className="settings-reset-backdrop">
          <div
            className="settings-reset-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-reset-title"
            aria-describedby="settings-reset-description"
          >
            <span className="control-eyebrow">Destructive action</span>
            <h2 id="settings-reset-title">Reset all settings?</h2>
            <p id="settings-reset-description">
              This restores every Settings section to its defaults, including runtime, security, model, and integration configuration. Existing settings will be replaced.
            </p>
            <div className="settings-reset-actions">
              <button type="button" data-testid="settings-reset-cancel" onClick={() => setResetDialogOpen(false)} autoFocus>
                Cancel
              </button>
              <button type="button" className="is-danger" data-testid="settings-reset-confirm" onClick={handleResetConfirm}>
                Reset all settings
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="settings-control-grid">
        <nav className="settings-control-rail" aria-label="Settings sections">
          {isAdmin && (
            <div className="settings-scope-toggle mb-3" role="group" aria-label="Settings view">
              <button
                type="button"
                className={`btn btn-sm ${settingsScope === "essentials" ? "btn-primary" : "btn-outline-secondary"}`}
                aria-pressed={settingsScope === "essentials"}
                data-testid="settings-scope-essentials"
                onClick={() => {
                  setSearchQuery("");
                  setSettingsScope("essentials");
                  if (!settingsEssentialIds.includes(section)) setSection("general");
                }}
              >
                Essentials
              </button>
              <button
                type="button"
                className={`btn btn-sm ${settingsScope === "advanced" ? "btn-primary" : "btn-outline-secondary"}`}
                aria-pressed={settingsScope === "advanced"}
                data-testid="settings-scope-advanced"
                onClick={() => setSettingsScope("advanced")}
              >
                All settings
              </button>
            </div>
          )}
          <label className="settings-search">
            <Search size={16} aria-hidden="true" />
            <input
              id="rasputin-settings-filter"
              name="rasputin-settings-filter"
              type="search"
              aria-label="Filter settings sections"
              placeholder="Find a setting"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              readOnly={!searchEditable}
              onFocus={() => setSearchEditable(true)}
              onBlur={() => setSearchEditable(false)}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck="false"
              data-1p-ignore="true"
              data-lpignore="true"
              data-bwignore="true"
            />
            <kbd>/</kbd>
          </label>
          <div className="settings-rail-scroll">
            {visibleGroups.map((group) => (
              <div className="settings-nav-group" key={group.label}>
                <span>{group.label}</span>
                {group.items.map(([id, label, small]) => {
                  const Icon = iconMap[id] || Settings2;
                  return (
                    <button
                      key={id}
                      type="button"
                      className={`settings-nav-item ${effectiveSection === id ? "is-active" : ""}`}
                      data-testid={`settings-${id}`}
                      aria-current={effectiveSection === id ? "page" : undefined}
                      onClick={() => setSection(id)}
                    >
                      <span className="settings-nav-icon"><Icon size={17} /></span>
                      <span><strong>{label}</strong><small>{small}</small></span>
                      <i aria-hidden="true" />
                    </button>
                  );
                })}
              </div>
            ))}
            {visibleGroups.length === 0 && <p className="settings-no-results">No settings match “{searchQuery}”.</p>}
          </div>
        </nav>

        <main className="settings-control-stage">
          <div className="settings-stage-heading">
            <span className="settings-stage-icon"><ActiveIcon size={23} /></span>
            <div>
              <span className="control-eyebrow">Configuration / {activeSetting[2]}</span>
              <h2>{activeSetting[1]}</h2>
              <p>{activeInspector.desc}</p>
            </div>
            <span className={"settings-validation is-" + settingsStatus.tone} role="status" aria-live="polite">
              {settingsStatus.icon} {settingsStatus.label}
            </span>
          </div>

          <div className="settings-context-strip">
            <div><span>Validation</span><p>{activeInspector.validation}</p></div>
            <div><span>Operational impact</span><p><ShieldAlert size={13} /> {activeInspector.impact}</p></div>
            <div><span>Connected systems</span><p>{activeInspector.deps.length ? activeInspector.deps.join(" · ") : "Isolated configuration"}</p></div>
          </div>

          <div className="settings-panel-surface">
            {effectiveSection === "general" && (
              <GeneralSettings
                theme={theme}
                setTheme={setTheme}
                motionMode={motionMode}
                setMotionMode={setMotionMode}
                testingMode={testingMode}
                updateTestingMode={updateTestingMode}
              />
            )}
            {effectiveSection === "runtime" && <RuntimeSettings />}
            {effectiveSection === "security" && <SecuritySettings desktopOnly={desktopOnly} />}
            {effectiveSection === "accounts" && <AccountsSettings session={session} />}
            {effectiveSection === "models" && <ModelSettings models={models} modeModelOverrides={modeModelOverrides} setModeModelOverride={setModeModelOverride} />}
            {effectiveSection === "deployments" && <DeploymentSettings />}
            {effectiveSection === "integrations" && <IntegrationSettings />}
            {effectiveSection === "mcp" && (
              <McpSettings
                mcpRelays={mcpRelays}
                workspaceRoots={workspaceRoots}
                registerMcpRelay={registerMcpRelay}
                registerMcpFixture={registerMcpFixture}
                startMcpRelay={startMcpRelay}
                stopMcpRelay={stopMcpRelay}
                restartMcpRelay={restartMcpRelay}
                removeMcpRelay={removeMcpRelay}
                discoverMcpRelay={discoverMcpRelay}
                testMcpRelay={testMcpRelay}
                classifyMcpTool={classifyMcpTool}
                callMcpTestTool={callMcpTestTool}
                go={go}
              />
            )}
            {effectiveSection === "resources" && <ResourceSettings />}
            {effectiveSection === "notifications" && <NotificationSettings />}
            {effectiveSection === "audit" && <AuditSettings />}
            {effectiveSection === "diagnostics" && <DiagnosticsSettings />}
            {effectiveSection === "about" && <AboutSettings desktopOnly={desktopOnly} />}
          </div>
        </main>
      </div>
    </section>
  );
}

function getInspectorText(section) {
  const data = {
    general: { desc: "Tune the application experience and the defaults every new session inherits.", validation: "Live type and range checks", impact: "Changes the interface and session defaults", deps: ["Archive", "Workspaces"] },
    runtime: { desc: "Balance speed, stability, and resource use for local task execution.", validation: "Resource limits and numeric bounds", impact: "Can affect new and running tasks", deps: ["WarSat"] },
    security: { desc: "Control authentication, secrets, approvals, and agent access boundaries.", validation: "Key and policy integrity checks", impact: "May end sessions or revoke capabilities", deps: ["All subsystems"] },
    accounts: { desc: "Manage local identities, appliance roles, and account lifecycle.", validation: "Unique usernames and strong local passwords", impact: "Controls who can sign in and administer the appliance", deps: ["Security", "Workspaces"] },
    models: { desc: "Register intelligence providers and choose how work routes between them.", validation: "Provider and model availability", impact: "Changes inference routing", deps: ["Runtime", "Tasks"] },
    deployments: { desc: "Define how isolated WarSat workers are created and operated.", validation: "Container deployment schema", impact: "Applies to newly created workers", deps: ["WarSat", "Models"] },
    integrations: { desc: "Connect Rasputin to the external services that extend your workflow.", validation: "Endpoint and credential checks", impact: "Changes available external actions", deps: ["Security"] },
    mcp: { desc: "Register local or Streamable HTTP Model Context Protocol servers and govern their tools.", validation: "Transport, approval, and tool policy checks", impact: "Changes the tools available to agentic runs", deps: ["Security", "Workspaces"] },
    resources: { desc: "Set practical hardware ceilings for predictable local performance.", validation: "Host capacity and numeric bounds", impact: "May reduce task concurrency", deps: ["Runtime"] },
    notifications: { desc: "Decide which system events deserve your attention and where they appear.", validation: "Channel and event mapping", impact: "Changes alert delivery only", deps: ["Activity"] },
    audit: { desc: "Configure the durable record of agent actions and security-sensitive events.", validation: "Retention and storage policy", impact: "Changes compliance records", deps: ["Security", "Activity"] },
    diagnostics: { desc: "Inspect health signals and tune the evidence available for troubleshooting.", validation: "Diagnostic service checks", impact: "May increase local telemetry", deps: ["Runtime"] },
    about: { desc: "Review build identity, platform information, and project resources.", validation: "Build metadata", impact: "Read-only information", deps: [] },
  };
  return data[section] || { desc: "Configure Rasputin.", validation: "Standard schema checks", impact: "Low system impact", deps: [] };
}
