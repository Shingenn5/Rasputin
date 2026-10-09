import {
  CheckCircle2,
  Cpu,
  MonitorSpeaker,
  Play,
  Search,
  Server,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { displayModelName, displayModelSecondary, labelize, modelMismatchLine } from "../../lib/display.js";
import { contextWindowFor } from "./modelPresentation.js";
import { CompatibilitySummary } from "./ModelStatus.jsx";

export function ActiveModelCard({ model, models, healthy, status, runModelAction, executeAction, setUiState, openWarsat, desktopOnly = false }) {
  const name = displayModelName(model, models);
  const secondary = displayModelSecondary(model, models);
  const mismatch = modelMismatchLine(model);
  const ctx = contextWindowFor(model);

  const handleTest = () => executeAction("TestHealth", model?.key, async () => runModelAction?.("test", model?.key), setUiState);
  const handleDiscover = () => executeAction("Discover", model?.key, async () => runModelAction?.("discover", model?.key), setUiState);
  const handleRepair = () => executeAction("Repair", model?.key, async () => runModelAction?.("repair", model?.key), setUiState);

  return (
    <div className="w2-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <Cpu size={24} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <div>
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--cc-muted)", fontWeight: 600 }}>Active Chat Model</div>
            <h2 style={{ margin: "2px 0 0", fontSize: "1.125rem" }}>{name}</h2>
            {secondary && <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--cc-muted)" }}>{secondary}</p>}
          </div>
        </div>
        <span style={{ fontSize: "0.75rem", padding: "4px 12px", borderRadius: "999px", background: healthy ? "color-mix(in srgb, var(--ras-safe) 15%, var(--cc-surface))" : "color-mix(in srgb, var(--ras-danger) 15%, var(--cc-surface))", color: healthy ? "var(--ras-safe)" : "var(--ras-danger)", fontWeight: 600 }}>
          {healthy ? "Reachable" : labelize(status)}
        </span>
      </div>

      <div style={{ display: "flex", gap: "16px", fontSize: "0.75rem", color: "var(--cc-muted)", flexWrap: "wrap" }}>
        <span>Model: {model?.model || "Not configured"}</span>
        <span>Endpoint: {model?.url || model?.base_url || "Not set"}</span>
        <span>Runtime: {model?.runtime || model?.provider || "local"}</span>
        {ctx > 0 && <span>Context: {ctx.toLocaleString()}</span>}
      </div>

      {mismatch && (
        <div style={{ display: "flex", gap: "6px", alignItems: "center", fontSize: "0.75rem", color: "var(--ras-warn)", padding: "8px 10px", background: "color-mix(in srgb, var(--ras-warn) 8%, var(--cc-surface))", borderRadius: "6px" }}>
          <Wrench size={13} /> {mismatch}
        </div>
      )}


      <CompatibilitySummary model={model} />

      <div style={{ display: "flex", gap: "8px" }}>
        <button className="w2-button" type="button" onClick={handleTest}><CheckCircle2 size={14} /> Test</button>
        <button className="w2-button" type="button" onClick={handleDiscover}><Search size={14} /> Discover</button>
        <button className="w2-button" type="button" onClick={handleRepair}><Wrench size={14} /> Repair</button>
        {!desktopOnly && model?.runtime !== "native-llamacpp" && <button className="w2-button primary" type="button" onClick={openWarsat}><Play size={14} /> Warsat</button>}
      </div>
    </div>
  );
}

export function InfraStatusCard({ warsatHardware, warsatRuntimes, warsat, desktopOnly = false }) {
  const runtimeCount = warsatRuntimes?.count ?? warsatRuntimes?.containers?.length ?? 0;
  return (
    <div className="w2-card">
      <h3 style={{ margin: 0, fontSize: "0.875rem" }}>Infrastructure</h3>
      <div className="w2-health-grid">
        {desktopOnly ? (
          <>
            <div className="w2-health-item"><Server size={16} color="var(--cc-muted)" /> Native runtime: {warsatHardware ? labelize(warsatHardware.status || "unknown") : "Not checked"}</div>
            <div className="w2-health-item"><MonitorSpeaker size={16} color="var(--cc-muted)" /> Running models: {runtimeCount}</div>
            <div className="w2-health-item"><ShieldCheck size={16} color="var(--ras-safe)" /> llama.cpp: Bundled</div>
          </>
        ) : (
          <>
            <div className="w2-health-item"><Server size={16} color="var(--cc-muted)" /> Warsat: {warsatHardware ? labelize(warsatHardware.status || "unknown") : "Not checked"}</div>
            <div className="w2-health-item"><MonitorSpeaker size={16} color="var(--cc-muted)" /> Containers: {runtimeCount}</div>
            <div className="w2-health-item"><ShieldCheck size={16} color="var(--ras-safe)" /> Docker: {warsat?.dockerControlEnabled ? "Enabled" : "Off"}</div>
          </>
        )}
      </div>
    </div>
  );
}

export function RightPanel({ activeTab, activeModel, models, healthy, status, warsatHardware, desktopOnly = false }) {
  const name = displayModelName(activeModel, models);

  if (activeTab === "library") {
    return (
      <div className="w2-section">
        <h3 className="w2-section-title">Quick Start</h3>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>How to add a model</strong>
          <ol style={{ margin: 0, paddingLeft: "18px", fontSize: "0.75rem", color: "var(--cc-muted)" }}>
            {desktopOnly ? (
              <>
                <li>Browse or search for a model</li>
                <li>Choose an exact GGUF variant</li>
                <li>Download a GGUF variant, then select Load model when it finishes</li>
              </>
            ) : (
              <>
                <li>Browse or search for a model</li>
                <li>Click "Deploy via Warsat" on a deployable model</li>
                <li>Or use Settings to connect a running endpoint</li>
              </>
            )}
          </ol>
        </div>
        <div className="w2-card">
          <strong style={{ fontSize: "0.875rem" }}>{desktopOnly ? "Bundled Runtime" : "Supported Runtimes"}</strong>
          <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
            {desktopOnly ? (
              <>
                <span>- llama.cpp native engine (bundled)</span>
                <span>- GGUF model files</span>
                <span>- GPU offload and KV cache controls</span>
                <span>- No external runtime installation</span>
              </>
            ) : (
              <>
                <span>- vLLM CUDA (Hugging Face models)</span>
                <span>- llama.cpp (GGUF files)</span>
                <span>- Ollama (quick experiments)</span>
                <span>- External local endpoints</span>
                <span>- Remote APIs (OpenAI, Anthropic, Gemini)</span>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w2-section">
      <h3 className="w2-section-title">Active Model</h3>
      <div className="w2-card">
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Cpu size={18} color={healthy ? "var(--ras-safe)" : "var(--ras-danger)"} />
          <strong style={{ fontSize: "0.875rem" }}>{name}</strong>
        </div>
        <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <span>Status: {healthy ? "Reachable" : labelize(status)}</span>
          <span>Model: {activeModel?.model || ""}</span>
          <span>Runtime: {activeModel?.runtime || activeModel?.provider || ""}</span>
          <span>Role: {labelize(activeModel?.role || "main")}</span>
        </div>
      </div>

      {warsatHardware?.detectedHardware?.gpus?.length > 0 && (
        <>
          <h3 className="w2-section-title">GPU Hardware</h3>
          <div className="w2-card">
            {warsatHardware.detectedHardware.gpus.map((gpu, i) => {
              const vramMb = gpu.memoryTotalMb || gpu.memory_total_mb;
              return (
                <div key={i} style={{ fontSize: "0.75rem", color: "var(--cc-muted)" }}>
                  <strong style={{ color: "var(--cc-text)" }}>{gpu.name}</strong>
                  <div>{vramMb ? ((vramMb / 1024).toFixed(1) + " GB VRAM") : "Unknown VRAM"}</div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
