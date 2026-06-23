import React, { useState, useEffect } from "react";
import {
  Archive,
  Search,
  Camera,
  Target,
  FileText,
  Package,
  HardDrive,
  MessageSquare,
  Files,
  RefreshCw,
  Trash2,
  Download,
  CheckCircle2,
  AlertTriangle,
  RotateCcw
} from "lucide-react";
import { api, postJson } from "../../api/client.js";

const ARCHIVE_NAV = [
  { id: "all", label: "All Archives", icon: Archive },
  { id: "snapshots", label: "Snapshots", icon: Camera },
  { id: "missions", label: "Missions", icon: Target },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "exports", label: "Exports", icon: Package },
  { id: "backups", label: "Backups", icon: HardDrive },
  { id: "conversations", label: "Conversations", icon: MessageSquare },
  { id: "artifacts", label: "Artifacts", icon: Files },
];

export function ArchiveView({ view }) {
  const [activeNav, setActiveNav] = useState("all");
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);

  const fetchItems = async (type = null) => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL("/api/archive/items", window.location.origin);
      if (type && type !== "all") url.searchParams.append("type", type);
      if (search) url.searchParams.append("search", search);
      const res = await api(url.pathname + url.search);
      setItems(res || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (view === "archive") {
      fetchItems(activeNav);
    }
  }, [view, activeNav]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchItems(activeNav);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to permanently delete this archive item?")) return;
    try {
      await api(`/api/archive/items/${id}`, { method: "DELETE" });
      setItems(items.filter(i => i.id !== id));
      if (selectedItem?.id === id) setSelectedItem(null);
    } catch (err) {
      alert("Failed to delete: " + err.message);
    }
  };

  const handleRestore = async (id) => {
    if (!window.confirm("Are you sure you want to restore this archive item? This will modify your current state.")) return;
    try {
      await api(`/api/archive/items/${id}/restore`, { method: "POST" });
      alert("Restore completed successfully! (Audit log created)");
      fetchItems(activeNav);
    } catch (err) {
      alert("Failed to restore: " + err.message);
    }
  };

  return (
    <section className={`w2-layout app-view archive-view tw ${view === "archive" ? "active" : ""}`} id="archiveView" data-app-view="archive">
      <div className="fx-rise mx-auto flex max-w-[1500px] flex-col gap-5 p-7">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-5">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Archive size={26} className="text-primary" /> Archive <span className="text-muted-foreground">Center</span>
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Long-term retention, snapshot recovery, and mission preservation.</p>
        </div>
        <div className="flex gap-3">
          <div className="glow-card rounded-xl border border-border bg-card px-4 py-2.5 text-center">
            <div className="text-xl font-bold">{items.length}</div>
            <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">Total Items</div>
          </div>
          <div className="glow-card rounded-xl border border-border bg-card px-4 py-2.5 text-center">
            <div className="text-xl font-bold text-primary">Online</div>
            <div className="text-[0.66rem] uppercase tracking-wide text-muted-foreground">Vault Status</div>
          </div>
        </div>
      </div>

      <div className="w2-main-grid" style={{ gridTemplateColumns: "240px 1fr 320px", marginTop: "16px" }}>
        
        {/* ── Left Navigation ── */}
        <div className="w2-column">
          <div className="w2-card" style={{ padding: "8px" }}>
            {ARCHIVE_NAV.map(nav => {
              const Icon = nav.icon;
              return (
                <button
                  key={nav.id}
                  type="button"
                  className={`w2-list-item ${activeNav === nav.id ? "is-active" : ""}`}
                  style={{ background: activeNav === nav.id ? "var(--cc-surface)" : "transparent", padding: "8px 12px", borderRadius: "4px", border: "none", width: "100%", justifyContent: "flex-start", cursor: "pointer" }}
                  onClick={() => { setActiveNav(nav.id); setSelectedItem(null); }}
                >
                  <div style={{ display: "flex", gap: "12px", alignItems: "center", color: activeNav === nav.id ? "var(--cc-text)" : "var(--cc-muted)" }}>
                    <Icon size={16} />
                    <span style={{ fontSize: "0.875rem", fontWeight: activeNav === nav.id ? 600 : 400 }}>{nav.label}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Main View ── */}
        <div className="w2-column">
          <div className="w2-card">
            <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "8px" }}>
              <div style={{ position: "relative", flex: 1 }}>
                <Search size={16} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--cc-muted)" }} />
                <input
                  type="text"
                  className="w2-input"
                  style={{ paddingLeft: "36px", width: "100%" }}
                  placeholder={`Search ${activeNav}...`}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <button type="submit" className="w2-button primary"><Search size={14} /> Search</button>
              <button type="button" className="w2-button" onClick={() => fetchItems(activeNav)}><RefreshCw size={14} /> Refresh</button>
            </form>
          </div>

          <div className="w2-card" style={{ flex: 1, overflowY: "auto" }}>
            {loading ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)" }}>Searching archive...</div>
            ) : error ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--ras-danger)" }}>{error}</div>
            ) : items.length === 0 ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--cc-muted)" }}>No archive items found.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {items.map(item => (
                  <div
                    key={item.id}
                    className={`w2-list-item ${selectedItem?.id === item.id ? "is-active" : ""}`}
                    onClick={() => setSelectedItem(item)}
                    style={{ background: selectedItem?.id === item.id ? "color-mix(in srgb, var(--cc-accent) 10%, var(--cc-bg))" : "var(--cc-surface)" }}
                  >
                    <div>
                      <strong style={{ fontSize: "0.875rem" }}>{item.name}</strong>
                      <div style={{ fontSize: "0.75rem", color: "var(--cc-muted)", marginTop: "4px" }}>
                        {item.type} · {new Date(item.archived_at * 1000).toLocaleString()} · {Math.round(item.size / 1024)} KB
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Inspector Panel ── */}
        <div className="w2-column">
          <div className="w2-card" style={{ flex: 1 }}>
            <h3 style={{ margin: "0 0 16px 0", fontSize: "0.875rem" }}>Inspector</h3>
            {selectedItem ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px" }}>
                  <h4 style={{ margin: "0 0 8px 0", fontSize: "1rem" }}>{selectedItem.name}</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 12px", fontSize: "0.75rem" }}>
                    <span style={{ color: "var(--cc-muted)" }}>ID</span>
                    <span style={{ fontFamily: "monospace" }}>{selectedItem.id}</span>
                    <span style={{ color: "var(--cc-muted)" }}>Type</span>
                    <span>{selectedItem.type}</span>
                    <span style={{ color: "var(--cc-muted)" }}>Source</span>
                    <span>{selectedItem.source}</span>
                    <span style={{ color: "var(--cc-muted)" }}>Workspace</span>
                    <span>{selectedItem.workspace || "Global"}</span>
                    <span style={{ color: "var(--cc-muted)" }}>Created</span>
                    <span>{new Date(selectedItem.created_at * 1000).toLocaleString()}</span>
                  </div>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {(selectedItem.tags || []).map(tag => (
                    <span key={tag} style={{ background: "var(--cc-surface)", padding: "2px 8px", borderRadius: "999px", fontSize: "0.6875rem", border: "1px solid var(--cc-border)" }}>
                      {tag}
                    </span>
                  ))}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "auto" }}>
                  <button className="w2-button primary" onClick={() => handleRestore(selectedItem.id)}>
                    <RotateCcw size={14} /> Restore Item
                  </button>
                  <button className="w2-button" onClick={() => alert("Export not implemented")}>
                    <Download size={14} /> Download Export
                  </button>
                  <button className="w2-button" style={{ color: "var(--ras-danger)", borderColor: "color-mix(in srgb, var(--ras-danger) 30%, transparent)" }} onClick={() => handleDelete(selectedItem.id)}>
                    <Trash2 size={14} /> Delete Forever
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ color: "var(--cc-muted)", fontSize: "0.875rem", textAlign: "center", marginTop: "32px" }}>
                Select an item to view details.
              </div>
            )}
          </div>
        </div>

      </div>
      </div>
    </section>
  );
}
