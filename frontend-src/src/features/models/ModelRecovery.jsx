import { useState } from "react";
import { RefreshCw, SlidersHorizontal, FileSearch } from "lucide-react";
import { postJson } from "../../api/client.js";
import { Button } from "../../components/Button.jsx";
import { LocalModelSources } from "./LocalModelSources.jsx";

export function ModelRecovery({ model, signal, onConfigureLoad, onSaved, onFindModels }) {
  const [address, setAddress] = useState(model.baseUrl || model.base_url || "");
  const [modelId, setModelId] = useState(model.model || "");
  const [apiKey, setApiKey] = useState("");
  const [path, setPath] = useState("");
  const [available, setAvailable] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const external = !model.managed && model.runtime !== "native-llamacpp";
  async function act(operation) {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); }
    catch (failure) { setError(failure.message || "Unable to complete this action. Try again."); }
    finally { setBusy(false); }
  }
  async function check() {
    const result = await postJson("/api/model-registry/discover", { key: model.key });
    const ids = result.models || [];
    setAvailable(ids);
    const state = result.status || result.runtimeStatus;
    const matched = !ids.length || ids.includes(modelId);
    setMessage(["reachable", "ready"].includes(state) && matched
      ? "Connection confirmed. This model is ready to use."
      : ids.length ? "The app responded. Choose a served model ID below, then save and check again."
        : "The model is still unavailable. Check the address and API key, and make sure its app is serving a model.");
    await onSaved?.();
  }
  return <section className={`model-recovery is-${signal.key}`} aria-label="Model status and recovery">
    <div className="model-recovery-heading"><span className="model-recovery-dot" aria-hidden="true" /><h3>{signal.label}</h3></div>
    <p>{signal.detail}</p><p className="model-recovery-next">{signal.next}</p>
    <div className="model-recovery-actions">
      {["load", "configure"].includes(signal.action) && <Button primary onClick={() => onConfigureLoad?.(model)} icon={<SlidersHorizontal size={15} />}>{signal.action === "load" ? "Load model" : "Adjust settings and retry"}</Button>}
      {signal.action === "download" && <Button primary onClick={() => onConfigureLoad?.(model)}>Find a GGUF version</Button>}
      {!["wait", "load", "file", "download"].includes(signal.action) && <Button loading={busy} loadingLabel="Checking…" onClick={() => act(check)} icon={<RefreshCw size={15} />}>Check again</Button>}
      {signal.action === "download" && <Button onClick={onFindModels}>Browse models</Button>}
    </div>
    {external && <details className="model-repair-form" open={signal.key === "down" || undefined}>
      <summary>Edit connection</summary>
      <form onSubmit={(event) => { event.preventDefault(); act(async () => {
        await postJson("/api/model-registry/repair-settings", { key: model.key, baseUrl: address, modelId, ...(apiKey ? { apiKey } : {}) });
        setApiKey("");
        await onSaved?.();
        await check();
      }); }}>
        <label>Server address<input type="url" required value={address} onChange={(event) => setAddress(event.target.value)} placeholder="http://127.0.0.1:8888/v1" /></label>
        <label>Model ID<input required value={modelId} list={`served-models-${model.key}`} onChange={(event) => setModelId(event.target.value)} /></label>
        <datalist id={`served-models-${model.key}`}>{available.map((id) => <option key={id} value={id} />)}</datalist>
        {available.length > 0 && <div className="model-available-choices"><span>Models served by this app</span>{available.map((id) => <button type="button" key={id} onClick={() => setModelId(id)}>{id}</button>)}</div>}
        <label>New API key <small>Leave blank to keep your saved key.</small><input type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} /></label>
        <Button type="submit" primary loading={busy} loadingLabel="Saving…">Save and check connection</Button>
      </form>
      <p>Rasputin can update this connection here. The app that owns the model must still be running.</p>
    </details>}
    {signal.action === "file" && <div className="model-repair-form">
      <form onSubmit={(event) => { event.preventDefault(); act(async () => {
        await postJson("/api/model-registry/repair-settings", { key: model.key, path });
        await onSaved?.(); setMessage("Model file updated. You can now load it from Rasputin.");
      }); }}>
        <label>Replacement GGUF file<input value={path} required onChange={(event) => setPath(event.target.value)} placeholder="Full path to a GGUF in your model library" /></label>
        <Button type="submit" loading={busy} loadingLabel="Updating…" icon={<FileSearch size={15} />}>Use this model file</Button>
      </form>
      <p>If the file is in a new folder, import that folder first using the control below.</p>
      <LocalModelSources onImported={onSaved} />
    </div>}
    {signal.technical && signal.key !== "live" && <details className="model-error-details"><summary>Technical error details</summary><pre>{signal.technical}</pre></details>}
    {error && <p role="alert" className="model-repair-error">{error}</p>}
    {message && <p role="status">{message}</p>}
  </section>;
}
