import React, { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Command, FileText, MessageSquare, Search, X } from "lucide-react";
import { api } from "../api/client.js";
import { Button } from "@/components/ui/button.jsx";
import { Badge } from "@/components/ui/badge.jsx";

function ResultIcon({ type }) {
  if (type === "task") return <Activity size={16} />;
  if (type === "artifact") return <FileText size={16} />;
  return <MessageSquare size={16} />;
}

export function CommandPalette({ commands = [], onOpenTask, onOpenSession }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    function onKeyDown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setResults([]);
    setActiveIndex(0);
    window.requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!open || trimmed.length < 2) {
      setResults([]);
      setLoading(false);
      return undefined;
    }
    let active = true;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const payload = await api(`/api/search?q=${encodeURIComponent(trimmed)}&limit=20`);
        if (active) setResults(payload.results || []);
      } catch {
        if (active) setResults([]);
      } finally {
        if (active) setLoading(false);
      }
    }, 180);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [open, query]);

  const filteredCommands = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((item) => `${item.label} ${item.hint || ""} ${item.keywords || ""}`.toLowerCase().includes(needle));
  }, [commands, query]);
  const items = [...filteredCommands.map((command) => ({ kind: "command", command })), ...results.map((result) => ({ kind: "result", result }))];

  function activate(item) {
    if (!item) return;
    setOpen(false);
    if (item.kind === "command") {
      item.command.action?.();
      return;
    }
    if (item.result.taskId) onOpenTask?.(item.result.taskId);
    else if (item.result.sessionId) onOpenSession?.(item.result.sessionId);
  }

  if (!open) return (
    <button type="button" className="fixed bottom-5 right-5 z-20 hidden items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-2 text-xs text-muted-foreground shadow-lg backdrop-blur hover:text-foreground md:flex" onClick={() => setOpen(true)} aria-label="Open command palette">
      <Command size={14} /> Quick actions <kbd className="rounded border border-border px-1.5 py-0.5">Ctrl K</kbd>
    </button>
  );

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-black/60 px-4 pt-[12vh] backdrop-blur-sm" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-popover shadow-2xl" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search size={18} className="text-muted-foreground" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((value) => Math.min(value + 1, Math.max(items.length - 1, 0))); }
              if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((value) => Math.max(value - 1, 0)); }
              if (event.key === "Enter") { event.preventDefault(); activate(items[activeIndex]); }
            }}
            className="h-14 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            placeholder="Search chats and artifacts, or run a command..."
            aria-label="Search commands and Rasputin history"
          />
          <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close command palette"><X size={16} /></Button>
        </div>
        <div className="max-h-[58vh] overflow-y-auto p-2" role="listbox">
          {items.map((item, index) => {
            const key = item.kind === "command" ? `command-${item.command.label}` : `result-${item.result.type}-${item.result.id}`;
            return (
              <button
                key={key}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => activate(item)}
                className={`flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left ${index === activeIndex ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"}`}
              >
                <span className="mt-0.5 rounded-lg border border-border p-2 text-muted-foreground">{item.kind === "command" ? <Command size={16} /> : <ResultIcon type={item.result.type} />}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2"><strong className="truncate text-sm">{item.kind === "command" ? item.command.label : item.result.title}</strong>{item.kind === "result" && <Badge variant="muted">{item.result.type}</Badge>}</span>
                  <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.kind === "command" ? item.command.hint : item.result.snippet}</span>
                </span>
              </button>
            );
          })}
          {!items.length && <div className="p-8 text-center text-sm text-muted-foreground">{loading ? "Searching Rasputin..." : query.length < 2 ? "Type to search your chats, tasks, and artifacts." : "No matching commands or history."}</div>}
        </div>
        <footer className="flex items-center justify-between border-t border-border px-4 py-2 text-[0.7rem] text-muted-foreground"><span>↑↓ navigate · Enter open · Esc close</span><span>Private to this account</span></footer>
      </section>
    </div>
  );
}
