import { Activity, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

export const EXP_TYPES = [
  { value: "model", label: "Model Test" },
  { value: "prompt", label: "Prompt Test" },
  { value: "agent", label: "Agent Test" },
  { value: "workflow", label: "Workflow Test" },
  { value: "rag", label: "RAG Test" },
  { value: "tool", label: "Tool Test" },
  { value: "custom", label: "Custom" },
];

export function statusColor(st) {
  if (["completed", "done", "success", "running"].includes(st)) return "var(--ras-safe)";
  if (["failed", "error", "cancelled"].includes(st)) return "var(--ras-danger)";
  if (["draft", "pending", "paused"].includes(st)) return "var(--ras-warn)";
  return "var(--cc-muted)";
}

export function statusIcon(st) {
  if (st === "running") return <Loader2 size={14} color="var(--ras-safe)" style={{ animation: "spin 1s linear infinite" }} />;
  if (["completed", "done", "success"].includes(st)) return <CheckCircle2 size={14} color="var(--ras-safe)" />;
  if (["failed", "error"].includes(st)) return <AlertTriangle size={14} color="var(--ras-danger)" />;
  return <Activity size={14} color="var(--cc-muted)" />;
}

export function fmtDate(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function RadarChart({ scores, size = 200 }) {
  const categories = ["accuracy", "reasoning", "reliability", "performance", "efficiency", "safety", "usability"];
  const labels = ["Accuracy", "Reasoning", "Reliability", "Performance", "Efficiency", "Safety", "Usability"];
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.38;
  const angleStep = (2 * Math.PI) / categories.length;
  const offset = -Math.PI / 2;

  function point(i, r) {
    const a = offset + i * angleStep;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  }

  const rings = [0.25, 0.5, 0.75, 1.0];
  const dataPoints = categories.flatMap((cat, i) => {
    const score = scores?.[cat];
    if (typeof score !== "number" || !Number.isFinite(score)) return [];
    const val = Math.min(Math.max(score / 100, 0), 1);
    return [{ category: cat, point: point(i, val * maxR) }];
  });
  const polyPoints = dataPoints.map(({ point: coordinates }) => coordinates.join(",")).join(" ");

  return (
    <svg role="img" aria-label="Measured scorecard dimensions; missing dimensions have no point" data-testid="scorecard-radar" width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: "visible" }}>
      {/* Grid rings */}
      {rings.map(r => (
        <polygon
          key={r}
          points={categories.map((_, i) => point(i, r * maxR).join(",")).join(" ")}
          fill="none"
          stroke="var(--cc-border)"
          strokeWidth="0.5"
          opacity="0.5"
        />
      ))}
      {/* Axis lines */}
      {categories.map((_, i) => {
        const [ex, ey] = point(i, maxR);
        return <line key={i} x1={cx} y1={cy} x2={ex} y2={ey} stroke="var(--cc-border)" strokeWidth="0.5" opacity="0.3" />;
      })}
      {/* Data polygon */}
      {dataPoints.length === categories.length && (
        <polygon data-testid="scorecard-data-polygon" points={polyPoints} fill="color-mix(in srgb, var(--cc-accent) 25%, transparent)" stroke="var(--cc-accent)" strokeWidth="2" />
      )}
      {/* Missing measurements have neither a dot nor a fabricated zero. */}
      {dataPoints.map(({ category, point: [x, y] }) => (
        <circle key={category} data-score-category={category} cx={x} cy={y} r="3" fill="var(--cc-accent)" />
      ))}
      {/* Labels */}
      {categories.map((_, i) => {
        const [lx, ly] = point(i, maxR + 16);
        return (
          <text key={i} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize="9" fill="var(--cc-muted)" fontWeight="500">
            {labels[i]}
          </text>
        );
      })}
    </svg>
  );
}

export function ScorecardMeasurements({ scorecard }) {
  const categories = ["accuracy", "reasoning", "reliability", "performance", "efficiency", "safety", "usability", "overall"];
  const evidence = scorecard.evidence || {};
  const current = evidence.schemaVersion === 1;
  const scores = Object.fromEntries(categories.map(category => {
    const value = scorecard.scores?.[category];
    const state = evidence.dimensions?.[category]?.state;
    const measured = current && (state === "measured" || (category === "overall" && state === "derived"));
    return [category, measured && typeof value === "number" && Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : null];
  }));
  const measured = categories.filter(category => category !== "overall" && scores[category] !== null);
  const label = category => category === "reliability" ? "Request completion" : category === "overall" ? "Measured average" : category;
  return (
    <div data-testid="trial-scorecard" style={{ fontSize: "0.75rem", overflowWrap: "anywhere" }}>
      {measured.length > 0 && <div style={{ display: "flex", justifyContent: "center", padding: "8px 0 18px" }}>
        <RadarChart scores={scores} size={200} />
      </div>}
      <p style={{ color: "var(--cc-muted)" }}>
        {measured.length} of 7 dimensions measured. Missing dimensions are excluded from the average.
      </p>
      {(!current || evidence.notice) && <p role="note" style={{ color: "var(--ras-warn)" }}>
        {evidence.notice || "This older scorecard has no measurement provenance. Regenerate it to use recorded experiment evidence."}
      </p>}
      <dl style={{ display: "grid", gap: "4px", margin: 0 }}>
        {categories.map(category => {
          const score = scores[category];
          return <div key={category} data-testid={`scorecard-${category}`} style={{ display: "flex", justifyContent: "space-between", gap: "8px", padding: "4px 8px", background: "var(--cc-bg)", borderRadius: "4px" }}>
            <dt style={{ color: "var(--cc-muted)", textTransform: "capitalize" }}>{label(category)}</dt>
            <dd style={{ margin: 0, fontWeight: 600, color: score === null ? "var(--cc-muted)" : "inherit" }}>
              {score === null ? "Not measured" : `${score} / 100`}
            </dd>
          </div>;
        })}
      </dl>
      <details style={{ marginTop: "12px" }}>
        <summary style={{ cursor: "pointer" }}>Measurement details</summary>
        <p>Configured dataset: {evidence.configuredDatasetId || "Not recorded"}. Evaluated version: {evidence.datasetVersion || "Not recorded"}.</p>
        {evidence.datasetNotice && <p>{evidence.datasetNotice}</p>}
        <p>Experiment last updated: {fmtDate(evidence.experimentUpdatedAt)}. Scorecard generated: {fmtDate(scorecard.createdAt)}.</p>
        {typeof evidence.observations?.totalDurationMs === "number" && Number.isFinite(evidence.observations.totalDurationMs) &&
          <p>Recorded experiment duration: {evidence.observations.totalDurationMs.toLocaleString()} ms. This is elapsed time for the whole experiment.</p>}
        {categories.map(category => {
          const detail = evidence.dimensions?.[category] || {};
          return <div key={category}>
            <strong style={{ textTransform: "capitalize" }}>{label(category)}</strong>
            {scores[category] === null ? <p>{detail.reason || "No supported measurement was recorded."}</p> : <>
              <p>{detail.method || "Scoring method not recorded."}</p>
              {category !== "overall" && <>
                <p>Samples: {detail.sampleCount ?? "Not recorded"}. Source: {detail.source || "Not recorded"}.</p>
                <p>Uncertainty: {detail.uncertainty || "Not estimated."}</p>
              </>}
            </>}
          </div>;
        })}
        {(evidence.limitations || []).map(limitation => <p key={limitation}>{limitation}</p>)}
      </details>
    </div>
  );
}
