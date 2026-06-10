import React, { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RefreshCw, Square, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { displayModelName, displayWorkspaceName } from "../../lib/display.js";
import { GraphEdgeCard } from "../knowledge/GraphEvidence.jsx";

const sections = [
  ["overview", "Overview"],
  ["seen", "What Rasputin Saw"],
  ["trace", "Plan And Trace"],
  ["logs", "Logs"],
  ["outputs", "Outputs"],
  ["subagents", "Sub-Agents"],
  ["tools", "Tools"],
  ["approvals", "Approvals"],
];

export function TaskDetailsDrawer({
  taskId,
  detail,
  loading,
  error,
  models,
  closeTaskDetails,
  refreshTaskDetails,
  cancelTask,
  pauseTask,
  resumeTask,
  openTaskDetails,
  approveApproval,
  denyApproval,
  returnFocusRef,
}) {
  const [section, setSection] = useState("overview");
  const drawerRef = useRef(null);
  const task = detail?.task;
  const active = ["queued", "running", "paused"].includes(task?.status);

  useEffect(() => {
    if (!taskId) return undefined;
    setSection("overview");
    window.setTimeout(() => drawerRef.current?.focus(), 0);
    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeTaskDetails();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [taskId, closeTaskDetails]);

  useEffect(() => {
    if (taskId) return undefined;
    const target = returnFocusRef?.current;
    if (target?.focus) window.setTimeout(() => target.focus(), 0);
    return undefined;
  }, [taskId, returnFocusRef]);

  const logs = useMemo(() => {
    const taskLogs = task?.logs || [];
    const eventLogs = (detail?.events || [])
      .filter((event) => event.kind === "log")
      .map((event) => event.detail?.message)
      .filter(Boolean);
    return taskLogs.length ? taskLogs : eventLogs;
  }, [detail, task]);
  const contextBudgets = useMemo(
    () => (detail?.trace || []).filter((item) => item.kind === "context_budget"),
    [detail],
  );

  if (!taskId) return null;

  return (
    <div className="task-drawer-layer" role="presentation">
      <button className="task-drawer-backdrop" type="button" aria-label="Close task details" onClick={closeTaskDetails} />
      <aside
        ref={drawerRef}
        className="task-details-drawer"
        data-testid="task-details-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="taskDetailsTitle"
        tabIndex="-1"
      >
        <header className="task-details-header">
          <div>
            <span className="eyebrow">Task Inspector</span>
            <h1 id="taskDetailsTitle">{task?.objective || "Task details"}</h1>
            {task && (
              <p>
                {displayWorkspaceName(task.workspace)} / {displayModelName(task.model, models)} / {task.mode || "chat"}
              </p>
            )}
          </div>
          <div className="task-details-actions">
            <button className="icon-button" type="button" aria-label="Refresh task details" onClick={() => refreshTaskDetails(taskId)}>
              <RefreshCw size={17} />
            </button>
            <button className="icon-button" type="button" data-testid="task-details-close" aria-label="Close task details" onClick={closeTaskDetails}>
              <X size={18} />
            </button>
          </div>
        </header>

        {error && <p className="drawer-error" role="alert">{error}</p>}
        {loading && <p className="drawer-loading" role="status">Loading task details...</p>}

        {task && (
          <>
            <nav className="task-details-tabs" role="tablist" aria-label="Task detail sections">
              {sections.map(([id, label]) => (
                <button
                  key={id}
                  id={`task-detail-tab-${id}`}
                  type="button"
                  className={section === id ? "task-detail-tab is-active" : "task-detail-tab"}
                  role="tab"
                  aria-selected={section === id}
                  aria-controls={`task-detail-panel-${id}`}
                  tabIndex={section === id ? 0 : -1}
                  onClick={() => setSection(id)}
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="task-details-body">
              {section === "overview" && (
                <section id="task-detail-panel-overview" role="tabpanel" aria-labelledby="task-detail-tab-overview" data-testid="task-details-overview">
                  <div className="task-detail-grid">
                    <Metric label="Status" value={task.status || "queued"} tone={task.status} />
                    <Metric label="Progress" value={`${Number(task.progress || 0)}%`} />
                    <Metric label="Workspace" value={displayWorkspaceName(task.workspace)} />
                    <Metric label="Model" value={displayModelName(task.model, models)} />
                    <Metric label="Mode" value={task.mode || "chat"} />
                    <Metric label="Session" value={task.sessionId || detail?.session?.id || "Unknown"} />
                    <Metric label="Created" value={formatTime(task.createdAt)} />
                    <Metric label="Task ID" value={task.id} />
                  </div>
                  {active && (
                    <div className="drawer-control-row" aria-label="Task controls">
                      {task.status === "paused" ? (
                        <button type="button" className="tiny-action" onClick={() => resumeTask(task.id)}>
                          <Play size={13} />
                          Resume
                        </button>
                      ) : (
                        <button type="button" className="tiny-action" onClick={() => pauseTask(task.id)}>
                          <Pause size={13} />
                          Pause
                        </button>
                      )}
                      <button type="button" className="tiny-action danger" onClick={() => cancelTask(task.id)}>
                        <Square size={13} />
                        Stop
                      </button>
                    </div>
                  )}
                  <article className="drawer-result-block">
                    <h2>Result</h2>
                    <div className="markdown-body">
                      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{task.result || "No final result yet."}</ReactMarkdown>
                    </div>
                  </article>
                </section>
              )}

              {section === "seen" && (
                <section id="task-detail-panel-seen" role="tabpanel" aria-labelledby="task-detail-tab-seen" data-testid="task-details-seen">
                  <div className="context-stack">
                    <ContextBudgetPanel budgets={contextBudgets} />
                    <ContextBlock title="Local RAG Sources" empty="No local RAG sources were attached to this snapshot.">
                      {(task.sources || []).map((source, index) => (
                        <li key={`${source.source}-${source.chunk}-${index}`}>
                          <strong>{source.source}</strong>
                          <span>chunk {source.chunk} / score {source.score}</span>
                        </li>
                      ))}
                    </ContextBlock>
                    <article className="context-block task-graph-context" data-testid="task-graph-evidence">
                      <h2>Graphify Relationships</h2>
                      {(task.graph || []).length ? (
                        <div className="graph-evidence-stack">
                          {(task.graph || []).map((edge, index) => (
                            <GraphEdgeCard edge={edge} compact key={`${edge.source}-${edge.target}-${index}`} />
                          ))}
                        </div>
                      ) : (
                        <p className="empty-inline">No graph relationships were attached to this snapshot.</p>
                      )}
                    </article>
                    <ContextBlock title="Memory And Context Trace" empty="No context trace was recorded yet.">
                      {(detail.trace || [])
                        .filter((item) => ["memory_recall", "rag_context", "graph_context", "tool_plan"].includes(item.kind))
                        .map((item, index) => (
                          <li key={`${item.kind}-${index}`}>
                            <strong>{labelize(item.kind)}</strong>
                            <span>{summarizeDetail(item.detail)}</span>
                          </li>
                        ))}
                    </ContextBlock>
                  </div>
                </section>
              )}

              {section === "trace" && (
                <section id="task-detail-panel-trace" role="tabpanel" aria-labelledby="task-detail-tab-trace" data-testid="task-details-trace">
                  <Timeline items={detail.trace || []} empty="No agent trace entries recorded yet." />
                </section>
              )}

              {section === "logs" && (
                <section id="task-detail-panel-logs" role="tabpanel" aria-labelledby="task-detail-tab-logs" data-testid="task-details-logs">
                  <pre className="log-box">{logs.length ? logs.join("\n") : "No task logs yet."}</pre>
                </section>
              )}

              {section === "outputs" && (
                <section id="task-detail-panel-outputs" role="tabpanel" aria-labelledby="task-detail-tab-outputs" data-testid="task-details-outputs">
                  <div className="output-stack">
                    {(detail.outputs || task.outputs || []).map((output, index) => (
                      <article className="output-card" key={output.id || `${output.title}-${index}`}>
                        <div className="section-row">
                          <div>
                            <span className="eyebrow">{output.kind || "output"}</span>
                            <h2>{output.title || "Task output"}</h2>
                          </div>
                          <span className="status-pill">{formatTime(output.createdAt)}</span>
                        </div>
                        <div className="markdown-body">
                          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{output.content || ""}</ReactMarkdown>
                        </div>
                      </article>
                    ))}
                    {!(detail.outputs || task.outputs || []).length && <EmptyInline text="No outputs have been written for this task." />}
                  </div>
                </section>
              )}

              {section === "subagents" && (
                <section id="task-detail-panel-subagents" role="tabpanel" aria-labelledby="task-detail-tab-subagents" data-testid="task-details-subagents">
                  <div className="subagent-stack">
                    {(detail.children || []).map((child) => (
                      <button className="subagent-card" type="button" key={child.id} onClick={() => openTaskDetails(child.id)}>
                        <span className={`status-pill status-${child.status}`}>{child.status}</span>
                        <strong>{child.objective}</strong>
                        <small>{displayModelName(child.model, models)} / {Number(child.progress || 0)}%</small>
                      </button>
                    ))}
                    {!(detail.children || []).length && <EmptyInline text="No sub-agents were spawned for this task." />}
                  </div>
                </section>
              )}

              {section === "tools" && (
                <section id="task-detail-panel-tools" role="tabpanel" aria-labelledby="task-detail-tab-tools" data-testid="task-details-tools">
                  <div className="approval-tool-stack">
                    {(detail.toolCalls || []).map((tool) => <ToolCallSummary key={tool.id} tool={tool} />)}
                    {!(detail.toolCalls || []).length && <EmptyInline text="No tool calls were recorded for this task." />}
                  </div>
                </section>
              )}

              {section === "approvals" && (
                <section id="task-detail-panel-approvals" role="tabpanel" aria-labelledby="task-detail-tab-approvals" data-testid="task-details-approvals">
                  <div className="approval-tool-stack">
                    {(detail.approvals || []).map((approval) => (
                      <ApprovalSummary
                        key={approval.id}
                        approval={approval}
                        approveApproval={approveApproval}
                        denyApproval={denyApproval}
                      />
                    ))}
                    {!(detail.approvals || []).length && <EmptyInline text="No approvals were recorded for this task." />}
                  </div>
                </section>
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function ToolCallSummary({ tool }) {
  return (
    <article className="tool-call-card">
      <div className="section-row">
        <div>
          <span className={`status-pill status-${tool.status}`}>{tool.status}</span>
          <h2>{labelize(tool.name)}</h2>
        </div>
        <span className={`status-pill risk-${tool.risk}`}>{labelize(tool.risk)}</span>
      </div>
      <dl className="detail-grid">
        <dt>Approval</dt><dd>{tool.approvalId || "Not required"}</dd>
        <dt>Args</dt><dd>{summarizeDetail(tool.argsRedacted || {})}</dd>
        <dt>Result</dt><dd>{summarizeDetail(tool.resultRedacted || {})}</dd>
        <dt>Updated</dt><dd>{formatTime(tool.updatedAt || tool.updated_at)}</dd>
      </dl>
    </article>
  );
}

function Metric({ label, value, tone }) {
  return (
    <article className="task-detail-metric">
      <span>{label}</span>
      <strong className={tone ? `status-${tone}` : ""}>{value || "None"}</strong>
    </article>
  );
}

function ContextBlock({ title, empty, children }) {
  const list = React.Children.toArray(children).filter(Boolean);
  return (
    <article className="context-block">
      <h2>{title}</h2>
      {list.length ? <ul>{list}</ul> : <EmptyInline text={empty} />}
    </article>
  );
}

function ContextBudgetPanel({ budgets }) {
  if (!budgets.length) {
    return (
      <article className="context-block" data-testid="task-context-budget">
        <h2>Context Budget</h2>
        <EmptyInline text="No context budget trace has been recorded yet." />
      </article>
    );
  }
  const latest = budgets[budgets.length - 1]?.detail || {};
  const sections = latest.sections || [];
  const trimmed = latest.trimmed || [];
  const omitted = latest.omitted || [];
  return (
    <article className="context-block context-budget-card" data-testid="task-context-budget">
      <div className="section-row">
        <div>
          <h2>Context Budget</h2>
          <p>{labelize(latest.phase)} / {latest.modelKey || "model unknown"}</p>
        </div>
        <span className="status-pill">
          {Number(latest.estimatedInputTokens || 0).toLocaleString()} / {Number(latest.inputBudgetTokens || 0).toLocaleString()} input tokens
        </span>
      </div>
      <dl className="detail-grid">
        <dt>Context Window</dt><dd>{Number(latest.contextWindow || 0).toLocaleString()}</dd>
        <dt>Max Output</dt><dd>{Number(latest.maxTokens || 0).toLocaleString()}</dd>
        <dt>Trimmed</dt><dd>{trimmed.length ? trimmed.map(labelize).join(", ") : "None"}</dd>
        <dt>Omitted</dt><dd>{omitted.length ? omitted.map(labelize).join(", ") : "None"}</dd>
      </dl>
      {!!sections.length && (
        <ul className="context-budget-sections" aria-label="Context section status">
          {sections.map((item) => (
            <li key={`${item.key}-${item.status}`}>
              <strong>{item.title || labelize(item.key)}</strong>
              <span>{labelize(item.status)} / {Number(item.estimatedTokens || 0).toLocaleString()} tokens</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Timeline({ items, empty }) {
  if (!items.length) return <EmptyInline text={empty} />;
  return (
    <ol className="trace-timeline">
      {items.map((item, index) => (
        <li key={`${item.kind}-${item.createdAt}-${index}`}>
          <span>{formatTime(item.createdAt)}</span>
          <strong>{labelize(item.kind)}</strong>
          <p>{summarizeDetail(item.detail)}</p>
        </li>
      ))}
    </ol>
  );
}

function ApprovalSummary({ approval, approveApproval, denyApproval }) {
  const actionType = approval.actionType || approval.action_type || "approval";
  return (
    <article className="approval-card detail-approval-card" data-testid="approval-card">
      <div className="section-row">
        <div>
          <span className={`status-pill status-${approval.status}`}>{approval.status}</span>
          <h2>{approval.summary || labelize(actionType)}</h2>
          <p>
            Code {approval.code} / {labelize(actionType)} / {displayWorkspaceName(approval.workspace)}
          </p>
        </div>
        {approval.status === "pending" && (
          <div className="task-card-actions">
            <button className="tiny-action" type="button" onClick={() => approveApproval(approval.id)}>Approve</button>
            <button className="tiny-action danger" type="button" onClick={() => denyApproval(approval.id)}>Deny</button>
          </div>
        )}
      </div>
      <dl className="detail-grid">
        <dt>Risk</dt><dd>{approval.riskLevel || approval.risk_level || "approval required"}</dd>
        <dt>Expires</dt><dd>{formatTime(approval.expiresAt || approval.expires_at)}</dd>
        <dt>Details</dt><dd>{summarizeDetail(approval.redactedDetail || approval.redacted_detail || {})}</dd>
      </dl>
    </article>
  );
}

function EmptyInline({ text }) {
  return <p className="empty-inline">{text}</p>;
}

function formatTime(value) {
  if (!value) return "Unknown";
  const numeric = Number(value);
  const date = new Date(numeric > 10_000_000_000 ? numeric : numeric * 1000);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function labelize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
    || "Unknown";
}

function summarizeDetail(value) {
  if (value == null) return "None";
  if (typeof value === "string") return value || "None";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "Recorded detail";
  }
}
