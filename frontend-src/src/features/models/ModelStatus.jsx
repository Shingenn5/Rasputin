import { Crosshair } from "lucide-react";
import { labelize } from "../../lib/display.js";

export function ModelStateSignal({ signal, chatActive = false, compact = false, role }) {
  return (
    <span className={`models-state-signal is-${signal.key} ${compact ? "is-compact" : ""}`} role={role}>
      <span className="models-state-glyph" aria-hidden="true"><i /><i /><i /></span>
      <span className="models-state-copy"><strong>{signal.label}</strong><small>{signal.detail}</small></span>
      {chatActive && <span className="models-chat-target"><Crosshair size={11} aria-hidden="true" /> Chat Target</span>}
    </span>
  );
}

export function CompatibilitySummary({ model }) {
  const profile = model?.compatibility;
  if (!profile) {
    return (
      <div data-testid="model-compatibility" className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        Not certified yet. Run Test to verify chat, context retention, and tool calling automatically.
      </div>
    );
  }
  const legacyFallback = profile.status === "incompatible";
  const status = legacyFallback ? "limited" : (profile.status || "unknown");
  const tier = legacyFallback ? "basic-inference" : (profile.tier || "unknown");
  const modes = legacyFallback ? ["chat"] : (Array.isArray(profile.supportedModes) ? profile.supportedModes : []);
  const issues = Array.isArray(profile.issues) ? profile.issues : [];
  const tone = status === "certified" ? "text-emerald-400" : status === "incompatible" ? "text-red-400" : "text-amber-400";
  return (
    <div data-testid="model-compatibility" className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <strong className={tone}>{labelize(status)}</strong>
        <span className="text-muted-foreground">Tier: {labelize(tier)}</span>
        <span className="text-muted-foreground">Context profile: {labelize(legacyFallback ? "minimal" : (profile.promptProfile || "standard"))}</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        Modes: {modes.length ? modes.map(labelize).join(", ") : "None"}
      </div>
      {issues[0] && <div className="mt-1 text-amber-400">{issues[0]}</div>}
    </div>
  );
}
