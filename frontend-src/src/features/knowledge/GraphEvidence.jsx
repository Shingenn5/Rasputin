import React from "react";
import { labelize } from "../../lib/display.js";

function firstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

function shorten(value, max = 280) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 3)}...`;
}

function citationText(evidence = {}) {
  const citation = evidence.citation || evidence;
  const path = firstValue(evidence.path, citation.path, evidence.source, "local source");
  const pageStart = firstValue(citation.pageStart, citation.page_start);
  const pageEnd = firstValue(citation.pageEnd, citation.page_end, pageStart);
  const sheetName = firstValue(citation.sheetName, citation.sheet_name);
  const rowStart = firstValue(citation.rowStart, citation.row_start);
  const rowEnd = firstValue(citation.rowEnd, citation.row_end, rowStart);
  const lineStart = firstValue(citation.lineStart, citation.line_start);
  const lineEnd = firstValue(citation.lineEnd, citation.line_end, lineStart);
  const chunk = firstValue(evidence.chunk, citation.chunk);

  let location = "";
  if (pageStart) location = `page ${pageStart}${pageEnd && pageEnd !== pageStart ? `-${pageEnd}` : ""}`;
  else if (sheetName) location = `${sheetName} rows ${rowStart || "?"}-${rowEnd || "?"}`;
  else if (lineStart) location = `lines ${lineStart}-${lineEnd || lineStart}`;
  else if (chunk !== undefined) location = `chunk ${chunk}`;

  return location ? `${path} / ${location}` : String(path);
}

function EvidenceList({ evidence = [], compact = false }) {
  const items = evidence.slice(0, compact ? 1 : 3);
  if (!items.length) {
    return <p className="graph-evidence-empty">No source evidence attached.</p>;
  }
  return (
    <div className="graph-evidence-list" aria-label="Source evidence">
      <span className="graph-evidence-title">Evidence</span>
      {items.map((item, index) => (
        <article className="graph-evidence-item" key={`${citationText(item)}-${index}`}>
          <span className="graph-evidence-citation">{citationText(item)}</span>
          {item.snippet && <p className="graph-evidence-snippet">{shorten(item.snippet, compact ? 180 : 260)}</p>}
        </article>
      ))}
    </div>
  );
}

export function GraphNodeCard({ node = {}, compact = false }) {
  const kind = firstValue(node.kind, node.type, "node");
  const evidence = Array.isArray(node.evidence) ? node.evidence : [];
  const sources = Array.isArray(node.sources) ? node.sources : [];
  return (
    <article className="graph-evidence-card" data-testid="graph-node-card">
      <div className="graph-evidence-card-head">
        <div>
          <span className="graph-type-pill">{labelize(kind)}</span>
          <strong>{node.name || "Unnamed graph node"}</strong>
        </div>
        {node.weight !== undefined && <span className="graph-evidence-meta">weight {node.weight}</span>}
      </div>
      {!evidence.length && !!sources.length && (
        <p className="graph-evidence-why">{sources.slice(0, 3).join(", ")}</p>
      )}
      <EvidenceList evidence={evidence} compact={compact} />
    </article>
  );
}

export function GraphEdgeCard({ edge = {}, compact = false }) {
  const sourceKind = firstValue(edge.sourceKind, edge.source_kind);
  const targetKind = firstValue(edge.targetKind, edge.target_kind);
  const evidence = Array.isArray(edge.evidence) ? edge.evidence : [];
  return (
    <article className="graph-evidence-card" data-testid="graph-edge-card">
      <div className="graph-evidence-card-head">
        <div>
          <span className="graph-type-pill">{labelize(edge.relation || "relationship")}</span>
          <strong>{edge.source || "source"} -&gt; {edge.target || "target"}</strong>
        </div>
        {edge.confidence !== undefined && <span className="graph-evidence-meta">confidence {edge.confidence}</span>}
      </div>
      <p className="graph-evidence-why">
        {edge.why || `Why Rasputin connects this: ${sourceKind ? `${labelize(sourceKind)} ` : ""}${edge.source || "source"} ${edge.relation || "relates to"} ${targetKind ? `${labelize(targetKind)} ` : ""}${edge.target || "target"}.`}
      </p>
      <EvidenceList evidence={evidence} compact={compact} />
    </article>
  );
}

