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
    summary: "Command-bridge layout with compact navigation, telemetry, and mission-control density.",
  },
  {
    id: "operator-desk",
    label: "Operator Desk",
    summary: "Workbench layout with top navigation, contextual side panels, and calmer task flow.",
  },
  {
    id: "archive-studio",
    label: "Archive Studio",
    summary: "Library layout for long chats, documents, memory, citations, and file review.",
  },
  {
    id: "rasputin-candidate",
    label: "Rasputin Candidate",
    summary: "Composite build: original chat home, Warmind workspaces and Warsat, Archive activity, and a refined Operator-style model manager.",
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
  modes: ["Chat", "Analyze", "Research", "Code", "Write", "Organize"],
};

const icons = {
  home: Home,
  workspaces: Folder,
  activity: Activity,
  models: Cpu,
  warsat: TerminalSquare,
  settings: Settings,
  panels: Layers,
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
      <PreviewController
        screen={screen}
        variant={variant}
        theme={theme}
        viewport={viewport}
        showA11y={showA11y}
        variantInfo={variantInfo}
        setVariant={setVariant}
        setTheme={setTheme}
        setViewport={setViewport}
        setShowA11y={setShowA11y}
        navigate={navigate}
      />

      <section className="preview-stage-shell" style={{ "--preview-width": `${viewportWidth}px` }}>
        <PreviewStage variant={variant} screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />
      </section>

      {showA11y && <AccessibilityChecklist variant={variantInfo} screen={screen} />}
    </main>
  );
}

function PreviewController({
  screen,
  variant,
  theme,
  viewport,
  showA11y,
  variantInfo,
  setVariant,
  setTheme,
  setViewport,
  setShowA11y,
  navigate,
}) {
  return (
    <section className="preview-controller" aria-label="RasputinTest GUI preview controller">
      <div>
        <span className="preview-kicker">RasputinTest</span>
        <h1>GUI Layout Preview Hub</h1>
        <p>{variantInfo.summary}</p>
      </div>
      <label>
        <span>Screen</span>
        <select data-testid="gui-preview-screen-select" value={screen} onChange={(event) => navigate(event.target.value)}>
          {screens.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      <label>
        <span>Layout</span>
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
  );
}

function PreviewStage({ variant, screen, viewport, navigate, variantInfo }) {
  if (variant === "rasputin-candidate") {
    return <RasputinCandidateLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (variant === "operator-desk") {
    return <OperatorDeskLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (variant === "archive-studio") {
    return <ArchiveStudioLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  return <WarmindConsoleLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
}

function RasputinCandidateLayout({ screen, viewport, navigate, variantInfo }) {
  if (screen === "home") {
    return <OriginalHomeLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (screen === "workspaces") {
    return <WarmindConsoleLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} hideTelemetry />;
  }
  if (screen === "activity") {
    return <ArchiveStudioLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (screen === "models") {
    return <CandidateModelsLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (screen === "warsat") {
    return <WarmindConsoleLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  if (screen === "settings") {
    return <OperatorDeskLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
  }
  return <OperatorDeskLayout screen={screen} viewport={viewport} navigate={navigate} variantInfo={variantInfo} />;
}

function WarmindConsoleLayout({ screen, viewport, navigate, variantInfo, hideTelemetry = false }) {
  const showTelemetry = !hideTelemetry && screen !== "workspaces";
  return (
    <div className={`preview-stage preview-layout preview-layout-warmind ${showTelemetry ? "" : "preview-layout-no-telemetry"}`} data-viewport={viewport}>
      <aside className="preview-command-rail" aria-label="Warmind Console navigation">
        <div className="preview-rail-brand">R</div>
        <nav>
          {screens.map(([id, label]) => {
            const Icon = icons[id] || Home;
            return (
              <button key={id} type="button" className={screen === id ? "is-active" : ""} aria-label={label} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}>
                <Icon size={18} />
              </button>
            );
          })}
        </nav>
        <button type="button" aria-label="New chat"><Sparkles size={18} /></button>
      </aside>
      <section className="preview-command-main">
        <header className="preview-command-header">
          <div>
            <span className="preview-kicker">{variantInfo.label}</span>
            <h2 data-testid="preview-screen-title">{screenLabel(screen)}</h2>
          </div>
          <div className="preview-status-row">
            <span><Lock size={14} />Local only</span>
            <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
            {showTelemetry && <span><Gauge size={14} />3 active runs</span>}
          </div>
        </header>
        <div className="preview-command-content">{renderWarmindScreen(screen)}</div>
      </section>
      {showTelemetry && (
        <aside className="preview-telemetry" aria-label="Warmind Console telemetry">
          <TelemetryBlock title="Active Runs" items={fixtures.tasks.map(([status, title, progress]) => `${status}: ${title} / ${progress}`)} />
          <TelemetryBlock title="Approvals" items={fixtures.approvals.map(([summary, action, status]) => `${status}: ${action} / ${summary}`)} />
          <TelemetryBlock title="Runtime" items={["Privacy lock enabled", "Docker control disabled", "Workspace: Project Root"]} />
        </aside>
      )}
    </div>
  );
}

function OriginalHomeLayout({ screen, viewport, navigate, variantInfo }) {
  return (
    <div className="preview-stage preview-stage-original" data-viewport={viewport}>
      <LegacyPreviewSidebar screen={screen} navigate={navigate} variantInfo={variantInfo} />
      <section className="preview-canvas" aria-label={`${variantInfo.label} ${screen} preview`}>
        <header className="preview-header">
          <div>
            <span className="preview-kicker">{variantInfo.label}</span>
            <h2 data-testid="preview-screen-title">{screenLabel(screen)}</h2>
          </div>
          <div className="preview-status-row">
            <span><Lock size={14} />Local only</span>
            <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
          </div>
        </header>
        <div className="preview-home">
          <section className="preview-thread">
            <article className="preview-message user">Can you inspect my workspace and tell me what matters first?</article>
            <article className="preview-message assistant">
              <strong>Workspace read plan</strong>
              <p>I will scan approved folders, use local RAG and Graphify context, then return citations before suggesting file changes.</p>
            </article>
          </section>
          <section className="preview-composer">
            <textarea defaultValue="Message Rasputin" aria-label="Preview message composer" />
            <div className="preview-runbar">
              <button type="button"><Bot size={16} />Mode <strong>Chat</strong><ChevronDown size={14} /></button>
              <button type="button"><Cpu size={16} />Model <strong>llava-1.5</strong><ChevronDown size={14} /></button>
              <button type="button" className="preview-send"><Play size={16} />Send</button>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

function LegacyPreviewSidebar({ screen, navigate, variantInfo }) {
  return (
    <aside className="preview-sidebar">
      <div className="preview-brand">
        <span>R</span>
        <div>
          <strong>Rasputin</strong>
          <small>{variantInfo.label}</small>
        </div>
      </div>
      <button className="preview-new-chat" type="button"><Sparkles size={16} />New Chat</button>
      <nav aria-label="Preview screens">
        {screens.map(([id, label]) => {
          const Icon = icons[id] || Home;
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

function OperatorDeskLayout({ screen, viewport, navigate, variantInfo }) {
  return (
    <div className="preview-stage preview-layout preview-layout-operator" data-viewport={viewport}>
      <header className="preview-operator-topbar">
        <div className="preview-brand-inline">
          <span>R</span>
          <div>
            <strong>Rasputin</strong>
            <small>{variantInfo.label}</small>
          </div>
        </div>
        <nav aria-label="Operator Desk navigation">
          {screens.slice(0, 6).map(([id, label]) => (
            <button key={id} type="button" className={screen === id ? "is-active" : ""} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}>
              {label}
            </button>
          ))}
        </nav>
        <button type="button" className="preview-new-chat"><Sparkles size={16} />New Chat</button>
      </header>
      <aside className="preview-operator-context">
        <ContextPanel screen={screen} />
      </aside>
      <main className="preview-operator-workspace">
        <header className="preview-section-header">
          <div>
            <span className="preview-kicker">{variantInfo.label}</span>
            <h2 data-testid="preview-screen-title">{screenLabel(screen)}</h2>
          </div>
          <div className="preview-status-row">
            <span><Lock size={14} />Local only</span>
            <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
          </div>
        </header>
        {renderOperatorScreen(screen)}
      </main>
      <aside className="preview-operator-inspector">
        <InspectorPanel screen={screen} />
      </aside>
    </div>
  );
}

function ArchiveStudioLayout({ screen, viewport, navigate, variantInfo }) {
  return (
    <div className="preview-stage preview-layout preview-layout-archive" data-viewport={viewport}>
      <aside className="preview-archive-library" aria-label="Archive Studio library">
        <div className="preview-brand-inline">
          <span>R</span>
          <div>
            <strong>Rasputin</strong>
            <small>{variantInfo.label}</small>
          </div>
        </div>
        <label className="preview-library-search">
          <Search size={15} />
          <span>Search chats, files, memory</span>
        </label>
        <nav>
          {screens.map(([id, label]) => (
            <button key={id} type="button" className={screen === id ? "is-active" : ""} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}>
              {label}
            </button>
          ))}
        </nav>
        <section>
          <h3>Folders</h3>
          {["Files", "Writing", "Builds", "Work"].map((folder) => <button key={folder} type="button">{folder}<span>4</span></button>)}
        </section>
      </aside>
      <main className="preview-archive-canvas">
        <header className="preview-section-header">
          <div>
            <span className="preview-kicker">{variantInfo.label}</span>
            <h2 data-testid="preview-screen-title">{screenLabel(screen)}</h2>
          </div>
          <div className="preview-status-row">
            <span><Archive size={14} />Memory ready</span>
            <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
          </div>
        </header>
        {renderArchiveScreen(screen)}
      </main>
      <aside className="preview-archive-inspector">
        <InspectorPanel screen={screen} archive />
      </aside>
    </div>
  );
}

function CandidateModelsLayout({ screen, viewport, navigate, variantInfo }) {
  const sourceGroups = [
    ["Active Local", "vLLM and llama.cpp endpoints Rasputin can reach now", "1 ready"],
    ["Container Plans", "Warsat launch plans waiting for approval", "2 drafts"],
    ["External APIs", "Optional API-key providers, disabled by default", "0 active"],
    ["Knowledge Models", "Embeddings and retrieval-only services", "1 ready"],
  ];
  const roleRows = [
    ["Chat", "llava-hf/llava-1.5-7b-hf", "healthy"],
    ["Code", "fallback: chat model", "needs route"],
    ["Research", "fallback: chat model", "web broker gated"],
    ["Embeddings", "text-embedding-local", "ready"],
  ];

  return (
    <div className="preview-stage preview-layout preview-layout-candidate-models" data-viewport={viewport}>
      <header className="preview-candidate-models-topbar">
        <div className="preview-brand-inline">
          <span>R</span>
          <div>
            <strong>Rasputin</strong>
            <small>{variantInfo.label}</small>
          </div>
        </div>
        <nav aria-label="Rasputin Candidate navigation">
          {screens.slice(0, 6).map(([id, label]) => (
            <button key={id} type="button" className={screen === id ? "is-active" : ""} aria-current={screen === id ? "page" : undefined} onClick={() => navigate(id)}>
              {label}
            </button>
          ))}
        </nav>
        <button type="button" className="preview-new-chat"><Sparkles size={16} />New Chat</button>
      </header>

      <aside className="preview-model-source-rail" aria-label="Model sources">
        <div>
          <span className="preview-kicker">Sources</span>
          <h3>Model Library</h3>
        </div>
        {sourceGroups.map(([title, detail, count], index) => (
          <button key={title} type="button" className={index === 0 ? "is-active" : ""}>
            <strong>{title}</strong>
            <span>{detail}</span>
            <small>{count}</small>
          </button>
        ))}
      </aside>

      <main className="preview-candidate-models-main">
        <header className="preview-section-header">
          <div>
            <span className="preview-kicker">{variantInfo.label}</span>
            <h2 data-testid="preview-screen-title">{screenLabel(screen)}</h2>
          </div>
          <div className="preview-status-row">
            <span><Lock size={14} />Local first</span>
            <span><Cpu size={14} />llava-hf/llava-1.5-7b-hf</span>
          </div>
        </header>

        <section className="preview-model-control-board">
          <article className="preview-active-model-board">
            <div className="preview-model-board-head">
              <div>
                <span className="preview-kicker">Active Chat Model</span>
                <h3>llava-hf/llava-1.5-7b-hf</h3>
                <p>Shown exactly as the runtime reports it. Friendly labels stay secondary.</p>
              </div>
              <span className="preview-model-health is-healthy"><CheckCircle2 size={15} />Healthy</span>
            </div>
            <div className="preview-model-health-strip">
              <span>Endpoint: 127.0.0.1:8000</span>
              <span>Latency: 214 ms</span>
              <span>Context: 1024 tokens</span>
              <span>Privacy: brokered tools only</span>
            </div>
            <div className="preview-model-action-row">
              <button type="button"><Search size={16} />Discover models</button>
              <button type="button"><Gauge size={16} />Test health</button>
              <button type="button" className="preview-send"><Play size={16} />Use for chat</button>
            </div>
          </article>

          <section className="preview-model-role-panel">
            <div>
              <span className="preview-kicker">Routing</span>
              <h3>Mode model map</h3>
            </div>
            {roleRows.map(([mode, model, state]) => (
              <article key={mode}>
                <strong>{mode}</strong>
                <span>{model}</span>
                <small>{state}</small>
              </article>
            ))}
          </section>
        </section>
      </main>

      <aside className="preview-model-ops-panel" aria-label="Model operations">
        <section>
          <span className="preview-kicker">Deploy</span>
          <h3>Warsat hook</h3>
          <p>Generate a container plan from a selected model, then approve deployment from Warsat.</p>
          <button type="button"><TerminalSquare size={16} />Create launch plan</button>
        </section>
        <section>
          <span className="preview-kicker">APIs</span>
          <h3>Provider keys</h3>
          <p>External providers stay optional and store secrets through env or secret files only.</p>
          <button type="button"><ShieldCheck size={16} />Configure secrets</button>
        </section>
        <section className="preview-advanced-summary">
          <span className="preview-kicker">Advanced</span>
          <h3>Registry details</h3>
          <ChipList items={["Raw keys hidden", "Dry-run hidden", "Embeddings separated", "Repair available"]} />
        </section>
      </aside>
    </div>
  );
}

function renderWarmindScreen(screen) {
  const map = {
    home: <WarmindHome />,
    workspaces: <WarmindWorkspaces />,
    activity: <WarmindActivity />,
    models: <WarmindModels />,
    warsat: <WarmindWarsat />,
    settings: <WarmindSettings />,
    panels: <WarmindPanels />,
  };
  return map[screen] || map.home;
}

function renderOperatorScreen(screen) {
  const map = {
    home: <OperatorHome />,
    workspaces: <OperatorWorkspaces />,
    activity: <OperatorActivity />,
    models: <OperatorModels />,
    warsat: <OperatorWarsat />,
    settings: <OperatorSettings />,
    panels: <OperatorPanels />,
  };
  return map[screen] || map.home;
}

function renderArchiveScreen(screen) {
  const map = {
    home: <ArchiveHome />,
    workspaces: <ArchiveWorkspaces />,
    activity: <ArchiveActivity />,
    models: <ArchiveModels />,
    warsat: <ArchiveWarsat />,
    settings: <ArchiveSettings />,
    panels: <ArchivePanels />,
  };
  return map[screen] || map.home;
}

function WarmindHome() {
  return (
    <div className="preview-warmind-home">
      <section className="preview-console-card preview-command-terminal">
        <h3>Command Thread</h3>
        <article className="preview-message user">Inspect the workspace and tell me what matters first.</article>
        <article className="preview-message assistant">
          <strong>Local scan plan</strong>
          <p>Read approved folders, retrieve local memory, inspect citations, then wait before any mutation.</p>
        </article>
      </section>
      <section className="preview-console-card">
        <h3>Mission Queue</h3>
        <TaskStack compact />
      </section>
      <section className="preview-console-card preview-command-input">
        <textarea defaultValue="Message Rasputin" aria-label="Warmind command composer" />
        <div className="preview-runbar">
          <button type="button"><Bot size={16} />Mode <strong>Chat</strong></button>
          <button type="button"><Cpu size={16} />Model <strong>llava-1.5</strong></button>
          <button type="button" className="preview-send"><Play size={16} />Execute</button>
        </div>
      </section>
      <section className="preview-console-card">
        <h3>Context Feed</h3>
        <ChipList items={["Project Root", "RAG: 42 chunks", "Graph: 18 edges", "Memory: 6 hits"]} />
      </section>
    </div>
  );
}

function OperatorHome() {
  return (
    <div className="preview-operator-home">
      <section className="preview-chat-column">
        <article className="preview-message user">Inspect the workspace and tell me what matters first.</article>
        <article className="preview-message assistant">
          <strong>Workspace read plan</strong>
          <p>I will scan approved folders, use local RAG and Graphify context, then return citations before suggesting file changes.</p>
        </article>
      </section>
      <section className="preview-composer preview-operator-composer">
        <textarea defaultValue="Message Rasputin" aria-label="Operator message composer" />
        <div className="preview-runbar">
          <button type="button" className="preview-run-config"><Gauge size={16} />Run Config <span>Chat / local model / no helpers</span></button>
          <button type="button" className="preview-send"><Play size={16} />Send</button>
        </div>
      </section>
    </div>
  );
}

function ArchiveHome() {
  return (
    <div className="preview-archive-home">
      <section className="preview-reading-thread">
        <article className="preview-message user">Inspect the workspace and tell me what matters first.</article>
        <article className="preview-message assistant">
          <strong>Workspace read plan</strong>
          <p>I will scan approved folders, use local RAG and Graphify context, then return citations before suggesting file changes.</p>
        </article>
      </section>
      <section className="preview-composer preview-archive-composer">
        <textarea defaultValue="Message Rasputin" aria-label="Archive Studio message composer" />
        <div className="preview-runbar">
          <button type="button"><Bot size={16} />Mode <strong>Chat</strong><ChevronDown size={14} /></button>
          <button type="button"><Cpu size={16} />Model <strong>llava-1.5</strong><ChevronDown size={14} /></button>
          <button type="button" className="preview-send"><Play size={16} />Send</button>
        </div>
      </section>
    </div>
  );
}

function WarmindWorkspaces() {
  return (
    <div className="preview-layout-grid preview-warmind-files">
      <section className="preview-console-card">
        <h3>Mounted Roots</h3>
        <RootButtons />
      </section>
      <section className="preview-console-card preview-file-matrix">
        <h3>/workspace/docs</h3>
        <FileRows />
      </section>
      <section className="preview-console-card">
        <h3>Index Telemetry</h3>
        <ChipList items={["backend indexed", "docs indexed", "4 previewable files", "0 write actions"]} />
      </section>
      <section className="preview-console-card">
        <h3>Selected Item</h3>
        <p>architecture.md can be previewed and linked into memory without exposing contents outside the container.</p>
      </section>
    </div>
  );
}

function OperatorWorkspaces() {
  return (
    <div className="preview-file-explorer">
      <section className="preview-pane roots"><h3>Approved folders</h3><RootButtons /></section>
      <section className="preview-pane files"><div className="preview-search"><Search size={15} /><span>/workspace/docs</span></div><FileRows /></section>
      <section className="preview-pane preview"><h3>Preview</h3><p>Read-only text preview, index state, citations, and graph links live here.</p></section>
    </div>
  );
}

function ArchiveWorkspaces() {
  return (
    <div className="preview-archive-workspaces">
      <section className="preview-pane">
        <h3>Library Shelves</h3>
        <RootButtons />
      </section>
      <section className="preview-pane preview-document">
        <h3>architecture.md</h3>
        <p># Rasputin architecture</p>
        <p>Local files remain inside approved roots. Indexing produces local citations and graph evidence.</p>
      </section>
      <section className="preview-pane">
        <h3>Memory Links</h3>
        <ChipList items={["Project note", "PDF source", "Graph edge", "Citation range"]} />
      </section>
    </div>
  );
}

function WarmindActivity() {
  return <div className="preview-lane-board">{["Running", "Paused", "Done"].map((lane) => <section key={lane} className="preview-console-card"><h3>{lane}</h3><TaskStack status={lane} compact /></section>)}</div>;
}

function OperatorActivity() {
  return <div className="preview-activity-split"><section><TaskStack /></section><section className="preview-pane"><h3>Run Details</h3><p>Trace, logs, approvals, artifacts, and sub-agents stay one click away.</p></section></div>;
}

function ArchiveActivity() {
  return <div className="preview-journal-list">{fixtures.tasks.map(([status, title, progress, detail]) => <article key={title}><strong>{title}</strong><span>{status} / {progress}</span><p>{detail}</p></article>)}</div>;
}

function WarmindModels() {
  return <div className="preview-model-matrix"><ModelRows /><section className="preview-console-card"><h3>Role Routing</h3><ChipList items={["main -> llava", "coder -> qwen", "embeddings -> local only"]} /></section></div>;
}

function OperatorModels() {
  return <div className="preview-model-dashboard"><section className="preview-pane active-model"><h3>Active Model</h3><strong>llava-hf/llava-1.5-7b-hf</strong><button type="button">Test health</button></section><ModelRows /></div>;
}

function ArchiveModels() {
  return <div className="preview-card-catalog">{fixtures.models.map(([name, status, purpose]) => <article key={name}><Cpu size={20} /><strong>{name}</strong><span>{purpose}</span><small>{status}</small></article>)}</div>;
}

function WarmindWarsat() {
  return <div className="preview-launch-grid"><section className="preview-console-card"><h3>Launch Sequence</h3><ChipList items={["Recipe selected", "VRAM budget set", "Compose file generated", "Approval pending"]} /></section><section className="preview-console-card"><h3>Generated Command</h3><p>Container binds to 127.0.0.1, uses no-new-privileges, and mounts models read-only.</p><button type="button">Request deployment approval</button></section></div>;
}

function OperatorWarsat() {
  return <div className="preview-wizard"><nav>{["Runtime", "Model", "Resources", "Safety", "Deploy"].map((item) => <button key={item} type="button">{item}</button>)}</nav><section className="preview-pane"><h3>Runtime Recipe</h3><ChipList items={["vLLM CUDA", "Qwen/Qwen2.5-Coder-7B", "Port 8020", "Profile: Large"]} /><button type="button">Preview compose file</button></section></div>;
}

function ArchiveWarsat() {
  return <div className="preview-recipe-library"><section className="preview-pane"><h3>Recipe Library</h3><RootButtons items={["Local chat model", "Coding model", "Embedding service"]} /></section><section className="preview-pane preview-document"><h3>Generated Compose Notes</h3><p>Review the generated compose plan as a document before approving deployment.</p></section></div>;
}

function WarmindSettings() {
  return <div className="preview-setting-matrix">{["Safety", "Models", "Knowledge", "Output"].map((item) => <section key={item} className="preview-console-card"><h3>{item}</h3><ChipList items={["Pending changes: 0", "Requires save", "Audit enabled"]} /></section>)}</div>;
}

function OperatorSettings() {
  return <div className="preview-settings-workbench"><nav>{["General", "Workspaces", "Safety", "Knowledge", "Output", "Appearance", "Admin"].map((item) => <button key={item} type="button">{item}</button>)}</nav><section className="preview-pane"><h3>Safety</h3><p>Settings use staged changes and explicit Save / Revert controls.</p><button type="button">Save changes</button></section></div>;
}

function ArchiveSettings() {
  return <div className="preview-preference-notebook"><section className="preview-pane"><h3>Preferences Notebook</h3><p>Settings are organized as readable sections with change history and plain-language descriptions.</p></section><section className="preview-pane"><h3>Appearance</h3><div className="preview-theme-grid">{themeOptions.slice(0, 6).map(([value, label]) => <span key={value}>{label}</span>)}</div></section></div>;
}

function WarmindPanels() {
  return <div className="preview-overlay-stack"><PanelCard title="Model Panel" /><PanelCard title="Mode Panel" /><PanelCard title="Approval Stack" /></div>;
}

function OperatorPanels() {
  return <div className="preview-panel-layout"><section className="preview-pane"><h3>Right Side Sheet</h3><p>Model selection, mode routing, and task details open as focused sheets.</p></section><section className="preview-pane"><h3>Bottom Drawer</h3><p>Logs and artifacts can expand without pushing the main chat away.</p></section></div>;
}

function ArchivePanels() {
  return <div className="preview-citation-panels"><section className="preview-pane"><h3>Citations</h3><ChipList items={["architecture.md:12", "README.md:44", "notes.pdf:3"]} /></section><section className="preview-pane"><h3>Memory Review</h3><p>Memory suggestions appear as reviewable notes, not raw system logs.</p></section></div>;
}

function ContextPanel({ screen }) {
  if (screen === "workspaces") {
    return <><h3>Workspace Context</h3><RootButtons /></>;
  }
  if (screen === "models" || screen === "warsat") {
    return <><h3>Runtime Context</h3><ChipList items={["Main model healthy", "Docker disabled", "1 launch plan"]} /></>;
  }
  return <><h3>Recent Chats</h3>{fixtures.sessions.map(([title, meta]) => <article key={title}><strong>{title}</strong><span>{meta}</span></article>)}</>;
}

function InspectorPanel({ screen, archive = false }) {
  const title = archive ? "Evidence Inspector" : "Details";
  return (
    <>
      <h3>{title}</h3>
      <p>{screenLabel(screen)} details stay visible without crowding the primary work area.</p>
      <ChipList items={archive ? ["Citations", "Memory", "Graph links"] : ["Task status", "Approvals", "Exports"]} />
    </>
  );
}

function TelemetryBlock({ title, items }) {
  return <section><h3>{title}</h3>{items.map((item) => <p key={item}>{item}</p>)}</section>;
}

function RootButtons({ items = ["Project Root", "Research PDFs", "Writing Output"] }) {
  return (
    <div className="preview-root-button-list">
      {items.map((root) => (
        <button key={root} type="button">
          <span>{root}</span>
          <small>mounted</small>
        </button>
      ))}
    </div>
  );
}

function FileRows() {
  return fixtures.files.map(([name, kind, detail, state]) => (
    <article key={name}>
      {kind === "folder" ? <Folder size={18} /> : <FileText size={18} />}
      <strong>{name}</strong>
      <span>{detail}</span>
      <small>{state}</small>
    </article>
  ));
}

function TaskStack({ status, compact = false }) {
  return fixtures.tasks
    .filter(([taskStatus]) => !status || taskStatus === status)
    .map(([taskStatus, title, progress, detail]) => (
      <article key={title} className={compact ? "is-compact" : ""}>
        <span className={`preview-state state-${taskStatus.toLowerCase()}`}>{taskStatus}</span>
        <strong>{title}</strong>
        <small>{progress}</small>
        {!compact && <p>{detail}</p>}
      </article>
    ));
}

function ModelRows() {
  return fixtures.models.map(([name, status, purpose]) => (
    <article key={name}>
      <Cpu size={20} />
      <div><strong>{name}</strong><span>{purpose}</span></div>
      <small>{status}</small>
    </article>
  ));
}

function ChipList({ items }) {
  return <div className="preview-chip-list">{items.map((item) => <span key={item}>{item}</span>)}</div>;
}

function PanelCard({ title }) {
  return <section className="preview-pane"><h3>{title}</h3><p>Previewed as its own spatial pattern instead of another identical page card.</p></section>;
}

function currentScreen() {
  const value = window.location.pathname.split("/").filter(Boolean)[1] || "home";
  return screens.some(([screen]) => screen === value) ? value : "home";
}

function AccessibilityChecklist({ variant, screen }) {
  const checks = useMemo(() => [
    "Each option changes layout structure, not only color or surface styling.",
    "Keyboard path reaches navigation, preview controller, cards, and panels.",
    "Focus rings use the active theme focus token.",
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
