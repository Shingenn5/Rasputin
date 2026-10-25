import React, { useState } from "react";
import { postJson } from "../../api/client.js";

export function LocalModelSources({ onImported }) {
  const [folder, setFolder] = useState("");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:8888/v1");
  const [apiKey, setApiKey] = useState("");
  const [found, setFound] = useState([]);
  const [probedEndpoint, setProbedEndpoint] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function run(action) {
    setBusy(true);
    setError("");
    setMessage("");
    try { await action(); }
    catch (err) { setError(err.message || "Unable to access this model source."); }
    finally { setBusy(false); }
  }
  const scan = (root) => run(async () => {
    const result = await postJson("/api/model-registry/local-sources/scan", root ? { root } : {});
    await onImported?.();
    setMessage(`${result.registered?.length || 0} models added; ${result.existing?.length || 0} already registered.${result.truncated ? " Scan limit reached; choose a narrower folder and scan again." : ""}`);
  });
  return <details className="local-model-sources" data-testid="local-model-sources">
    <summary>Import from other apps · Unsloth, LM Studio, Ollama</summary>
    <p>Reuse GGUF files without copying or downloading them again. Load and tune imported files in My Models. Keep the original files available.</p>
    <button type="button" className="w2-button" disabled={busy} onClick={() => scan()}>Scan known model folders</button>
    <form onSubmit={(event) => { event.preventDefault(); scan(folder.trim()); }}>
      <label>Model export folder<input className="w2-input" value={folder} required onChange={(event) => setFolder(event.target.value)} placeholder="Folder containing exported GGUF files" /></label>
      <button className="w2-button" disabled={busy || !folder.trim()}>Scan and import folder</button>
    </form>
    <p>Known folders include LM Studio, Unsloth Studio exports and cache, and the Hugging Face cache. For another library, enter its folder above. Safetensors, adapters, and Ollama blobs need a GGUF export or a running compatible server.</p>
    <details>
      <summary>Connect a running local engine</summary>
      <p>Enter its OpenAI-compatible API address. The engine owns model loading and tuning; Rasputin connects to the model it serves.</p>
      <form onSubmit={(event) => { event.preventDefault(); run(async () => {
        setFound([]);
        setSelected("");
        const result = await postJson("/api/model-registry/local-sources/probe", { baseUrl: endpoint, apiKey });
        setFound(result.models || []);
        setSelected(result.models?.[0] || "");
        setProbedEndpoint(result.baseUrl);
        setMessage(`${result.models?.length || 0} models found at this endpoint.`);
      }); }}>
        <label>Local API address<input className="w2-input" type="url" required value={endpoint} onChange={(event) => { setEndpoint(event.target.value); setFound([]); }} /></label>
        <label>API key (if required)<input className="w2-input" type="password" autoComplete="off" value={apiKey} onChange={(event) => { setApiKey(event.target.value); setFound([]); }} /></label>
        <button className="w2-button" disabled={busy}>Find served models</button>
      </form>
      {found.length > 0 && <form onSubmit={(event) => { event.preventDefault(); run(async () => {
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${probedEndpoint}\n${selected}`));
        const key = "external-" + Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("").slice(0, 24);
        const model = await postJson("/api/model-registry/upsert", { key, name: selected, model: selected, baseUrl: probedEndpoint, apiKey, provider: "openai-compatible", runtime: "external-local", enabled: true, managed: false });
        await postJson("/api/model-registry/discover", { key: model.key });
        await onImported?.();
        setApiKey("");
        setFound([]);
        setMessage("Local engine model connected. Select it in My Models to use it.");
      }); }}>
        <label>Served model<select className="w2-input" value={selected} onChange={(event) => setSelected(event.target.value)}>{found.map((id) => <option key={id}>{id}</option>)}</select></label>
        <button className="w2-button" disabled={busy || !selected}>Connect model</button>
      </form>}
    </details>
    {busy && <p role="status">Checking model source…</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error}</p>}
  </details>;
}
