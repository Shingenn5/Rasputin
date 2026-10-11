import { formatGenerationMetrics } from "../../lib/generationMetrics.js";

import { Pause, Play, Square } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { displayModelName, displayWorkspaceName, labelize } from "../../lib/display.js";

import { Avatar } from "../../components/Avatar.jsx";

import { CodeSandbox } from "../../components/CodeSandbox.jsx";

export function TaskThread({ task, models, cancelTask, pauseTask, resumeTask, openTaskDetails }) {
  const status = task.status || "queued";
  const deploymentProfile = task.deploymentProfile || task.deployment_profile || {};
  const taskModel = displayModelName(task.model || deploymentProfile.key, models);
  const taskMode = task.mode || "chat";
  const taskWorkspace = displayWorkspaceName(task.workspace);
  const taskRuntime = deploymentProfile.runtime || deploymentProfile.provider || "unknown";
  const taskRuntimeIdentity = "Model " + taskModel + " · Mode " + taskMode + " · Workspace " + taskWorkspace + " · Runtime " + taskRuntime;
  const active = ["queued", "running", "paused"].includes(status);
  const runningPhase = [...(task.steps || [])].reverse().find((step) => step.kind === "phase" && step.status === "running")?.name;
  // Planning/execution streams remain available in task details; the chat
  // bubble presents only a direct chat reply or the final reflection so it
  // never flashes internal intermediate drafts as if they were the answer.
  const presentsAnswer = task.mode === "chat" || runningPhase === "chat" || runningPhase === "reflection";
  const liveText = presentsAnswer ? String(task.streamText || "") : "";
  const streaming = status === "running" && Boolean(liveText);
  const response = task.result || liveText || task.logs?.slice(-4).join("\n") || "Working...";
  const generation = formatGenerationMetrics(task.generationMetrics);
  return (
    <article className="thread-item">
      <div className="message user-message">
        <div className="message-label">
          <Avatar kind="user" name="You" size="sm" />
          <span>You</span>
        </div>
        <div className="message-body user-bubble">{task.objective}</div>
      </div>
      <div className="message assistant-message">
        <div className="message-label assistant-label">
          <Avatar kind="model" name={displayModelName(task.model, models) || "Rasputin"} size="sm" />
          <span>Rasputin</span>
          <span className={`status-pill status-${status}`}>{status}</span>
          {active && (
            <span className="status-pill status-running">
              {streaming ? "Generating…" : status === "queued" ? "Queued" : status === "paused" ? "Paused" : runningPhase === "chat" ? "Waiting for first token…" : "Working…"}
            </span>
          )}
          <span className="task-runtime-identity" data-testid="task-runtime-identity" title={taskRuntimeIdentity}>
            {taskRuntimeIdentity}
          </span>
        </div>
        <div
          className={`markdown-body${streaming ? " is-streaming" : ""}`}
          data-testid="chat-assistant-response"
          data-streaming={streaming ? "true" : "false"}
        >
          <ReactMarkdown
            rehypePlugins={[rehypeSanitize]}
            components={{
              code: CodeSandbox
            }}
          >
            {response}
          </ReactMarkdown>
        </div>
        <details className="runtime-details" data-testid="runtime-details-toggle">
          <summary>Details</summary>
          <dl className="detail-grid">
            <dt>Model</dt><dd>{displayModelName(task.model, models)}</dd>
            <dt>Mode</dt><dd>{task.mode || "chat"}</dd>
            <dt>Memory</dt><dd>{labelize(task.memoryMode || "auto")}</dd>
            {task.reasoning && task.reasoning !== "auto" && (
              <>
                <dt>Reasoning</dt><dd>{labelize(task.reasoning)}</dd>
              </>
            )}
            <dt>Workspace</dt><dd>{displayWorkspaceName(task.workspace)}</dd>
            <dt>Status</dt><dd>{status}</dd>
            <dt>Request throughput (all calls)</dt>
            <dd data-testid="message-generation-tps">{generation.tokensPerSecond}</dd>
            <dt>Generation speed (last call)</dt>
            <dd data-testid="message-decode-tps">{generation.decodeSpeed}</dd>
            <dt>First visible token (last call)</dt>
            <dd data-testid="message-first-token">{generation.firstToken}</dd>
            <dt>Prompt processing (last call)</dt><dd>{generation.promptTime}</dd>
            <dt>Request time (last call)</dt><dd>{generation.requestTime}</dd>
            <dt>Output tokens</dt>
            <dd>{generation.outputTokens}</dd>
          </dl>
          <div className="task-inline-actions" aria-label="Task details">
            <button type="button" className="tiny-action" data-testid="activity-task-details" onClick={() => openTaskDetails(task.id)}>
              Open details
            </button>
          </div>
          {active && (
            <div className="task-inline-actions" aria-label="Task controls">
              {status === "paused" ? (
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
        </details>
      </div>
    </article>
  );
}
