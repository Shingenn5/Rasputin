import React, { useEffect, useState } from "react";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { Button } from "../../components/ui/button.jsx";
import { ModelServingPanel } from "../models/ModelServingPanel.jsx";
import "./workstation.css";

export function ApiView({ view }) {
  const [keys, setKeys] = useState([]);
  const [gateway, setGateway] = useState(null);
  const [name, setName] = useState("");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const baseUrl = `${window.location.origin}/v1`;
  async function refresh() {
    const [credentials, status] = await Promise.all([api("/api/model-serving/keys"), api("/api/model-serving")]);
    setKeys(credentials.keys || []); setGateway(status);
  }
  useEffect(() => { refresh().catch((e) => setError(e.message)); }, []);
  async function create(event) {
    event.preventDefault();
    setBusy(true); setError(""); setSecret("");
    try {
      const result = await postJson("/api/model-serving/keys", { name });
      setSecret(result.apiKey); setName(""); await refresh();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function revoke(id) {
    setBusy(true); setError("");
    try {
      await api(`/api/model-serving/keys/${encodeURIComponent(id)}`, { method: "DELETE" });
      setSecret(""); await refresh();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <section className={`app-view workstation-view ${view === "api" ? "active" : ""}`} data-app-view="api" id="apiView">
    <header className="workstation-heading"><div><h1>API</h1><p>Your local models, in the tools you already use.</p></div></header>
    {error && <p className="workstation-error" role="alert">{error}</p>}
    <div className="workstation-grid">
      <section className="workstation-card"><h2>Connect an application</h2><p>Choose an OpenAI-compatible provider in your client and enter this base URL, a key, and a model ID from the gateway below.</p>
        <label className="workstation-field">Base URL<input readOnly value={baseUrl} onFocus={(e) => e.target.select()} /></label>
        <p className="workstation-muted">The app must stay open and the model must be loaded. This address works on this computer. Keys do not enable remote access.</p>
        <h2>Available model IDs</h2>
        {gateway?.servableModels?.length ? gateway.servableModels.map((model) => <label className="workstation-field" key={model.id}>{model.name}<input readOnly value={model.id} onFocus={(e) => e.target.select()} /></label>) : <p className="workstation-muted">Load and verify a model in Library to make it available here.</p>}
        {gateway && <p className="workstation-muted">Gateway: {gateway.enabled ? "enabled" : "off"}. {(gateway.nextActions || []).join(" ")}</p>}
        <details><summary>Python example</summary><pre>{`from openai import OpenAI\nimport os\n\nclient = OpenAI(base_url="${baseUrl}",\n                api_key=os.environ["RASPUTIN_API_KEY"])\nmodels = client.models.list()\nreply = client.chat.completions.create(\n    model=models.data[0].id,\n    messages=[{"role": "user", "content": "Hello"}],\n)\nprint(reply.choices[0].message.content)`}</pre></details>
      </section>
      <section className="workstation-card"><h2>Application keys</h2><p>Create a separate key for each client. These keys grant local inference only.</p>
        <form onSubmit={create} className="workstation-inline"><label className="workstation-field">Key name<input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="My editor" /></label><Button disabled={busy || !name.trim()} type="submit"><Plus />Create key</Button></form>
        {secret && <div className="workstation-notice" role="status"><strong>Copy your key now</strong><p>It appears once. Save it in your client before leaving this page.</p><label className="workstation-field">New API key<input readOnly value={secret} onFocus={(e) => e.target.select()} autoComplete="off" spellCheck={false} /></label><Button variant="ghost" onClick={() => setSecret("")}>Hide key</Button></div>}
        <ul className="workstation-list">{keys.map((key) => <li key={key.id}><div><strong>{key.name}</strong><small>{key.prefix}… · {key.revokedAt ? "Revoked" : "Active"}</small></div>{!key.revokedAt && <Button variant="ghost" disabled={busy} aria-label={`Revoke ${key.name}`} onClick={() => revoke(key.id)}><Trash2 size={16} /></Button>}</li>)}</ul>
        {!keys.length && <p className="workstation-muted">No application keys yet.</p>}
        <Button variant="ghost" disabled={busy} onClick={() => refresh().catch((e) => setError(e.message))}><RefreshCw />Refresh keys</Button>
      </section>
    </div>
    <details className="workstation-card workstation-gateway"><summary>Gateway status and advanced protocols</summary><ModelServingPanel onOpenModels={() => { window.location.hash = "models"; }} /></details>
  </section>;
}
