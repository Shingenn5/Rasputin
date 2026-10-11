import React, { useState } from "react";
import { Star, Trophy } from "lucide-react";
import { postJson } from "../../api/client.js";
import { statusColor, fmtDate, ScorecardMeasurements } from "./trialPresentation.jsx";

export function InspectorPanel({ selected, scorecards, experiments, refresh, setError }) {
  const [generatingScorecard, setGeneratingScorecard] = useState(false);
  const revealedModels = [...new Set((selected?.runs || []).flatMap(run => (run.outputs || []).map(output => output.modelKey)).filter(Boolean))];

  async function handleGenerateScorecard() {
    if (!selected?.id) return;
    setGeneratingScorecard(true);
    try {
      await postJson("/api/trials/scorecards", { experimentId: selected.id });
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingScorecard(false);
    }
  }

  async function handlePromoteCertificate(modelKey) {
    setGeneratingScorecard(true);
    try {
      await postJson(`/api/trials/blind-comparisons/${selected.id}/certificate`, {
        modelKey,
        mission: selected.config?.mission || "",
      });
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setGeneratingScorecard(false);
    }
  }

  // Find scorecard for selected experiment
  const relatedScorecard = scorecards.find(sc => sc.subjectId === selected?.id);

  return (
    <>
      <div className="w2-card" style={{ flex: 1 }}>
        <h3 style={{ margin: "0 0 8px 0", fontSize: "0.875rem" }}>Inspector</h3>
        {selected ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px" }}>
              <h4 style={{ margin: "0 0 8px 0", fontSize: "1rem" }}>{selected.name}</h4>
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "6px 12px", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--cc-muted)" }}>ID</span>
                <span style={{ fontFamily: "monospace", fontSize: "0.6875rem" }}>{selected.id}</span>
                {selected.type && <>
                  <span style={{ color: "var(--cc-muted)" }}>Type</span>
                  <span style={{ textTransform: "capitalize" }}>{selected.type}</span>
                </>}
                {selected.status && <>
                  <span style={{ color: "var(--cc-muted)" }}>Status</span>
                  <span style={{ color: statusColor(selected.status), textTransform: "capitalize" }}>{selected.status}</span>
                </>}
                {selected.createdAt && <>
                  <span style={{ color: "var(--cc-muted)" }}>Created</span>
                  <span>{fmtDate(selected.createdAt)}</span>
                </>}
                {selected.entries && <>
                  <span style={{ color: "var(--cc-muted)" }}>Entries</span>
                  <span>{selected.entries.length}</span>
                </>}
              </div>
            </div>

            {/* Tags */}
            {(selected.tags || []).length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                {selected.tags.map(tag => (
                  <span key={tag} style={{ fontSize: "0.6875rem", padding: "1px 8px", borderRadius: "999px", background: "var(--cc-surface)", border: "1px solid var(--cc-border)" }}>{tag}</span>
                ))}
              </div>
            )}

            {/* Metrics */}
            {selected.metrics && Object.keys(selected.metrics).length > 0 && (
              <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px" }}>
                <strong style={{ fontSize: "0.75rem", color: "var(--cc-muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>Metrics</strong>
                <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: "0.75rem", marginTop: "8px" }}>
                  {Object.entries(selected.metrics).filter(([k]) => k !== "results" && k !== "error").map(([k, v]) => (
                    <React.Fragment key={k}>
                      <span style={{ color: "var(--cc-muted)" }}>{k}</span>
                      <span>{typeof v === "number" ? v.toLocaleString() : String(v)}</span>
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            {/* Report content preview */}
            {selected.contentMd && (
              <div style={{ background: "var(--cc-bg)", padding: "12px", borderRadius: "6px", maxHeight: "400px", overflow: "auto" }}>
                <strong style={{ fontSize: "0.75rem", color: "var(--cc-muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>Report Preview</strong>
                <pre style={{ fontSize: "0.75rem", whiteSpace: "pre-wrap", marginTop: "8px", fontFamily: "inherit" }}>
                  {selected.contentMd}
                </pre>
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "auto" }}>
              {selected.status === "completed" && (
                selected.type === "blind_compare" && selected.config?.revealed ? (
                  revealedModels.map(modelKey => (
                    <button key={modelKey} className="w2-button primary" type="button" onClick={() => handlePromoteCertificate(modelKey)} disabled={generatingScorecard}>
                      <Star size={14} /> Certify {modelKey}
                    </button>
                  ))
                ) : selected.type !== "blind_compare" && (
                <button className="w2-button primary" type="button" onClick={handleGenerateScorecard} disabled={generatingScorecard}>
                  <Star size={14} /> {generatingScorecard ? "Generating..." : "Generate Scorecard"}
                </button>
                )
              )}
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--cc-muted)", fontSize: "0.875rem", textAlign: "center", marginTop: "32px" }}>
            Select an item to inspect.
          </div>
        )}
      </div>

      {/* Scorecard display */}
      {relatedScorecard && (
        <div className="w2-card">
          <h3 style={{ margin: "0 0 8px 0", fontSize: "0.875rem" }}><Trophy size={14} style={{ verticalAlign: "-2px", marginRight: "4px" }} />Scorecard</h3>
          {relatedScorecard.subjectType === "fitness_certificate" ? (
            <div style={{ fontSize: "0.75rem" }}>
              <strong>{relatedScorecard.scores?.modelKey}</strong> · {relatedScorecard.scores?.mission}
              <p>{relatedScorecard.scores?.measured?.sampleCount} measured samples · {Math.round((relatedScorecard.scores?.measured?.successRate || 0) * 100)}% successful · {relatedScorecard.scores?.measured?.avgLatencyMs} ms average latency</p>
              <p style={{ color: "var(--cc-muted)" }}>{relatedScorecard.scores?.limitations?.[0]}</p>
            </div>
          ) : <>
          <ScorecardMeasurements scorecard={relatedScorecard} />
          </>}
        </div>
      )}
    </>
  );
}
