import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bell,
  BrainCircuit,
  CheckCircle2,
  Download,
  FileWarning,
  Info,
  Plug,
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
import { settingsItems } from "../../lib/constants.js";
import { useSettingsStore } from "./settingsStore.js";
import { loadSettings, exportSettings, importSettings, restoreDefaults } from "./settingsActions.js";
import { SecuritySettings } from "./SecuritySettings.jsx";
import { DeploymentSettings } from "./DeploymentSettings.jsx";
import { RuntimeSettings } from "./RuntimeSettings.jsx";
import { ModelSettings } from "./ModelSettings.jsx";
import { IntegrationSettings } from "./IntegrationSettings.jsx";
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
  { label: "Platform", ids: ["deployments", "integrations", "about"] },
];

export function SettingsView(props) {
  const {
    view,
    section,
    setSection,
    setTheme,
    models,
    modeModelOverrides,
    setModeModelOverride,
    testingMode,
    updateTestingMode,
    security,
    session,
  } = props;
  const isAdmin = session?.role === "admin";
  const allowedSettings = useMemo(
    () => isAdmin ? settingsItems : settingsItems.filter(([id]) => ["accounts", "about"].includes(id)),
    [isAdmin],
  );
  const activeSetting = allowedSettings.find(([id]) => id === section) || allowedSettings[0] || settingsItems[0];
  const activeInspector = getInspectorText(activeSetting[0]);
  const ActiveIcon = iconMap[activeSetting[0]] || Settings2;
  const [searchQuery, setSearchQuery] = useState("");
  const loading = useSettingsStore((state) => state.loading);

  const visibleGroups = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return settingGroups
      .map((group) => ({
        ...group,
        items: allowedSettings.filter(([id, label, small]) =>
          group.ids.includes(id) && (!query || `${label} ${small}`.toLowerCase().includes(query))
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [allowedSettings, searchQuery]);

  useEffect(() => {
    if (view === "settings" && isAdmin) loadSettings();
  }, [isAdmin, view]);

  useEffect(() => {
    if (view === "settings" && !allowedSettings.some(([id]) => id === section)) {
      setSection(allowedSettings[0]?.[0] || "accounts");
    }
  }, [allowedSettings, section, setSection, view]);

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
          <button type="button" onClick={() => importSettings({})} disabled={loading}><Upload size={15} /> Import</button>
          <button type="button" onClick={exportSettings} disabled={loading}><Download size={15} /> Export</button>
          <button type="button" className="is-danger" onClick={() => restoreDefaults("all")} disabled={loading}><RefreshCw size={15} /> Reset</button>
        </div>}
      </header>

      <div className="settings-control-grid">
        <nav className="settings-control-rail" aria-label="Settings sections">
          <label className="settings-search">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              placeholder="Find a setting"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
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
                      className={`settings-nav-item ${section === id ? "is-active" : ""}`}
                      data-testid={`settings-${id}`}
                      aria-current={section === id ? "page" : undefined}
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
            <span className="settings-validation"><CheckCircle2 size={14} /> Schema valid</span>
          </div>

          <div className="settings-context-strip">
            <div><span>Validation</span><p>{activeInspector.validation}</p></div>
            <div><span>Operational impact</span><p><ShieldAlert size={13} /> {activeInspector.impact}</p></div>
            <div><span>Connected systems</span><p>{activeInspector.deps.length ? activeInspector.deps.join(" · ") : "Isolated configuration"}</p></div>
          </div>

          <div className="settings-panel-surface">
            {section === "general" && <GeneralSettings setTheme={setTheme} testingMode={testingMode} updateTestingMode={updateTestingMode} />}
            {section === "runtime" && <RuntimeSettings />}
            {section === "security" && <SecuritySettings />}
            {section === "accounts" && <AccountsSettings session={session} />}
            {section === "models" && <ModelSettings models={models} modeModelOverrides={modeModelOverrides} setModeModelOverride={setModeModelOverride} />}
            {section === "deployments" && <DeploymentSettings />}
            {section === "integrations" && <IntegrationSettings />}
            {section === "resources" && <ResourceSettings />}
            {section === "notifications" && <NotificationSettings />}
            {section === "audit" && <AuditSettings />}
            {section === "diagnostics" && <DiagnosticsSettings />}
            {section === "about" && <AboutSettings />}
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
    resources: { desc: "Set practical hardware ceilings for predictable local performance.", validation: "Host capacity and numeric bounds", impact: "May reduce task concurrency", deps: ["Runtime"] },
    notifications: { desc: "Decide which system events deserve your attention and where they appear.", validation: "Channel and event mapping", impact: "Changes alert delivery only", deps: ["Activity"] },
    audit: { desc: "Configure the durable record of agent actions and security-sensitive events.", validation: "Retention and storage policy", impact: "Changes compliance records", deps: ["Security", "Activity"] },
    diagnostics: { desc: "Inspect health signals and tune the evidence available for troubleshooting.", validation: "Diagnostic service checks", impact: "May increase local telemetry", deps: ["Runtime"] },
    about: { desc: "Review build identity, platform information, and project resources.", validation: "Build metadata", impact: "Read-only information", deps: [] },
  };
  return data[section] || { desc: "Configure Rasputin.", validation: "Standard schema checks", impact: "Low system impact", deps: [] };
}
