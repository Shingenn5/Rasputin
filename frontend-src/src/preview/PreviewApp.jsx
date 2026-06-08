import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Archive,
  Bot,
  CheckCircle2,
  ChevronDown,
  Cpu,
  FileText,
  Folder,
  Gauge,
  Home,
  Layers,
  Lock,
  PanelLeft,
  Play,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
} from "lucide-react";
import { themeOptions } from "../lib/constants.js";

const variants = [
  {
    id: "warmind-console",
    label: "Warmind Console",
    summary: "Dense command surface, dark technical framing, strong red/amber states.",
  },
  {
    id: "operator-desk",
    label: "Operator Desk",
    summary: "Professional workbench layout with more whitespace and clearer task grouping.",
  },
  {
    id: "archive-studio",
    label: "Archive Studio",
    summary: "Readability-first workspace for long chats, files, documents, and memory.",
  },
];

const screens = [
  ["home", "Home"],
  ["workspaces", "Workspaces"],
  ["activity", "Activity"],
  ["models", "Models"],
  ["warsat", "Warsat"],
  ["settings", "Settings"],
  ["panels", "Panels"],
];

const viewportPresets = [
  ["desktop", "Desktop", 1380],
  ["split", "Split", 1080],
  ["tablet", "Tablet", 820],
  ["mobile", "Mobile", 390],
];

const fixtures = {
  sessions: [
    ["Folder cleanup", "Organize / Project Root", "Files"],
    ["Paper source map", "Research / Writing", "Writing"],
    ["Docker model test", "Warsat / Models", "Builds"],
    ["Excel intake", "Analyze / Finance", "Work"],
  ],
  tasks: [
    ["Running", "Index workspace docs", "68%", "rag + graph"],
    ["Paused", "Draft folder plan", "approval", "file move preview"],
    ["Done", "Summarize PDF batch", "complete", "memory saved"],
  ],
  models: [
    ["llava-hf/llava-1.5-7b-hf", "reachable", "main local model"],
    ["qwen2.5-coder:7b", "starting", "coder helper"],
    ["text-embedding-local", "ready", "knowledge only"],
  ],
  files: [
    ["backend", "folder", "read-write", "indexed"],
    ["docs", "folder", "read-only", "indexed"],
    ["requirements.txt", "file", "1.2 KB", "previewable"],
    ["architecture.md", "file", "8.9 KB", "memory candidate"],
  ],
  approvals: [
    ["Deploy model container", "warsat_deploy", "pending", "15 min"],
    ["Write summary markdown", "fs_write", "approved", "executed"],
  ],
};

export function PreviewApp() {
  const initialScreen = currentScreen();
  const [screen, setScreen] = useState(initialScreen);
  const [variant, setVariant] = useState(localStorage.getItem("rasputin-preview-variant") || "warmind-console");
  const [theme, setTheme] = useState(localStorage.getItem("rasputin-theme") || "rasputin-dark");
  const [viewport, setViewport] = useState("desktop");
  const [showA11y, setShowA11y] = useState(true);
  const variantInfo = variants.find((item) => item.id === variant) || variants[0];
  const viewportWidth = Number(viewportPresets.find((item) => item[0] === viewport)?.[2] || 1380);

  useEffect(() => {
    document.body.dataset.ready = "true";
    document.body.classList.add("preview-body");
    return () => document.body.classList.remove("preview-body");
  }, []);

  useEffect(() => {
    localStorage.setItem("rasputin-preview-variant", variant);
  }, [variant]);

  useEffect(() => {
    localStorage.setItem("rasputin-theme", theme);
    window.rasputinTheme?.apply?.(theme);
  }, [theme]);

  useEffect(() => {
    const onPop = () => setScreen(currentScreen());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function navigate(nextScreen) {
    setScreen(nextScreen);
    window.history.pushState({}, "", `/preview/${nextScreen}`);
  }

  return (
    <main className={`preview-root preview-${variant}`} data-testid="gui-preview-view">
      <section className="preview-controller" aria-label="RasputinTest GUI preview controller">
        <div>
          <span className="preview-kicker">RasputinTest</span>
          <h1>GUI Preview Hub</h1>
          <p>{variantInfo.summary}</p>
        </div>
        <label>
          <span>Screen</span>
          <select data-testid="gui-preview-screen-select" value={screen} onChange={(event) => navigate(event.target.value)}>
            {screens.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>Variant</span>
          <select data-testid="gui-preview-variant-select" value={variant} onChange={(event) => setVariant(event.target.value)}>
            {variants.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>
        <label>
          <span>Theme</span>
          <select data-testid="gui-preview-theme-select" value={theme} onChange={(event) => setTheme(event.target.value)}>
            {themeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          <span>Viewport</span>
          <select data-testid="gui-preview-viewport-select" value={viewport} onChange={(event) => setViewport(event.target.value)}>
            {viewportPresets.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <button type="button" className="preview-toggle" onClick={() => setShowA11y((current) => !current)}>
          {showA11y ? "Hide checks" : "Show checks"}
        </button>
      </section>

      <section className="preview-stage-shell" style={{ "--preview-width": `${viewportWidth}px` }}>
        <div className="preview-stage" data-viewport={viewport}>
          <PreviewSidebar screen={screen} navigate={navigate} variant={variant} />
          <section className="preview-canvas" aria-label={`${variantInfo.label} ${screen} preview`}>
            <PreviewHeader screen={screen} variant={variantInfo} />
            {renderScreen(screen, variant)}
          </section>
        </div>
      </section>

      {showA11y && <AccessibilityChecklist variant={variantInfo} screen={screen} />}
    </main>
  );
}

function currentScreen() {
  const value = window.location.pathname.split("/").filter(Boolean)[1] || "home";
  return screens.some(([screen]) => screen === value) ? value : "home";
}

function PreviewSidebar({ screen, navigate, variant }) {
  const labels = { home: Home, workspaces: Folder, activity: Activity, models: Cpu, warsat: TerminalSquare, settings: Settings, panels: Layers };
  return (
    <aside className="preview-sidebar" data-variant={variant}>
      <div className="preview-brand">
        <span>R</span>
        <div>
          <strong>Rasputin</strong>
          <small>{variantLabel(variant)}</small>
        </div>
      </div>
      <button className="preview-new-chat" type="button"><Sparkles size={16} />New Chat</button>
      <nav aria-label="Preview screens">
        {screens.map(([id, label]) => {
          const Icon = labels[id] || Home;
          return (
            <button key={id} type="button" className={screen === id ? "is-active" : ""} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}>
              <Icon size={17} />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>
      <section className="preview-chat-list" aria-label="Mock recent chats">
        <header>
          <span>Recent Chats</span>
          <small>{fixtures.sessions.length}</small>
        </header>
        {fixtures.sessions.map(([title, meta, folder]) => (
          <article key={title}>
            <strong>{title}</strong>
            <span>{meta}</span>
            <small>{folder}</small>
          </article>
        ))}
      </section>
      <footer>
        <ShieldCheck size={15} />
        <span>Privacy locked</span>
      </footer>
    </aside>
  );
}

function PreviewHeader({ screen, variant }) {
  return (
    <header className="preview-header">
      <div>
        <span className="preview-kicker">{variant.label}</span>
        <h2>{screenLabel(screen)}</h2>
      </div>
      <div className="preview-status-row">
        <span><Lock size={14} />Local only</span>
        <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
      </div>
    </header>
  );
}

function renderScreen(screen, variant) {
  const map = {
    home: <HomePreview variant={variant} />,
    workspaces: <WorkspacesPreview variant={variant} />,
    activity: <ActivityPreview variant={variant} />,
    models: <ModelsPreview variant={variant} />,
    warsat: <WarsatPreview variant={variant} />,
    settings: <SettingsPreview variant={variant} />,
    panels: <PanelsPreview variant={variant} />,
  };
  return map[screen] || map.home;
}

function HomePreview({ variant }) {
  return (
    <div className="preview-home">
      <section className="preview-thread">
        <article className="preview-message user">Can you inspect my workspace and tell me what matters first?</article>
        <article className="preview-message assistant">
          <strong>Workspace read plan</strong>
          <p>I will scan approved folders, use local RAG and Graphify context, then return citations before suggesting any file changes.</p>
        </article>
      </section>
      <section className="preview-composer">
        <textarea defaultValue="Message Rasputin" aria-label="Preview message composer" />
        <div className="preview-runbar">
          {variant === "operator-desk" ? (
            <button type="button" className="preview-run-config"><Gauge size={16} />Run Config <span>Chat / local model</span></button>
          ) : (
            <>
              <button type="button"><Bot size={16} />Mode <strong>Chat</strong><ChevronDown size={14} /></button>
              <button type="button"><Cpu size={16} />Model <strong>llava-1.5</strong><ChevronDown size={14} /></button>
            </>
          )}
          <button type="button" className="preview-send"><Play size={16} />Send</button>
        </div>
      </section>
    </div>
  );
}

function WorkspacesPreview({ variant }) {
  return (
    <div className="preview-workspace">
      <section className="preview-pane roots">
        <h3>Approved folders</h3>
        {["Project Root", "Research PDFs", "Writing Output"].map((root) => <button key={root} type="button">{root}<span>mounted</span></button>)}
      </section>
      <section className="preview-pane files">
        <div className="preview-search"><Search size={15} /><span>/workspace/docs</span></div>
        {fixtures.files.map(([name, kind, detail, state]) => (
          <article key={name}>
            {kind === "folder" ? <Folder size={18} /> : <FileText size={18} />}
            <strong>{name}</strong>
            <span>{detail}</span>
            <small>{state}</small>
          </article>
        ))}
      </section>
      <section className="preview-pane preview">
        <h3>{variant === "archive-studio" ? "Reading Preview" : "Selected item"}</h3>
        <p>architecture.md is previewable. Index status, citations, and graph links stay visible before any mutation is allowed.</p>
      </section>
    </div>
  );
}

function ActivityPreview() {
  return (
    <div className="preview-activity">
      {fixtures.tasks.map(([status, title, progress, detail]) => (
        <article key={title}>
          <span className={`preview-state state-${status.toLowerCase()}`}>{status}</span>
          <strong>{title}</strong>
          <p>{detail}</p>
          <div><span style={{ width: progress.endsWith("%") ? progress : "44%" }} /></div>
          <button type="button">Open details</button>
        </article>
      ))}
    </div>
  );
}

function ModelsPreview() {
  return (
    <div className="preview-models">
      {fixtures.models.map(([name, status, purpose]) => (
        <article key={name}>
          <Cpu size={20} />
          <div>
            <strong>{name}</strong>
            <span>{purpose}</span>
          </div>
          <small>{status}</small>
        </article>
      ))}
    </div>
  );
}

function WarsatPreview() {
  return (
    <div className="preview-warsat">
      <section>
        <h3>Launch Recipe</h3>
        <div className="preview-form-grid">
          <span>vLLM CUDA</span>
          <span>Qwen/Qwen2.5-Coder-7B</span>
          <span>Port 8020</span>
          <span>Profile: Large</span>
        </div>
      </section>
      <section>
        <h3>Generated plan</h3>
        <p>Container binds to 127.0.0.1, no host network, no-new-privileges enabled.</p>
        <button type="button">Request deploy approval</button>
      </section>
    </div>
  );
}

function SettingsPreview() {
  const items = ["General", "Workspaces", "Safety", "Knowledge", "Output", "Appearance", "Admin"];
  return (
    <div className="preview-settings">
      <nav>{items.map((item) => <button key={item} type="button" className={item === "Appearance" ? "is-active" : ""}>{item}</button>)}</nav>
      <section>
        <h3>Appearance</h3>
        <p>The selected design must keep theme switching persistent, readable, and visible across the sidebar.</p>
        <div className="preview-theme-grid">{themeOptions.slice(0, 6).map(([value, label]) => <span key={value}>{label}</span>)}</div>
      </section>
    </div>
  );
}

function PanelsPreview() {
  return (
    <div className="preview-panels">
      <section>
        <h3>Model panel</h3>
        {fixtures.models.slice(0, 2).map(([name, status]) => <button key={name} type="button"><span>{name}</span><small>{status}</small></button>)}
      </section>
      <section>
        <h3>Mode panel</h3>
        {["Chat", "Analyze", "Research", "Code", "Write", "Organize"].map((mode) => <button key={mode} type="button">{mode}<small>local route</small></button>)}
      </section>
      <section>
        <h3>Approvals</h3>
        {fixtures.approvals.map(([summary, action, status, ttl]) => <article key={summary}><strong>{summary}</strong><span>{action}</span><small>{status} / {ttl}</small></article>)}
      </section>
    </div>
  );
}

function AccessibilityChecklist({ variant, screen }) {
  const checks = useMemo(() => [
    "Keyboard path reaches navigation, preview controller, cards, and panels.",
    "Focus rings use the active theme focus token.",
    "Sidebar colors are driven by theme variables, not fixed dark values.",
    "Interactive controls have visible labels or accessible names.",
    "Split and mobile widths avoid horizontal overflow.",
  ], []);
  return (
    <aside className="preview-a11y" data-testid="gui-preview-accessibility-checks">
      <div>
        <span className="preview-kicker">Accessibility</span>
        <strong>{variant.label} / {screenLabel(screen)}</strong>
      </div>
      {checks.map((check) => <p key={check}><CheckCircle2 size={15} />{check}</p>)}
    </aside>
  );
}

function screenLabel(screen) {
  return screens.find(([value]) => value === screen)?.[1] || "Home";
}

function variantLabel(variant) {
  return variants.find((item) => item.id === variant)?.label || "Preview";
}
