import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, postJson } from "../../api/client.js";
import { Button } from "../../components/ui/button.jsx";
import { displayWorkspaceName } from "../../lib/display.js";
import { formatRuntimeTime } from "./RuntimePrimitives.jsx";
import "./sandbox-review.css";

export function SandboxApprovalReview({ approval, approveApproval, denyApproval }) {
  const [expanded, setExpanded] = useState(false);
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState("");
  const [selected, setSelected] = useState("");
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const reading = useRef(false);
  const fileVersion = useRef(0);
  const alive = useRef(true);
  const endpoint = `/api/execution/approvals/${encodeURIComponent(approval.id)}`;

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; fileVersion.current += 1; };
  }, []);

  const refresh = useCallback(async () => {
    if (reading.current) return null;
    reading.current = true;
    if (alive.current) setLoading(true);
    try {
      const data = await api(endpoint);
      if (alive.current) { setReview(data); setLoadError(""); }
      return data;
    } catch (error) {
      if (alive.current) setLoadError(error.message);
      return null;
    } finally {
      reading.current = false;
      if (alive.current) setLoading(false);
    }
  }, [endpoint]);

  const terminal = ["finished", "cancelled", "interrupted"].includes(review?.state)
    || ["denied", "expired"].includes(review?.approvalStatus);
  useEffect(() => {
    if (!expanded) return;
    refresh();
    if (terminal) return;
    const timer = setInterval(refresh, 1500);
    return () => clearInterval(timer);
  }, [expanded, terminal, refresh]);

  async function inspect(path) {
    const version = ++fileVersion.current;
    setSelected(path); setFile(null); setFileError("");
    try {
      const data = await api(`${endpoint}/file?${new URLSearchParams({ path })}`);
      if (alive.current && version === fileVersion.current) setFile(data);
    } catch (error) {
      if (alive.current && version === fileVersion.current) setFileError(error.message);
    }
  }

  async function run() {
    setBusy("run"); setActionError("");
    try {
      await postJson(`/api/execution/requests/${encodeURIComponent(review.plan.requestId)}/execute`, {});
    } catch (error) { setActionError(error.message); }
    finally { setBusy(""); await refresh(); }
  }

  async function approve() {
    setBusy("approve"); setActionError("");
    try {
      await approveApproval(approval.id);
      if (review.canRunManually) {
        await run();
      } else {
        await refresh();
      }
    } catch (error) { setActionError(error.message); }
    finally { setBusy(""); }
  }

  async function deny() {
    setBusy("deny"); setActionError("");
    try { await denyApproval(approval.id); await refresh(); }
    catch (error) { setActionError(error.message); }
    finally { setBusy(""); }
  }

  async function stop() {
    setActionError("");
    try {
      await postJson(`/api/execution/requests/${encodeURIComponent(review.plan.requestId)}/cancel`, {});
      await refresh();
    } catch (error) { setActionError(error.message); }
  }

  const plan = review?.plan;
  const receipt = review?.receipt;
  const pending = review?.approvalStatus === "pending" && review?.state === "pending_approval";
  const running = review?.state === "running" || busy === "run";
  const status = receipt
    ? receipt.ran === false ? "Did not run" : receipt.ran == null ? "Execution not confirmed" : receipt.passed ? "Passed" : "Did not pass"
    : running ? "Running" : review?.approvalStatus === "approved" ? "Approved; waiting to run"
      : ({ pending: "Waiting for approval", denied: "Denied", expired: "Expired" }[review?.approvalStatus] || review?.approvalStatus || "");

  return (
    <div className="sandbox-review" data-testid="sandbox-review">
      <Button type="button" variant="outline" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
        {expanded ? "Hide snapshot review" : "Review snapshot"}
      </Button>
      {expanded && (
        <div className="sandbox-review-content">
          <div className="sandbox-review-heading">
            <h3>Sandbox execution</h3>
            <Button type="button" variant="ghost" size="sm" disabled={loading} onClick={refresh}>Refresh execution</Button>
          </div>
          {(loadError || actionError) && <p role="alert" className="sandbox-review-error">{loadError || actionError}</p>}
          {!review && loading && <p role="status">Loading the captured request…</p>}
          {plan && <>
            <p>Runs a copied snapshot. File changes stay in the sandbox. Network access is disabled.</p>
            <dl className="sandbox-review-facts">
              <dt>Workspace</dt><dd>{displayWorkspaceName(plan.workspace)}</dd>
              <dt>Requested by</dt><dd>{review.ownerId}</dd>
              <dt>Runtime</dt><dd>{plan.toolchain.name}</dd>
              <dt>Time limit</dt><dd>{plan.timeout} seconds</dd>
            </dl>
            <h4>Exact arguments</h4>
            <p className="sandbox-review-note">Each row shows one argument as a quoted string; escapes preserve tabs and line breaks.</p>
            <ol className="sandbox-review-arguments" aria-label="Exact runtime arguments">
              {plan.arguments.map((argument, index) => <li key={index}><code>{JSON.stringify(argument)}</code></li>)}
            </ol>
            <h4>Captured files ({plan.files.length})</h4>
            <p className="sandbox-review-note">Inspect the captured version; later workspace edits are not part of this request.</p>
            <ul className="sandbox-review-files" aria-label="Captured files">
              {plan.files.map((item) => <li key={item.path}>
                <button type="button" className="sandbox-review-file" aria-pressed={selected === item.path} onClick={() => inspect(item.path)}>
                  <span>{item.path}</span><span>{item.bytes.toLocaleString()} bytes</span>
                </button>
              </li>)}
            </ul>
            {selected && <section aria-label={`Captured file: ${selected}`}>
              <h4>{selected}</h4>
              {fileError ? <p role="alert" className="sandbox-review-error">{fileError}</p>
                : !file ? <p role="status">Loading captured file…</p>
                  : file.binary ? <p>Binary file · {file.bytes.toLocaleString()} bytes. Text preview is unavailable.</p>
                    : <><pre className="sandbox-review-output" tabIndex={0}>{file.text || "(empty file)"}</pre>
                      {file.truncated && <p>Preview shows the first 32,768 characters. The full file remains in the captured snapshot.</p>}</>}
            </section>}
            <details className="sandbox-review-identities">
              <summary>Snapshot and runtime identities</summary>
              <dl className="sandbox-review-facts">
                <dt>Request</dt><dd><code>{plan.requestId}</code></dd>
                <dt>Snapshot SHA-256</dt><dd><code>{plan.snapshotSha256}</code></dd>
                <dt>Runtime SHA-256</dt><dd><code>{plan.toolchain.sha256}</code></dd>
              </dl>
            </details>
            <div className="sandbox-review-actions">
              {pending && <>
                <Button type="button" disabled={!!busy || !!loadError || !!fileError} onClick={approve}>
                  {busy === "approve" ? "Approving…" : review.canRunManually ? "Approve and run snapshot" : "Approve snapshot"}
                </Button>
                <Button type="button" variant="outline" disabled={!!busy} onClick={deny}>Deny snapshot</Button>
              </>}
              {review.approvalStatus === "approved" && review.state === "pending_approval" && review.canRunManually && (
                <Button type="button" disabled={!!busy || !!loadError} onClick={run}>Run approved snapshot</Button>
              )}
              {running && review.outputAccess && <Button type="button" variant="destructive" onClick={stop}>Stop execution</Button>}
            </div>
            <p role="status" className="sandbox-review-status">{status}</p>
            {review.approvalStatus === "approved" && !receipt && !running && !review.canRunManually && (
              <p>{plan.taskId ? "The task can now run this snapshot." : "The request owner can now run this snapshot."}</p>
            )}
            {receipt && <section aria-label="Execution result">
              <dl className="sandbox-review-facts">
                <dt>Termination</dt><dd>{receipt.terminationReason?.replaceAll("_", " ") || "Unknown"}</dd>
                {receipt.exitCode != null && <><dt>Exit code</dt><dd>{receipt.exitCode}</dd></>}
                <dt>Finished</dt><dd>{formatRuntimeTime(receipt.finishedAt)}</dd>
              </dl>
              {receipt.ran === true && receipt.evidenceComplete === false && <p>File evidence is incomplete; this run cannot count as passed.</p>}
              {review.outputAccess && receipt.output != null && <details open>
                <summary>Execution output</summary>
                <pre className="sandbox-review-output" tabIndex={0}>{receipt.output || "(no output)"}</pre>
                {receipt.truncated && <p>Output reached its limit and was truncated.</p>}
              </details>}
              {!review.outputAccess && <p>Execution output is private to the request owner.</p>}
              {receipt.changes?.length > 0 && <details>
                <summary>Changed files ({receipt.changes.length})</summary>
                <ul>{receipt.changes.map((change) => <li key={change.path}>{change.path}</li>)}</ul>
              </details>}
            </section>}
          </>}
        </div>
      )}
    </div>
  );
}
