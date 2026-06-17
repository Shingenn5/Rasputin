import React, { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Nav, Row, Stack } from "react-bootstrap";
import { CheckCircle2, Download, Upload, RefreshCw, Save, ShieldAlert, ShieldCheck, Square, Wrench, Search, Info, Settings2, Activity, BrainCircuit, Rocket, Plug, Server as ServerIcon, Bell, FileWarning, Stethoscope } from "lucide-react";
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

// Import existing settings components that haven't been rewritten yet, if they exist
// For now, we will create stubs for the new categories.

export function SettingsView(props) {
  const { view, section, setSection } = props;
  const activeSetting = settingsItems.find(([id]) => id === section) || settingsItems[0];
  const [searchQuery, setSearchQuery] = useState("");
  const loading = useSettingsStore(state => state.loading);

  const iconMap = {
    general: Settings2,
    runtime: Activity,
    security: ShieldCheck,
    models: BrainCircuit,
    deployments: Rocket,
    integrations: Plug,
    resources: ServerIcon,
    notifications: Bell,
    audit: FileWarning,
    diagnostics: Stethoscope,
    about: Info
  };

  useEffect(() => {
    if (view === "settings") {
      loadSettings();
    }
  }, [view]);

  return (
    <section className={`app-view settings-view ${view === "settings" ? "active" : ""}`} id="settingsShell" data-app-view="settings">
      {/* ── Settings Header ── */}
      <header className="page-header border-bottom bg-body d-flex justify-content-between align-items-center">
        <div>
          <h1 className="mb-0">Settings</h1>
          <p className="text-body-secondary mb-0">Platform configuration, governance, and deployment control plane.</p>
        </div>
        <div className="d-flex gap-2 align-items-center">
          <div className="input-group input-group-sm">
            <span className="input-group-text bg-body-tertiary"><Search size={14} /></span>
            <Form.Control 
              placeholder="Search Settings..." 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: "200px" }}
            />
          </div>
          <Button variant="outline-secondary" size="sm" onClick={() => importSettings({})} disabled={loading}>
            <Upload size={14} className="me-1" /> Import Config
          </Button>
          <Button variant="outline-secondary" size="sm" onClick={exportSettings} disabled={loading}>
            <Download size={14} className="me-1" /> Export Config
          </Button>
          <Button variant="outline-danger" size="sm" onClick={() => restoreDefaults("all")} disabled={loading}>
            <RefreshCw size={14} className="me-1" /> Restore Defaults
          </Button>
        </div>
      </header>

      <div className="settings-layout gui-workspace settings-gui-workspace">
        {/* ── Left Navigation ── */}
        <Nav className="settings-nav flex-column bg-body-tertiary gui-sidebar" aria-label="Settings sections">
          {settingsItems.map(([id, label, small]) => {
            const Icon = iconMap[id] || Square;
            return (
              <Button
                key={id}
                type="button"
                variant={section === id ? "primary" : "light"}
                className="settings-tab text-start d-flex align-items-center gap-3"
                data-testid={`settings-${id}`}
                aria-current={section === id ? "page" : undefined}
                onClick={() => setSection(id)}
              >
                <Icon size={18} className="flex-shrink-0" />
                <span className="fw-medium">{label}</span>
              </Button>
            );
          })}
        </Nav>

        {/* ── Main Settings Panel ── */}
        <div className="settings-panels gui-main">
          {section === "general" && <GeneralSettings />}
          {section === "runtime" && <RuntimeSettings />}
          {section === "security" && <SecuritySettings />}
          {section === "models" && <ModelSettings />}
          {section === "deployments" && <DeploymentSettings />}
          {section === "integrations" && <IntegrationSettings />}
          {section === "resources" && <ResourceSettings />}
          {section === "notifications" && <NotificationSettings />}
          {section === "audit" && <AuditSettings />}
          {section === "diagnostics" && <DiagnosticsSettings />}
          {section === "about" && <AboutSettings />}
        </div>

        {/* ── Inspector Panel ── */}
        <aside className="settings-inspector-panel gui-inspector" aria-label="Settings inspector">
          <span className="eyebrow">Inspector</span>
          <h2>{activeSetting[1]}</h2>
          
          <div className="mt-4">
            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Description</h6>
            <p className="small mb-3">{getInspectorText(activeSetting[0]).desc}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Validation Rules</h6>
            <p className="small mb-3 text-success"><CheckCircle2 size={12} className="me-1" />{getInspectorText(activeSetting[0]).validation}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Impact Analysis</h6>
            <p className="small mb-3 text-warning"><ShieldAlert size={12} className="me-1" />{getInspectorText(activeSetting[0]).impact}</p>

            <h6 className="text-uppercase text-muted" style={{ fontSize: "0.75rem", letterSpacing: "1px" }}>Dependencies</h6>
            <div className="small">
              {getInspectorText(activeSetting[0]).deps.map(d => (
                <Badge bg="secondary" className="me-1 mb-1" key={d}>{d}</Badge>
              ))}
              {getInspectorText(activeSetting[0]).deps.length === 0 && <span className="text-muted">None</span>}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function PlaceholderPanel({ title, desc }) {
  return (
    <section className="settings-pane active">
      <div className="mb-4 border-bottom pb-3">
        <h2 className="mb-1">{title}</h2>
        <p className="text-body-secondary mb-0">{desc}</p>
      </div>
      <Card className="shadow-sm">
        <Card.Body className="text-center py-5">
          <Wrench size={48} className="text-muted mb-3" />
          <h4>Under Construction</h4>
          <p className="text-body-secondary">
            This module is being migrated to the Settings V3 Architecture.
          </p>
        </Card.Body>
      </Card>
    </section>
  );
}

function getInspectorText(section) {
  const data = {
    general: {
      desc: "Platform-wide behavioral settings and startup defaults.",
      validation: "Strict type checking on primitives.",
      impact: "Affects UI layout and default session loading.",
      deps: ["Archive", "Workspaces"]
    },
    runtime: {
      desc: "Controls system resource allocation and task execution limits.",
      validation: "Numeric bounds checking required.",
      impact: "May reject new Tasks if limits are reduced below current usage.",
      deps: ["WarSat"]
    },
    security: {
      desc: "Critical authentication and encryption management.",
      validation: "Cryptographic validation of keys.",
      impact: "High risk: Revoking tokens will terminate active agents.",
      deps: ["All Subsystems"]
    },
    deployments: {
      desc: "Governs WarSat container creation and operational rules.",
      validation: "Docker/K8s schema validation.",
      impact: "Changes apply to new containers only.",
      deps: ["WarSat", "Models"]
    }
  };
  
  return data[section] || {
    desc: "Configuration module for Rasputin.",
    validation: "Standard schema validation.",
    impact: "Low system impact.",
    deps: []
  };
}
