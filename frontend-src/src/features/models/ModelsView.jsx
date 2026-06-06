import React from "react";
import {
  CheckCircle2,
  Cpu,
  HardDrive,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Wrench,
} from "lucide-react";
import {
  discoveredModelIds,
  displayModelName,
  displayModelSecondary,
  isModelHealthy,
  labelize,
  modelMismatchLine,
  runtimeStatus,
} from "../../lib/display.js";

const deploymentSteps = [
  ["Select", "Choose a managed runtime or connect an existing localhost endpoint."],
  ["Profile", "Pick a VRAM target, quantization preference, context length, and exposed local port."],
  ["Generate", "Create a Docker Compose launch plan and Dockerfile only when the selected runtime needs one."],
  ["Review", "Show mounts, environment variables, ports, and security flags before anything starts."],
  ["Deploy", "Run only after Docker control is enabled and the plan is explicitly approved."],
];

const runtimeOptions = [
  ["vLLM CUDA", "Best for a larger primary chat or coding model with enough VRAM.", "Hugging Face model id"],
  ["llama.cpp GGUF", "Best for smaller helper models, quantized local files, and low VRAM.", "Mounted .gguf file"],
  ["Ollama", "Good for quick local model testing through Ollama's OpenAI-compatible API.", "Ollama model name"],
  ["External local endpoint", "Use LM Studio, Ollama, text-generation-webui, or anything exposing a local /v1 API.", "localhost /v1 endpoint"],
];

const hardwareProfiles = [
  ["Small", "4-8 GB VRAM", "helper, summarize, organize"],
  ["Medium", "10-16 GB VRAM", "chat, analyze, code helper"],
  ["Large", "20+ GB VRAM", "main model, coding, long context"],
  ["Custom", "manual limits", "advanced tuning"],
];

export function ModelsView({
  view,
  models,
  selectedModelObject,
  testingMode,
  setTestingMode,
  runModelAction,
  loadModels,
  scanGguf,
  registerLocalModel,
  openWarsat,
}) {
  const activeModel = selectedModelObject || models?.[0] || null;
  const activeName = displayModelName(activeModel, models);
  const secondary = displayModelSecondary(activeModel, models);
  const healthy = isModelHealthy(activeModel);
  const status = runtimeStatus(activeModel);
  const mismatch = modelMismatchLine(activeModel);
  const discovered = discoveredModelIds(activeModel);

  return (
    <section className={`app-view models-view ${view === "models" ? "active" : ""}`} id="modelsView" data-app-view="models">
      <header className="page-header models-header">
        <div>
          <h1>Models</h1>
          <p>Inspect the active local model and plan model containers without leaving Rasputin.</p>
        </div>
        <div className="models-header-actions">
          <button className="ras-button ghost" type="button" onClick={loadModels}>
            <RefreshCw size={17} aria-hidden="true" />
            Refresh registry
          </button>
          <button className="ras-button primary" type="button" onClick={() => runModelAction("discover")}>
            <Search size={17} aria-hidden="true" />
            Discover vLLM
          </button>
        </div>
      </header>

      <div className="models-content">
        <section className="models-grid">
          <article className="model-command-card" data-testid="active-model-card" id="models-active-card">
            <div className="model-command-top">
              <span className="model-glyph" aria-hidden="true"><Cpu size={22} /></span>
              <div>
                <span className="eyebrow">Active Chat Model</span>
                <h2>{activeName}</h2>
                {secondary && <p>{secondary}</p>}
              </div>
              <span className={`model-health-pill ${healthy ? "is-healthy" : "is-unhealthy"}`}>
                {healthy ? "Reachable" : labelize(status)}
              </span>
            </div>

            <div className="model-truth-grid">
              <div>
                <span>Configured model id</span>
                <strong>{activeModel?.model || "No model configured"}</strong>
              </div>
              <div>
                <span>Endpoint</span>
                <strong>{activeModel?.url || activeModel?.baseUrl || "Local endpoint not set"}</strong>
              </div>
              <div>
                <span>Runtime</span>
                <strong>{activeModel?.runtime || activeModel?.provider || "local"}</strong>
              </div>
              <div>
                <span>Last health</span>
                <strong>{runtimeStatus(activeModel)}</strong>
              </div>
            </div>

            {mismatch && (
              <div className="model-warning" role="status">
                <Wrench size={17} aria-hidden="true" />
                <span>{mismatch}</span>
              </div>
            )}

            {!mismatch && activeModel?.lastError && (
              <div className="model-warning" role="status">
                <Wrench size={17} aria-hidden="true" />
                <span>{activeModel.lastError}</span>
              </div>
            )}

            {!!discovered.length && (
              <div className="model-discovery-list">
                <span>Discovered</span>
                {discovered.slice(0, 4).map((id) => <code key={id}>{id}</code>)}
              </div>
            )}

            <div className="model-action-row">
              <button className="ras-button" type="button" onClick={() => runModelAction("test")}>
                <CheckCircle2 size={17} aria-hidden="true" />
                Test health
              </button>
              <button className="ras-button" type="button" onClick={() => runModelAction("repair")}>
                <Wrench size={17} aria-hidden="true" />
                Use discovered model
              </button>
              <button className="ras-button" type="button" data-testid="gguf-scan" onClick={scanGguf}>
                <HardDrive size={17} aria-hidden="true" />
                Scan GGUF library
              </button>
            </div>
          </article>

          <aside className="model-health-card">
            <span className="eyebrow">Safety State</span>
            <h2>Local runtime control stays gated.</h2>
            <p>
              Rasputin prepares and deploys Docker model runtimes through Warsat. Starting containers stays behind
              Docker-control permission and an explicit approval step.
            </p>
            <div className="safety-stack">
              <span><ShieldCheck size={16} aria-hidden="true" /> Ports bind to 127.0.0.1</span>
              <span><ShieldCheck size={16} aria-hidden="true" /> Model mounts default read-only</span>
              <span><ShieldCheck size={16} aria-hidden="true" /> Compose plans are previewed first</span>
            </div>
          </aside>
        </section>

        <section className="model-builder-panel" aria-labelledby="modelBuilderTitle">
          <div className="section-row">
            <div>
              <span className="eyebrow">Warsat Deployment Plan</span>
              <h2 id="modelBuilderTitle">Generate and deploy model containers with Warsat</h2>
              <p>
                Use Warsat to select a runtime, choose hardware limits, review the Docker command, request approval,
                and deploy a local-only model endpoint.
              </p>
            </div>
            <button className="ras-button primary" type="button" onClick={openWarsat}>
              <Play size={17} aria-hidden="true" />
              Open Warsat
            </button>
          </div>

          <div className="deployment-layout">
            <div className="deployment-column">
              <h3>Runtime choices</h3>
              <div className="runtime-option-grid">
                {runtimeOptions.map(([name, text, input]) => (
                  <article className="runtime-option" key={name}>
                    <strong>{name}</strong>
                    <p>{text}</p>
                    <small>{input}</small>
                  </article>
                ))}
              </div>
            </div>

            <div className="deployment-column">
              <h3>Hardware profiles</h3>
              <div className="hardware-profile-grid">
                {hardwareProfiles.map(([name, vram, usage]) => (
                  <article className="hardware-profile" key={name}>
                    <span>{name}</span>
                    <strong>{vram}</strong>
                    <small>{usage}</small>
                  </article>
                ))}
              </div>
            </div>
          </div>

          <ol className="deployment-steps">
            {deploymentSteps.map(([title, text]) => (
              <li key={title}>
                <span>{title}</span>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="model-builder-panel local-model-panel" aria-labelledby="localModelTitle">
          <div className="section-row">
            <div>
              <span className="eyebrow">Local Endpoint</span>
              <h2 id="localModelTitle">Connect any OpenAI-compatible localhost model</h2>
              <p>
                Use this for models Rasputin does not launch itself: LM Studio, Ollama, text-generation-webui,
                a custom server, or another local wrapper. The endpoint must stay local while privacy lock is on.
              </p>
            </div>
          </div>
          <form className="local-model-form" onSubmit={registerLocalModel} data-testid="local-model-form">
            <label>
              <span>Display name</span>
              <input name="name" placeholder="My Local Coder" />
            </label>
            <label>
              <span>Model id</span>
              <input name="model" placeholder="qwen2.5-coder:7b" required />
            </label>
            <label>
              <span>Base endpoint</span>
              <input name="baseUrl" placeholder="http://127.0.0.1:1234/v1" required />
            </label>
            <label>
              <span>Purpose</span>
              <select name="role" defaultValue="helper">
                <option value="main">Main</option>
                <option value="planner">Planner</option>
                <option value="executor">Executor</option>
                <option value="coder">Coder</option>
                <option value="researcher">Researcher</option>
                <option value="summarizer">Summarizer</option>
                <option value="memory">Memory</option>
                <option value="helper">Helper</option>
              </select>
            </label>
            <label>
              <span>Provider</span>
              <select name="provider" defaultValue="openai-compatible">
                <option value="openai-compatible">OpenAI-compatible</option>
                <option value="ollama">Ollama</option>
                <option value="lm-studio">LM Studio</option>
                <option value="text-generation-webui">text-generation-webui</option>
                <option value="custom-local">Custom local</option>
              </select>
            </label>
            <label>
              <span>Context window</span>
              <input name="contextWindow" type="number" min="512" placeholder="4096" />
            </label>
            <label>
              <span>Max output tokens</span>
              <input name="maxTokens" type="number" min="1" placeholder="512" />
            </label>
            <label className="local-model-notes">
              <span>Notes</span>
              <input name="notes" placeholder="Started outside Rasputin" />
            </label>
            <div className="local-model-actions">
              <button className="ras-button primary" type="submit">
                <CheckCircle2 size={17} aria-hidden="true" />
                Connect local model
              </button>
              <small>After connecting, use Test health to verify `/models` and chat completion support.</small>
            </div>
          </form>
        </section>

        <details className="advanced-model-registry" data-testid="advanced-model-registry">
          <summary>
            <SlidersHorizontal size={17} aria-hidden="true" />
            Advanced model registry
          </summary>
          <div className="advanced-model-body">
            <label className="testing-mode-control">
              <input
                data-testid="testing-mode-toggle"
                type="checkbox"
                checked={testingMode}
                onChange={(event) => setTestingMode(event.target.checked)}
              />
              <span>
                <strong>Testing Mode</strong>
                <small>Show dry-run in the chat model picker.</small>
              </span>
            </label>
            <div id="modelRegistry" className="model-list registry-grid">
              {(models || []).map((model) => (
                <article className="model-row registry-row" key={model.key}>
                  <strong>{displayModelName(model, models)}</strong>
                  <dl className="model-meta-grid mb-0">
                    <dt>Purpose</dt><dd>{labelize(model.role || "chat")}</dd>
                    <dt>Runtime</dt><dd>{model.runtime || model.provider || "local"}</dd>
                    <dt>Health</dt><dd>{runtimeStatus(model)}</dd>
                    <dt>Key</dt><dd>{model.key}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>
        </details>
      </div>
    </section>
  );
}
