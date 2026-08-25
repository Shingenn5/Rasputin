import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  RadioTower,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { Badge } from "@/components/ui/badge.jsx";
import { Button as UIButton } from "@/components/ui/button.jsx";

function Toggle({ checked, disabled, label, description, onChange, testId }) {
  return (
    <div className="serving-toggle-row">
      <div>
        <strong>{label}</strong>
        <small>{description}</small>
      </div>
      <button
        type="button"
        className="serving-switch"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        data-testid={testId}
        data-state={checked ? "on" : "off"}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span aria-hidden="true" />
      </button>
    </div>
  );
}

function formatMs(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number)} ms` : "—";
}

function formatTokens(input, output) {
  const inputCount = Number(input);
  const outputCount = Number(output);
  if (!Number.isFinite(inputCount) && !Number.isFinite(outputCount)) return "—";
  return `${Number.isFinite(inputCount) ? inputCount : 0} in / ${Number.isFinite(outputCount) ? outputCount : 0} out`;
}

function statusValue(status, ...keys) {
  for (const key of keys) {
    if (status?.[key] !== undefined && status?.[key] !== null) return status[key];
  }
  return undefined;
}

function normalizedState(value) {
  return String(value || "").trim().toLowerCase().replaceAll("_", "-").replaceAll(" ", "-");
}

function modelAvailability(status) {
  const servableList = Array.isArray(status?.servableModels) ? status.servableModels : null;
  const configuredList = Array.isArray(status?.configuredModels) ? status.configuredModels : null;
  const countValue = statusValue(status, "servableModelCount", "servableModelsCount", "servableCount", "availableModelCount", "modelCount") ?? (servableList ? servableList.length : undefined);
  const configuredValue = statusValue(status, "configuredModelCount", "configuredModelsCount", "configuredCount", "registeredModelCount") ?? (configuredList ? configuredList.length : undefined);
  const count = countValue === undefined || countValue === null || countValue === "" ? null : Number(countValue);
  const configured = configuredValue === undefined || configuredValue === null || configuredValue === "" ? null : Number(configuredValue);
  const readyValue = statusValue(status, "hasServableModel", "modelReady", "modelAvailable", "servableModelReady");
  const ready = readyValue === undefined ? (count === null ? null : count > 0) : Boolean(readyValue);
  return { count: Number.isFinite(count) ? count : null, configured: Number.isFinite(configured) ? configured : null, ready };
}

function servingReadiness(status) {
  const explicit = normalizedState(statusValue(status, "readiness", "servingReadiness", "gatewayReadiness", "modelReadiness", "state"));
  const { ready } = modelAvailability(status);
  if (!status?.apiKeyConfigured) return { state: "key-required", label: "API key required", variant: "down" };
  if (!status?.enabled) return { state: "disabled", label: "Gateway off", variant: "muted" };
  if (explicit && ["blocked", "error", "failed", "unreachable", "no-model", "model-unavailable", "degraded"].includes(explicit)) {
    return { state: explicit, label: String(status.readinessLabel || status.readiness || "Model not ready"), variant: "down" };
  }
  if (ready === false) return { state: "no-model", label: "No servable model", variant: "down" };
  if (explicit === "ready" || ready === true) return { state: "ready", label: "Ready", variant: "up" };
  return { state: "unknown", label: "Readiness not reported", variant: "muted" };
}

function actionLabel(action) {
  if (typeof action === "string") return action;
  return action?.label || action?.message || action?.title || action?.action || "Review serving readiness.";
}

const protocolGuidance = {
  openai: {
    text: "Authorization: Bearer <key>. Use /v1/models or /v1/chat/completions.",
    headers: "Authorization: Bearer <your-rasputin-key>",
  },
  anthropic: {
    text: "x-api-key is required, plus anthropic-version: 2023-06-01 for /v1/messages.",
    headers: "x-api-key: <your-rasputin-key>\nanthropic-version: 2023-06-01",
  },
  rasputin: {
    text: "Authorization: Bearer <key>. Native responses and content-free metrics are available.",
    headers: "Authorization: Bearer <your-rasputin-key>",
  },
  mcp: {
    text: "Authorization: Bearer <key>. Limited MCP JSON-RPC HTTP: initialize, tools/list, and guarded tools/call.",
    headers: "Authorization: Bearer <your-rasputin-key>\nContent-Type: application/json",
  },
};

export function ModelServingPanel({ onOpenModels }) {
  const [status, setStatus] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState("");
  const [liveMessage, setLiveMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    setBusy("refresh");
    setError("");
    try {
      setStatus(await api("/api/model-serving"));
      setLiveMessage("Serving status refreshed.");
    } catch (refreshError) {
      setError(refreshError?.message || "Unable to load model-serving status.");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function updateConfig(next) {
    setBusy("config");
    setError("");
    try {
      setStatus(await postJson("/api/model-serving/config", next));
      setLiveMessage("Serving configuration updated.");
    } catch (updateError) {
      setError(updateError?.message || "Unable to update model serving.");
    } finally {
      setBusy("");
    }
  }

  async function rotateKey() {
    setBusy("key");
    setError("");
    try {
      const next = await postJson("/api/model-serving/key/rotate", {});
      setApiKey(next.apiKey || "");
      setStatus(next);
      setLiveMessage("A new serving key was generated. Copy it now; it will not be shown again.");
    } catch (rotateError) {
      setError(rotateError?.message || "Unable to generate a serving key.");
    } finally {
      setBusy("");
    }
  }

  async function copyText(value, id, label = "Value") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(id);
      setLiveMessage(`${label} copied.`);
      window.setTimeout(() => setCopied(""), 1800);
    } catch {
      setError("Copy failed. Select the value and copy it manually.");
      setLiveMessage("Copy failed. Select the value and copy it manually.");
    }
  }

  const protocols = status?.protocols || [];
  const recent = status?.recentRequests || [];
  const isBusy = Boolean(busy);
  const readiness = servingReadiness(status);
  const availability = modelAvailability(status);
  const backendActions = Array.isArray(status?.nextActions || status?.next_actions)
    ? (status.nextActions || status.next_actions).map(actionLabel).filter(Boolean)
    : [];
  const fallbackAction = readiness.state === "key-required"
    ? "Generate an API key before sharing an endpoint."
    : readiness.state === "no-model"
      ? "Load or enable a reachable model before sending requests."
      : readiness.state === "disabled"
        ? "Enable the gateway only after confirming a servable model is ready."
        : readiness.state === "unknown"
          ? "Refresh status and verify a reachable model before sending requests."
          : readiness.state === "ready"
            ? "Authenticated requests are ready for a configured model."
            : "Serving is not ready. Review the reported readiness state before sending requests.";

  return (
    <div className="model-serving-panel" data-testid="model-serving-panel">
      <div className="sr-only" aria-live="polite" data-testid="serving-live-status">{liveMessage || error}</div>
      <header className="serving-panel-header">
        <div>
          <span className="serving-eyebrow"><RadioTower size={13} /> Model-serving gateway</span>
          <h2>Expose configured models from Rasputin</h2>
          <p>OpenAI-compatible, Anthropic-compatible, Rasputin, and limited MCP JSON-RPC HTTP interfaces share one authenticated gateway.</p>
        </div>
        <div className="serving-header-actions">
          <Badge variant={status ? readiness.variant : "muted"}>{status ? readiness.label : "Loading"}</Badge>
          <UIButton type="button" variant="outline" size="sm" onClick={refresh} disabled={isBusy} aria-label="Refresh serving status">
            <RefreshCw size={14} className={busy === "refresh" ? "spin" : ""} /> Refresh
          </UIButton>
        </div>
      </header>

      {error && (
        <div className="serving-alert" role="alert">
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {!status && !error ? (
        <div className="serving-loading" role="status">Loading serving configuration…</div>
      ) : status && (
        <>
          <section className="serving-readiness" data-testid="serving-readiness" aria-label="Serving readiness">
            <div>
              <strong>{availability.count === null
                ? (availability.configured === null ? "Model availability" : `${availability.configured} configured model${availability.configured === 1 ? "" : "s"}`)
                : `${availability.count} servable model${availability.count === 1 ? "" : "s"}${availability.configured === null ? "" : ` · ${availability.configured} configured`}`}</strong>
              <small>{backendActions[0] || fallbackAction}</small>
            </div>
            {(readiness.state === "no-model" || readiness.state === "unknown") && onOpenModels && (
              <UIButton type="button" variant="outline" size="sm" onClick={onOpenModels}>Open Running Models</UIButton>
            )}
          </section>
          {backendActions.length > 1 && (
            <ul className="serving-next-actions" aria-label="Next actions">
              {backendActions.slice(1).map((action, index) => <li key={`${action}-${index}`}>{action}</li>)}
            </ul>
          )}
          <section className="serving-control-grid" aria-label="Serving controls">
            <div className="serving-control-card">
              <Toggle
                checked={Boolean(status.enabled)}
                disabled={isBusy || !status.apiKeyConfigured}
                label="Model-serving gateway"
                description={status.apiKeyConfigured ? "Accept authenticated requests on the Rasputin server." : "Generate an API key before enabling requests."}
                testId="serving-enable-toggle"
                onChange={(enabled) => updateConfig({ enabled })}
              />
              <div className="serving-key-actions">
                <div>
                  <KeyRound size={15} />
                  <span>
                    <strong>{status.apiKeyConfigured ? "API key configured" : "No API key yet"}</strong>
                    <small>Bearer, x-api-key, or x-rasputin-key</small>
                  </span>
                </div>
                <UIButton type="button" size="sm" onClick={rotateKey} disabled={isBusy} data-testid="serving-key-rotate">
                  <KeyRound size={14} /> {status.apiKeyConfigured ? "Rotate key" : "Generate key"}
                </UIButton>
              </div>
              {apiKey && (
                <div className="serving-secret" data-testid="serving-key-reveal">
                  <div>
                    <strong>Copy this key now</strong>
                    <small>Rasputin stores only its hash and cannot show it again.</small>
                  </div>
                  <code>{apiKey}</code>
                  <UIButton type="button" variant="outline" size="sm" onClick={() => copyText(apiKey, "key")}>
                    {copied === "key" ? <Check size={14} /> : <Copy size={14} />} {copied === "key" ? "Copied" : "Copy key"}
                  </UIButton>
                </div>
              )}
            </div>

            <div className="serving-control-card">
              <Toggle
                checked={Boolean(status.mcpToolExecution)}
                disabled={isBusy}
                label="Allow MCP tools/call"
                description="Tool discovery stays available; execution remains governed by Rasputin permissions and approvals."
                testId="serving-mcp-toggle"
                onChange={(mcpToolExecution) => updateConfig({ mcpToolExecution })}
              />
              <div className="serving-safety-note">
                <ShieldCheck size={17} />
                <p><strong>Safe by default.</strong> Compatibility requests can return tool calls to their caller, but never execute MCP tools automatically. Prompt and message content is not stored in request metrics.</p>
              </div>
            </div>
          </section>

          <section className="serving-protocol-section">
            <div className="serving-section-heading">
              <div>
                <h3>Compatible endpoints</h3>
                <p>Use the generated key with any endpoint below. The desktop app binds to loopback by default.</p>
              </div>
              <Badge variant="muted">{status.bindPolicy === "loopback-default" ? "Loopback default" : status.bindPolicy}</Badge>
            </div>
            <div className="serving-protocol-grid">
              {protocols.map((protocol) => (
                <article className="serving-protocol-card" key={protocol.id} data-testid={`serving-protocol-${protocol.id}`}>
                  <header>
                    <span className="serving-protocol-icon" aria-hidden="true">
                      {protocol.id === "rasputin" ? <Activity size={16} /> : <RadioTower size={16} />}
                    </span>
                    <div>
                      <strong>{protocol.id === "mcp" ? "MCP JSON-RPC HTTP (limited)" : protocol.name}</strong>
                      <small>{(protocol.features || []).join(" · ")}</small>
                    </div>
                    <Badge variant={status?.enabled && status?.apiKeyConfigured && normalizedState(protocol.status) === "ready" ? "up" : "muted"}>
                      {status?.enabled ? (status?.apiKeyConfigured ? (protocol.status || "Status not reported") : "Key required") : "Gateway off"}
                    </Badge>
                  </header>
                  <p className="serving-protocol-guidance">{protocolGuidance[protocol.id]?.text || "Use the serving API key with this endpoint."}</p>
                  {protocolGuidance[protocol.id] && (
                    <div className="serving-credential-guidance">
                      <code>{protocolGuidance[protocol.id].headers}</code>
                      <UIButton type="button" variant="outline" size="sm" onClick={() => copyText(protocolGuidance[protocol.id].headers, `headers-${protocol.id}`, `${protocol.name || protocol.id} headers`)}>
                        {copied === `headers-${protocol.id}` ? <Check size={13} /> : <Copy size={13} />} {copied === `headers-${protocol.id}` ? "Copied" : "Copy headers"}
                      </UIButton>
                    </div>
                  )}
                  <div className="serving-endpoint-list">
                    {(protocol.endpoints || []).map((endpoint) => (
                      <div key={endpoint}>
                        <code>{endpoint}</code>
                        <button type="button" aria-label={`Copy ${endpoint}`} title="Copy endpoint" onClick={() => copyText(endpoint, endpoint, "Endpoint")}>
                          {copied === endpoint ? <Check size={13} /> : <Copy size={13} />}
                        </button>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="serving-metrics-section">
            <div className="serving-section-heading">
              <div>
                <h3>Recent serving performance</h3>
                <p>Latency, throughput, token counts, and runtime identity only—never prompts or message text.</p>
              </div>
              <Badge variant="muted">{status.metricsCount || 0} captured</Badge>
            </div>
            {recent.length ? (
              <div className="serving-metrics-table-wrap">
                <table className="serving-metrics-table">
                  <thead>
                    <tr><th>Request</th><th>Model / runtime</th><th>First token</th><th>Total</th><th>Throughput</th><th>Tokens</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {[...recent].reverse().map((item) => (
                      <tr key={item.requestId}>
                        <td><strong>{item.protocol}</strong><small>{item.requestId}</small></td>
                        <td><strong>{item.model || "—"}</strong><small>{item.runtime || "—"}</small></td>
                        <td>{formatMs(item.timeToFirstTokenMs)}</td>
                        <td>{formatMs(item.totalMs)}</td>
                        <td>{Number.isFinite(Number(item.decodeTokensPerSecond)) ? `${Number(item.decodeTokensPerSecond).toFixed(1)} tok/s` : "—"}</td>
                        <td>{formatTokens(item.inputTokens, item.outputTokens)}</td>
                        <td><Badge variant={item.status === "completed" ? "up" : "down"}>{item.status}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="serving-empty-metrics">
                <Activity size={18} />
                <div><strong>No serving requests yet</strong><small>Authenticated API requests will appear here without their content.</small></div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
