import { useEffect, useState } from "react";
import { api, postJson } from "../../api/client.js";
import { Button } from "@/components/ui/button.jsx";

export function ModelDownloadFolder() {
  const [settings, setSettings] = useState(null);
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    api("/api/models/storage").then((result) => {
      if (!active) return;
      setSettings(result);
      setFolder(result.downloadFolder);
    }).catch((failure) => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, []);

  async function save(value) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await postJson("/api/models/storage", { downloadFolder: value });
      setSettings(result);
      setFolder(result.downloadFolder);
      setMessage("Download folder saved. New downloads will use this location.");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="min-w-0 rounded-lg border border-border p-3 mb-3" data-testid="model-download-folder">
      <summary className="cursor-pointer focus-visible:outline-2 focus-visible:outline-ring">
        <strong>Download folder</strong>
        {settings && <span className="block text-sm text-muted-foreground break-all mt-1">{settings.downloadFolder}</span>}
      </summary>
      <p className="text-sm text-muted-foreground my-3">Choose where new models are downloaded on the computer running Rasputin. Existing models and downloads already in progress stay in their current folders.</p>
      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); save(folder.trim()); }}>
        <label className="flex-1 min-w-0 basis-64 text-sm">
          Model download folder
          <input className="w2-input w-full mt-1" value={folder} onChange={(event) => { setFolder(event.target.value); setMessage(""); }} required disabled={busy || !settings} placeholder="Absolute path to a model folder" />
        </label>
        <Button type="submit" disabled={busy || !settings || !folder.trim() || folder.trim() === settings.downloadFolder}>{busy ? "Saving…" : "Save folder"}</Button>
        <Button type="button" variant="outline" disabled={busy || !settings || settings.downloadFolder === settings.defaultFolder} onClick={() => save(settings.defaultFolder)}>Use default</Button>
      </form>
      {error && <p role="alert" className="text-sm mt-2">{error}</p>}
      {message && <p role="status" className="text-sm mt-2">{message}</p>}
    </details>
  );
}
