import React, { useEffect, useState } from "react";
import { CheckCircle2, Mail, MessageSquare, Plug, RefreshCw, ShieldCheck, Trash2, Webhook } from "lucide-react";
import { api, postJson } from "../../api/client.js";
import { Button } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";

const providerIcons = { gmail: Mail, outlook: Mail, teams: MessageSquare, webhook: Webhook };

export function IntegrationSettings() {
  const [catalog, setCatalog] = useState([]);
  const [connectors, setConnectors] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ displayName: "", clientId: "", clientSecret: "", tenantId: "", url: "", secret: "" });
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const payload = await api("/api/connectors");
      setCatalog(payload.providers || []);
      setConnectors(payload.connectors || []);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function begin(provider) {
    const existing = connectors.find((item) => item.provider === provider.id);
    setSelected({ provider, existing });
    setForm({
      displayName: existing?.display_name || provider.name,
      clientId: existing?.config?.clientId || "",
      clientSecret: "",
      tenantId: existing?.config?.tenantId || "",
      url: existing?.config?.url || "",
      secret: "",
    });
    setStatus("");
  }

  async function save(event) {
    event.preventDefault();
    if (!selected) return;
    setLoading(true);
    try {
      const provider = selected.provider.id;
      const oauth = selected.provider.auth === "oauth2";
      const connector = await postJson("/api/connectors", {
        id: selected.existing?.id,
        provider,
        displayName: form.displayName || selected.provider.name,
        config: oauth ? { clientId: form.clientId, tenantId: form.tenantId } : { url: form.url },
        credentials: oauth ? { clientSecret: form.clientSecret } : { secret: form.secret },
      });
      setStatus(`${connector.display_name} saved locally.`);
      await load();
      setSelected(null);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function test(connector) {
    try {
      const result = await postJson(`/api/connectors/${connector.id}/test`, {});
      setStatus(result.message);
      await load();
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function remove(connector) {
    if (!window.confirm(`Remove ${connector.display_name}? Its locally stored credentials will be deleted.`)) return;
    try {
      await api(`/api/connectors/${connector.id}`, { method: "DELETE" });
      setStatus(`${connector.display_name} removed.`);
      await load();
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <section className="settings-pane active tw space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div><h2 className="flex items-center gap-2 text-2xl font-bold"><Plug className="text-primary" /> Connector Center</h2><p className="mt-1 text-sm text-muted-foreground">Prepare private, account-scoped connections to mail, collaboration tools, and HTTPS webhooks.</p></div>
        <Badge variant="muted">{connectors.length} configured</Badge>
      </header>

      {status && <div className="rounded-xl border border-border bg-card p-3 text-sm" role="status">{status}</div>}

      <div className="grid gap-3 md:grid-cols-2">
        {catalog.map((provider) => {
          const Icon = providerIcons[provider.id] || Plug;
          const connector = connectors.find((item) => item.provider === provider.id);
          return (
            <article key={provider.id} className="glow-card rounded-2xl border border-border bg-card p-5">
              <div className="flex items-start justify-between gap-3"><span className="rounded-xl bg-primary/10 p-3 text-primary"><Icon size={22} /></span><Badge variant={connector?.status === "ready" ? "up" : connector ? "muted" : "outline"}>{connector?.status?.replaceAll("_", " ") || "not configured"}</Badge></div>
              <h3 className="mt-4 font-semibold">{provider.name}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{provider.capabilities.map((item) => item.replaceAll("_", " ")).join(" · ")}</p>
              {connector && <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground"><ShieldCheck size={14} className="text-primary" />Credentials stored locally {connector.hasCredentials ? "and masked" : "(none saved)"}</div>}
              <div className="mt-5 flex gap-2"><Button size="sm" onClick={() => begin(provider)}>{connector ? "Configure" : "Set up"}</Button>{connector && <><Button variant="outline" size="sm" onClick={() => test(connector)}><RefreshCw size={14} /> Check</Button><Button variant="ghost" size="icon" onClick={() => remove(connector)} aria-label={`Remove ${provider.name}`}><Trash2 size={15} /></Button></>}</div>
            </article>
          );
        })}
      </div>

      {selected && (
        <form className="rounded-2xl border border-primary/30 bg-card p-5 shadow-lg" onSubmit={save}>
          <div className="mb-4 flex items-center justify-between"><div><h3 className="font-semibold">Configure {selected.provider.name}</h3><p className="text-xs text-muted-foreground">Secrets are never returned to the browser after saving.</p></div><Button type="button" variant="ghost" onClick={() => setSelected(null)}>Cancel</Button></div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm"><span className="mb-1.5 block font-medium">Connection name</span><input className="w2-input w-full" value={form.displayName} onChange={(event) => setForm({ ...form, displayName: event.target.value })} /></label>
            {selected.provider.auth === "oauth2" ? <>
              <label className="text-sm"><span className="mb-1.5 block font-medium">OAuth client ID</span><input className="w2-input w-full" required value={form.clientId} onChange={(event) => setForm({ ...form, clientId: event.target.value })} /></label>
              {selected.provider.id !== "gmail" && <label className="text-sm"><span className="mb-1.5 block font-medium">Tenant ID</span><input className="w2-input w-full" required value={form.tenantId} onChange={(event) => setForm({ ...form, tenantId: event.target.value })} /></label>}
              <label className="text-sm"><span className="mb-1.5 block font-medium">OAuth client secret</span><input className="w2-input w-full" type="password" required={!selected.existing?.hasCredentials} value={form.clientSecret} placeholder={selected.existing?.hasCredentials ? "Stored—leave blank to keep" : "Paste client secret"} onChange={(event) => setForm({ ...form, clientSecret: event.target.value })} /></label>
            </> : <>
              <label className="text-sm md:col-span-2"><span className="mb-1.5 block font-medium">HTTPS webhook URL</span><input className="w2-input w-full" type="url" required value={form.url} placeholder="https://example.com/hooks/rasputin" onChange={(event) => setForm({ ...form, url: event.target.value })} /></label>
              <label className="text-sm"><span className="mb-1.5 block font-medium">Signing secret (optional)</span><input className="w2-input w-full" type="password" value={form.secret} onChange={(event) => setForm({ ...form, secret: event.target.value })} /></label>
            </>}
          </div>
          {selected.provider.auth === "oauth2" && <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">This stores and validates your OAuth application configuration. Account authorization and mail/message synchronization remain disabled until the OAuth handoff is completed.</div>}
          <div className="mt-5 flex justify-end"><Button type="submit" disabled={loading}><CheckCircle2 size={15} /> Save locally</Button></div>
        </form>
      )}
    </section>
  );
}
