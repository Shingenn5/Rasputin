import React, { useEffect, useMemo, useRef, useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, Row, Stack } from "react-bootstrap";
import { ArrowRight, Bot, CheckCircle2, Clock3, Code2, Link2, MessageSquare, Mic, RefreshCw, ShieldCheck, Volume2, XCircle } from "lucide-react";

function titleize(value) {
  return String(value || "").replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function workflowLabel(session) {
  return session?.mode === "code" ? "Coding" : "Assistant";
}

function statusVariant(status) {
  if (["approved", "prepared", "ready_for_broker", "approved_for_broker", "ready", "completed"].includes(status)) return "success";
  if (["rejected", "denied", "blocked", "expired", "missing", "failed"].includes(status)) return "danger";
  if (["pending_approval", "awaiting_approval", "review_required", "needs_health_check"].includes(status)) return "warning";
  return "secondary";
}

function SectionHeader({ title, text, action }) {
  return (
    <div className="section-row mb-3">
      <div>
        <h2 className="h5 mb-1">{title}</h2>
        {text && <p className="text-body-secondary mb-0 small">{text}</p>}
      </div>
      {action}
    </div>
  );
}

function VoiceConsole() {
  const MAX_RECORDING_MS = 60 * 1000;
  const [state, setState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [responseText, setResponseText] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const stopTimerRef = useRef(null);

  useEffect(() => () => {
    if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [audioUrl]);

  const finishTurn = async (blob) => {
    setState("processing");
    setError("");
    try {
      const turnResponse = await fetch("/api/assistant/voice/turn", {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "audio/webm",
          "X-Filename": blob.type.includes("wav") ? "rasputin-recording.wav" : "rasputin-recording.webm",
        },
        body: blob,
      });
      const payload = await turnResponse.json().catch(() => ({}));
      if (!turnResponse.ok || payload.ok === false) {
        throw new Error(payload.error?.message || `Voice turn failed (${turnResponse.status}).`);
      }
      const data = payload.data || {};
      if (!data.transcript || !data.response || !data.audioBase64) throw new Error("The local voice turn returned incomplete conversation evidence.");
      setTranscript(data.transcript);
      setResponseText(data.response);
      const rawAudio = atob(data.audioBase64);
      const audioBytes = Uint8Array.from(rawAudio, (character) => character.charCodeAt(0));
      const nextUrl = URL.createObjectURL(new Blob([audioBytes], { type: data.contentType || "audio/wav" }));
      setAudioUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return nextUrl;
      });
      setState("ready");
    } catch (turnError) {
      setState("error");
      setError(String(turnError.message || turnError));
    }
  };

  const startRecording = async () => {
    setError("");
    setTranscript("");
    setResponseText("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setState("error");
      setError("This browser does not expose a microphone recorder. Use a modern browser on localhost.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
        stopTimerRef.current = null;
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (!blob.size) {
          setState("error");
          setError("The microphone returned no audio.");
          return;
        }
        finishTurn(blob);
      };
      recorder.start();
      stopTimerRef.current = setTimeout(() => {
        if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      }, MAX_RECORDING_MS);
      setState("recording");
    } catch (recordError) {
      streamRef.current?.getTracks?.().forEach((track) => track.stop());
      streamRef.current = null;
      setState("error");
      setError(recordError?.name === "NotAllowedError" ? "Microphone permission was not granted." : String(recordError.message || recordError));
    }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") {
      if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
      recorderRef.current.stop();
      setState("stopped");
    }
  };

  const active = state === "recording";
  const busy = ["stopped", "processing"].includes(state);
  return (
    <div className="border-top mt-3 pt-3" data-testid="assistant-voice-console">
      <SectionHeader title="Push-to-talk conversation" text="Microphone access starts only after you press the button. Local speech-to-text, Rasputin, and text-to-speech complete one bounded turn; host actions never start here." />
      <div className="d-flex flex-wrap align-items-center gap-2">
        <Button
          type="button"
          variant={active ? "danger" : "outline-primary"}
          onClick={active ? stopRecording : startRecording}
          disabled={busy}
          aria-pressed={active}
          aria-label={active ? "Stop recording" : "Start push to talk"}
          data-testid="assistant-voice-toggle"
        >
          <Mic size={14} className="me-1" aria-hidden="true" />{active ? "Stop recording" : "Start push to talk"}
        </Button>
        <Badge bg={state === "ready" ? "success" : state === "error" ? "danger" : "secondary"}>{titleize(state)}</Badge>
        {state === "recording" && <span className="small text-body-secondary">Recording locally until you stop.</span>}
        {state === "processing" && <span className="small text-body-secondary">Local voice turn in progress.</span>}
      </div>
      {error && <Alert variant="danger" className="mt-2 mb-0" data-testid="assistant-voice-error">{error}</Alert>}
      {transcript && <div className="small mt-2" data-testid="assistant-voice-transcript"><strong>Transcript:</strong> {transcript}</div>}
      {responseText && <div className="small mt-2" data-testid="assistant-voice-response"><strong>Rasputin:</strong> {responseText}</div>}
      {audioUrl && <audio className="w-100 mt-2" controls preload="metadata" src={audioUrl} data-testid="assistant-voice-audio">Your browser cannot play the local speech response.</audio>}
    </div>
  );
}

export function AssistantView({
  view,
  profile,
  capabilities,
  plans,
  contextCapsules = { capsules: [] },
  modelPacks,
  handoffs,
  tools = { tools: [], callableTools: [] },
  mcpRelays = { servers: [] },
  voicePreview,
  commandPreview,
  contextPreview,
  sessions = { sessions: [] },
  loading = false,
  error = "",
  refresh,
  createPlan,
  saveModelPack,
  reviewPlan,
  requestHandoff,
  prepareHandoff,
  dispatchHandoff,
  previewVoice,
  previewCommand,
  previewContext,
  saveProfile,
  createContextCapsule,
  reviewContextCapsule,
  openWorkflow,
}) {
  const controlOperations = capabilities?.controlOperations || {};
  const brokerOperationMetadata = useMemo(() => {
    const raw = capabilities?.broker?.dispatchOperationMetadata || [];
    return Array.isArray(raw) ? Object.fromEntries(raw.map((item) => [item.operation, item])) : raw;
  }, [capabilities]);
  const operationEntries = useMemo(() => {
    if (Array.isArray(controlOperations)) return controlOperations.map((item) => [item.operation, item]);
    return Object.entries(controlOperations).map(([key, definition]) => {
      const operation = definition.operation || key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
      return [operation, { ...definition, operation }];
    });
  }, [controlOperations]);
  const planItems = plans?.plans || [];
  const capsuleItems = contextCapsules?.capsules || [];
  const approvedCapsules = capsuleItems.filter((capsule) => capsule.status === "approved");
  const packItems = modelPacks?.packs || [];
  const handoffItems = handoffs?.handoffs || [];
  const voiceRoles = capabilities?.voiceRoles || [];
  const commandRouter = capabilities?.commandRouter || {};
  const voiceContract = capabilities?.voice || {};
  const voiceModelReadiness = capabilities?.voiceModels || capabilities?.voice_models || {};
  const voiceModelRoles = voiceModelReadiness.roles || {};
  const voiceModelStatus = voiceModelReadiness.status || "not_checked";
  const voiceModelRoleEntries = [
    ["speechToText", "Speech to text"],
    ["textToSpeech", "Text to speech"],
  ].map(([key, label]) => [key, label, voiceModelRoles[key] || voiceModelRoles[key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)] || {}]);
  const personaStyle = profile?.persona?.style || {};
  const toolItems = Array.isArray(tools?.tools) ? tools.tools : [];
  const callableToolItems = Array.isArray(tools?.callableTools)
    ? tools.callableTools
    : toolItems.filter((tool) => tool.callable !== false);
  const blockedToolCount = Math.max(0, toolItems.length - callableToolItems.length);
  const mcpServerItems = Array.isArray(mcpRelays?.servers) ? mcpRelays.servers : [];
  const runningMcpCount = mcpServerItems.filter((server) => server.status === "running" || server.health === "running").length;
  const commandOperations = Array.isArray(commandRouter.supportedOperations) ? commandRouter.supportedOperations : [];
  const commandReady = Boolean(commandRouter.previewEndpoint && commandRouter.executionMode === "preview_only");
  const voiceReady = Boolean(voiceContract.localOnly && voiceContract.transport);
  const mcpReady = Boolean(tools?.contract?.discoveryMode === "fail_closed" || tools?.contract?.discovery_mode === "fail_closed");
  const workflows = Array.isArray(capabilities?.workflows) ? capabilities.workflows : [];
  const sessionItems = (sessions?.sessions || []).slice(0, 30);
  const policy = profile?.localControlPolicy || {};
  const contextPolicy = profile?.contextAuthority || {};

  return (
    <section className={`app-view ${view === "assistant" ? "active" : ""}`} id="assistantView" data-app-view="assistant" data-testid="assistant-view">
      <div className="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-3">
        <div>
          <p className="text-uppercase small fw-semibold text-body-secondary mb-1">Personal assistant control plane</p>
          <h1 className="h3 mb-1">{profile?.displayName || "Rasputin"}</h1>
          <p className="text-body-secondary mb-0">{profile?.mission || "Coordinate local models and agents as one dependable workstation assistant."}</p>
        </div>
        <Button variant="outline-secondary" size="sm" onClick={refresh} disabled={loading} data-testid="assistant-refresh">
          <RefreshCw size={14} className={loading ? "spin me-1" : "me-1"} aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {error && <Alert variant="danger" role="alert">{error}</Alert>}

      <div className="task-dashboard assistant-dashboard">
        <Card className="settings-card shadow-sm mb-3" data-testid="assistant-workflow-launcher">
          <Card.Body>
            <SectionHeader
              title="Independent workspaces"
              text="Use the Assistant and Coding workflows separately. They share Rasputin's identity, context policy, and safety broker, but each opens its own task surface."
            />
            <Row className="g-3">
              {workflows.map((workflow) => {
                const isCoding = workflow.id === "coding";
                const Icon = isCoding ? Code2 : MessageSquare;
                return (
                  <Col md={6} key={workflow.id}>
                    <div className="border rounded p-3 h-100 d-flex flex-column gap-2" data-testid={`assistant-workflow-${workflow.id}`}>
                      <div className="d-flex align-items-start gap-2">
                        <div className="rounded-circle bg-primary-subtle text-primary p-2"><Icon size={18} aria-hidden="true" /></div>
                        <div>
                          <h3 className="h6 mb-1">{workflow.label || titleize(workflow.id)} workflow</h3>
                          <p className="small text-body-secondary mb-0">{workflow.description}</p>
                        </div>
                      </div>
                      <div className="d-flex flex-wrap gap-1 mt-auto">
                        {(workflow.capabilities || []).map((capability) => <Badge bg="light" text="dark" key={capability}>{titleize(capability)}</Badge>)}
                      </div>
                      <Button
                        type="button"
                        variant={isCoding ? "outline-primary" : "primary"}
                        className="align-self-start"
                        data-testid={`assistant-open-workflow-${workflow.id}`}
                        onClick={() => openWorkflow?.(workflow.id)}
                      >
                        Open {workflow.label || titleize(workflow.id)} <ArrowRight size={14} className="ms-1" aria-hidden="true" />
                      </Button>
                    </div>
                  </Col>
                );
              })}
            </Row>
          </Card.Body>
        </Card>

        <Card className="settings-card shadow-sm mb-3" data-testid="assistant-capability-contracts">
          <Card.Body>
            <SectionHeader
              title="Assistant readiness"
              text="The contracts below show what Rasputin can discover and preview locally. They do not start commands, audio devices, or model processes."
              action={<Badge bg={commandReady && voiceReady && mcpReady ? "success" : "secondary"}>{commandReady && voiceReady && mcpReady ? "Contracts ready" : "Contracts partial"}</Badge>}
            />
            <Row className="g-3">
              <Col md={4} data-testid="assistant-command-contract">
                <div className="border rounded p-3 h-100">
                  <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
                    <strong><ShieldCheck size={16} className="me-1 text-primary" aria-hidden="true" />Command router</strong>
                    <Badge bg={commandReady ? "success" : "secondary"}>{commandRouter.contractVersion || "Not advertised"}</Badge>
                  </div>
                  <p className="small text-body-secondary mb-2">{titleize(commandRouter.executionMode || "unavailable")} with approval before broker handoff.</p>
                  <div className="small"><span className="text-body-secondary">Preview endpoint:</span> <code>{commandRouter.previewEndpoint || "—"}</code></div>
                  <div className="small mt-1"><span className="text-body-secondary">Allowlisted operations:</span> {commandOperations.length}</div>
                </div>
              </Col>
              <Col md={4} data-testid="assistant-voice-contract">
                <div className="border rounded p-3 h-100">
                  <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
                    <strong><Mic size={16} className="me-1 text-primary" aria-hidden="true" />Voice transport</strong>
                    <Badge bg={voiceReady ? "success" : "secondary"}>{voiceContract.contractVersion || "Not advertised"}</Badge>
                  </div>
                  <p className="small text-body-secondary mb-2">{voiceContract.localOnly ? "Local-only adapter" : "Local policy not confirmed"}; device-free until an explicit audio layer is approved.</p>
                  <div className="small"><span className="text-body-secondary">Transcribe:</span> <code>{voiceContract.transcriptionPath || "—"}</code></div>
                  <div className="small mt-1"><span className="text-body-secondary">Synthesize:</span> <code>{voiceContract.synthesisPath || "—"}</code></div>
                  <div className="border-top mt-2 pt-2" data-testid="assistant-voice-model-readiness">
                    <div className="d-flex align-items-center justify-content-between gap-2">
                      <span className="text-body-secondary">Registered speech models</span>
                      <Badge bg={statusVariant(voiceModelStatus)}>{titleize(voiceModelStatus)}</Badge>
                    </div>
                    {voiceModelRoleEntries.map(([key, label, role]) => (
                      <div className="small mt-1" key={key} data-testid={`assistant-voice-role-${key}`}>
                        <span className="text-body-secondary">{label}:</span>{" "}
                        <strong>{titleize(role.status || "not_checked")}</strong>
                        {role.selectedModelKey && <span className="text-body-secondary"> ({role.selectedModelKey})</span>}
                      </div>
                    ))}
                    {voiceModelReadiness.nextActions?.[0] && <div className="small text-body-secondary mt-1">{voiceModelReadiness.nextActions[0]}</div>}
                  </div>
                </div>
              </Col>
              <Col md={4} data-testid="assistant-mcp-contract">
                <div className="border rounded p-3 h-100">
                  <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
                    <strong><Link2 size={16} className="me-1 text-primary" aria-hidden="true" />MCP capability catalog</strong>
                    <Badge bg={mcpReady ? "success" : "secondary"}>{tools?.contract?.version || "Not advertised"}</Badge>
                  </div>
                  <p className="small text-body-secondary mb-2">Fail-closed discovery keeps blocked tools visible to operators but unavailable to models.</p>
                  <div className="small"><span className="text-body-secondary">Callable tools:</span> {callableToolItems.length} / {toolItems.length}</div>
                  <div className="small mt-1"><span className="text-body-secondary">Blocked by policy:</span> {blockedToolCount}</div>
                  <div className="small mt-1"><span className="text-body-secondary">MCP relays running:</span> {runningMcpCount} / {mcpServerItems.length}</div>
                </div>
              </Col>
            </Row>
          </Card.Body>
        </Card>

        <Card className="settings-card shadow-sm mb-3" data-testid="assistant-command-preview">
          <Card.Body>
            <SectionHeader
              title="Speak a governed command"
              text="Type an intent in plain language. Rasputin only matches allowlisted operations and keeps execution in preview until you review the handoff."
              action={<Badge bg="secondary">Preview only</Badge>}
            />
            <Form onSubmit={previewCommand}>
              <Row className="g-2 align-items-end">
                <Col md={9}>
                  <Form.Label htmlFor="assistantCommand">Command or intent</Form.Label>
                  <Form.Control id="assistantCommand" name="assistantCommand" required maxLength={500} placeholder="Check Docker status or open VS Code" />
                </Col>
                <Col md={3}>
                  <Button type="submit" className="w-100" variant="outline-primary">Preview route</Button>
                </Col>
              </Row>
            </Form>
            {commandPreview && (
              <Alert
                className="mt-3 mb-0"
                variant={commandPreview.route?.status === "recognized" ? "success" : commandPreview.route?.status === "blocked" || commandPreview.route?.status === "rejected" ? "danger" : "warning"}
                data-testid="assistant-command-result"
              >
                <div className="d-flex flex-wrap justify-content-between gap-2">
                  <strong>{titleize(commandPreview.route?.status || "unknown")}</strong>
                  <Badge bg="light" text="dark">{titleize(commandPreview.approval?.state || "not requested")}</Badge>
                </div>
                <div className="small mt-1">{commandPreview.route?.reason || "No route explanation available."}</div>
                {commandPreview.route?.operation && <div className="small mt-1">Operation: <code>{commandPreview.route.operation}</code></div>}
                {(commandPreview.route?.blockedReasons || []).length > 0 && <div className="small text-danger mt-1">Blocked by: {commandPreview.route.blockedReasons.join(", ")}</div>}
                <div className="small text-body-secondary mt-2">Started: {commandPreview.execution?.started ? "yes" : "no"} · Side effects: {commandPreview.execution?.sideEffects ? "yes" : "no"}</div>
              </Alert>
            )}
          </Card.Body>
        </Card>

        <Row className="g-3">
          <Col xl={5}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-identity-card">
              <Card.Body>
                <SectionHeader title="Identity and context" text="Rasputin remains the stable personality and owner-scoped context authority." />
                <div className="d-flex align-items-start gap-3">
                  <div className="rounded-circle bg-primary-subtle text-primary p-3"><Bot size={22} aria-hidden="true" /></div>
                  <div>
                    <strong>{profile?.displayName || "Rasputin"}</strong>
                    <p className="small text-body-secondary mb-0 mt-1">{profile?.persona?.summary || "Local-first orchestration partner."}</p>
                  </div>
                </div>
                <div className="mt-3 d-flex flex-wrap gap-2">
                  {(profile?.persona?.traits || []).map((trait) => <Badge bg="light" text="dark" key={trait}>{trait}</Badge>)}
                </div>
                <dl className="row small mt-4 mb-0">
                  <dt className="col-6 text-body-secondary">Context scope</dt>
                  <dd className="col-6 text-end">{contextPolicy.crossWorkspace ? "Owner / cross-workspace" : "Current workspace"}</dd>
                  <dt className="col-6 text-body-secondary">Sensitive context</dt>
                  <dd className="col-6 text-end">{contextPolicy.sensitiveByDefault ? "Included" : "Excluded by default"}</dd>
                  <dt className="col-6 text-body-secondary">Host control</dt>
                  <dd className="col-6 text-end">{policy.brokerOnly ? "Broker only" : "Review policy"}</dd>
                </dl>
                <div className="border-top mt-3 pt-3 small text-body-secondary">
                  <ShieldCheck size={14} className="me-1 text-success" aria-hidden="true" />
                  Model containers have no direct host access.
                </div>
                <div className="border-top mt-3 pt-3" data-testid="assistant-profile-editor">
                  <SectionHeader title="Personality controls" text="Adjust presentation without changing the safety broker or context authority." />
                  <Form onSubmit={saveProfile}>
                    <Row className="g-2">
                      <Col md={6}>
                        <Form.Label htmlFor="assistantDisplayName">Display name</Form.Label>
                        <Form.Control id="assistantDisplayName" name="displayName" defaultValue={profile?.displayName || "Rasputin"} maxLength={80} />
                      </Col>
                      <Col md={3}>
                        <Form.Label htmlFor="assistantPersonaTone">Tone</Form.Label>
                        <Form.Select id="assistantPersonaTone" name="personaTone" defaultValue={personaStyle.tone || "dry"}>
                          <option value="dry">Dry</option>
                          <option value="direct">Direct</option>
                          <option value="warm">Warm</option>
                        </Form.Select>
                      </Col>
                      <Col md={3}>
                        <Form.Label htmlFor="assistantPersonaSarcasm">Sarcasm</Form.Label>
                        <Form.Select id="assistantPersonaSarcasm" name="personaSarcasm" defaultValue={personaStyle.sarcasm || "light"}>
                          <option value="off">Off</option>
                          <option value="light">Light</option>
                          <option value="moderate">Moderate</option>
                        </Form.Select>
                      </Col>
                      <Col md={12}>
                        <Form.Label htmlFor="assistantPersonaSummary">Personality summary</Form.Label>
                        <Form.Control as="textarea" rows={2} id="assistantPersonaSummary" name="personaSummary" defaultValue={profile?.persona?.summary || ""} maxLength={500} />
                      </Col>
                    </Row>
                    <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-2">
                      <Form.Text>Respectful behavior is always enforced; sarcasm cannot authorize a host action.</Form.Text>
                      <Button type="submit" size="sm" variant="outline-primary">Save personality</Button>
                    </div>
                  </Form>
                </div>
                <div className="border-top mt-3 pt-3" data-testid="assistant-context-preview">
                  <SectionHeader title="Context surface" text="Inspect owner-scoped memory and history before Rasputin builds a plan." />
                  <Form onSubmit={previewContext}>
                    <Row className="g-2">
                      <Col md={6}><Form.Control name="contextObjective" required placeholder="What should Rasputin recall?" aria-label="Context objective" /></Col>
                      <Col md={6}><Form.Control name="contextQuery" placeholder="Search across chats and workspaces" aria-label="Context query" /></Col>
                      <Col md={12}>
                        <Form.Select name="contextSessionId" aria-label="Context source session" defaultValue="">
                          <option value="">Use owner history and memory</option>
                          {sessionItems.map((session) => (
                            <option key={session.id} value={session.id}>
                              {workflowLabel(session)} · {session.title || "Untitled chat"} · {session.workspace || "."}
                            </option>
                          ))}
                        </Form.Select>
                        <Form.Text>Choose an Assistant or Coding chat when the context should be anchored to one conversation.</Form.Text>
                      </Col>
                    </Row>
                    <div className="d-flex justify-content-end mt-2"><Button type="submit" size="sm" variant="outline-primary">Inspect context</Button></div>
                  </Form>
                  {contextPreview && (
                    <div className="small mt-2">
                      <div className="d-flex flex-wrap gap-2">
                        <Badge bg="secondary">Memory {contextPreview.memory?.items?.length || 0}</Badge>
                        <Badge bg="secondary">History {contextPreview.ownerHistory?.results?.length || 0}</Badge>
                        <Badge bg="light" text="dark">Sensitive excluded {contextPreview.memory?.sensitiveExcluded || 0}</Badge>
                      </div>
                      {contextPreview.selectedSession && (
                        <div className="text-body-secondary mt-2">
                          Source session: <strong>{workflowLabel(contextPreview.selectedSession)}</strong> · {contextPreview.selectedSession.title || "Untitled chat"}
                          {(contextPreview.selectedSession.messages || []).length > 0 && (
                            <div className="border rounded p-2 mt-2" data-testid="assistant-selected-session-context">
                              <div className="d-flex justify-content-between gap-2">
                                <span>Selected excerpts</span>
                                <span>{contextPreview.selectedSession.messageCount || 0} messages{contextPreview.selectedSession.messagesTruncated ? " · latest shown" : ""}</span>
                              </div>
                              <Stack gap={1} className="mt-2">
                                {contextPreview.selectedSession.messages.map((message) => (
                                  <div key={message.id} className="bg-body-tertiary rounded px-2 py-1">
                                    <strong className="me-1">{titleize(message.role)}</strong>
                                    <span>{message.content}</span>
                                  </div>
                                ))}
                              </Stack>
                            </div>
                          )}
                        </div>
                      )}
                      <div className="text-body-secondary mt-2">Owner scoped: {contextPreview.policy?.ownerScoped ? "yes" : "no"} · Cross workspace: {contextPreview.policy?.crossWorkspace ? "yes" : "no"}</div>
                      <div className="d-flex justify-content-end mt-2">
                        <Button size="sm" variant="outline-primary" onClick={() => createContextCapsule?.(contextPreview)} data-testid="assistant-save-context-capsule">
                          Save review capsule
                        </Button>
                      </div>
                      {capsuleItems.length > 0 && (
                        <div className="border-top mt-3 pt-2" data-testid="assistant-context-capsule-ledger">
                          <div className="fw-semibold">Context capsule ledger</div>
                          <Stack gap={1} className="mt-2">
                            {capsuleItems.slice(0, 6).map((capsule) => (
                              <div key={capsule.id} className="d-flex flex-wrap align-items-center justify-content-between gap-2 border rounded px-2 py-1">
                                <span>{capsule.objective || "Shared context"}</span>
                                <span className="d-flex align-items-center gap-2">
                                  <Badge bg={statusVariant(capsule.status)}>{titleize(capsule.status)}</Badge>
                                  {capsule.status === "preview" && <Button size="sm" variant="outline-success" onClick={() => reviewContextCapsule?.(capsule.id, "approved")}>Approve</Button>}
                                  {capsule.status === "preview" && <Button size="sm" variant="outline-danger" onClick={() => reviewContextCapsule?.(capsule.id, "rejected")}>Reject</Button>}
                                </span>
                              </div>
                            ))}
                          </Stack>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </Card.Body>
            </Card>
          </Col>

          <Col xl={7}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-plan-composer">
              <Card.Body>
                <SectionHeader title="Plan a request" text="Describe the outcome. Rasputin will build a reviewable plan without starting anything." />
                <Form onSubmit={createPlan}>
                  <Form.Group className="mb-3" controlId="assistantObjective">
                    <Form.Label>Objective</Form.Label>
                    <Form.Control name="objective" required placeholder="Prepare a voice-enabled coding session" />
                  </Form.Group>
                  <Row className="g-2">
                    <Col md={6}>
                      <Form.Label htmlFor="assistantContextSession">Context source</Form.Label>
                      <Form.Select id="assistantContextSession" name="contextSessionId" defaultValue="">
                        <option value="">Use owner history and memory</option>
                        {sessionItems.map((session) => (
                          <option key={session.id} value={session.id}>
                            {workflowLabel(session)} · {session.title || "Untitled chat"}
                          </option>
                        ))}
                      </Form.Select>
                    </Col>
                    <Col md={6}>
                      <Form.Label htmlFor="assistantContextQuery">Context query</Form.Label>
                      <Form.Control id="assistantContextQuery" name="contextQuery" placeholder="What should the plan recall?" />
                    </Col>
                  </Row>
                  <Row className="g-2 mt-1">
                    <Col md={12}>
                      <Form.Label htmlFor="assistantContextCapsule">Approved context capsule</Form.Label>
                      <Form.Select id="assistantContextCapsule" name="contextCapsuleId" defaultValue="">
                        <option value="">Use live context selection above</option>
                        {approvedCapsules.map((capsule) => (
                          <option key={capsule.id} value={capsule.id}>{capsule.objective || "Shared context"} · {capsule.id}</option>
                        ))}
                      </Form.Select>
                      <Form.Text>Approved capsules preserve the inspected context and provenance until their expiry.</Form.Text>
                    </Col>
                  </Row>
                  <Row className="g-2 mt-1">
                    <Col md={6}>
                      <Form.Label htmlFor="assistantModelPack">Model pack</Form.Label>
                      <Form.Select id="assistantModelPack" name="modelPackId" defaultValue="">
                        <option value="">Use inline core pack</option>
                        {packItems.map((pack) => <option key={pack.packId} value={pack.packId}>{pack.packId} · v{pack.version}</option>)}
                      </Form.Select>
                    </Col>
                    <Col md={6}>
                      <Form.Label>Requested operations</Form.Label>
                      <div className="d-flex flex-wrap gap-2">
                        {operationEntries.map(([operation, definition]) => (
                          <Form.Check
                            key={operation}
                            inline
                            type="checkbox"
                            id={`assistant-op-${operation}`}
                            name="requestedOperations"
                            value={operation}
                            label={definition.label || titleize(operation)}
                          />
                        ))}
                      </div>
                    </Col>
                  </Row>
                  <div className="d-flex justify-content-end mt-3">
                    <Button type="submit" disabled={loading} data-testid="assistant-create-plan">Create preview</Button>
                  </div>
                </Form>
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Row className="g-3 mt-1">
          <Col xl={5}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-model-packs">
              <Card.Body>
                <SectionHeader title="Named model packs" text="Reusable fleet definitions for conversation, planning, and voice workers." />
                <Form onSubmit={saveModelPack} className="border-bottom pb-3 mb-3">
                  <div className="d-flex gap-2">
                    <Form.Control name="packId" required placeholder="voice-core" aria-label="Model pack id" />
                    <Button type="submit" variant="outline-primary">Save pack</Button>
                  </div>
                  <div className="mt-2 d-flex flex-wrap gap-2 small">
                    {["main", "planner", "speech_to_text", "text_to_speech"].map((role) => (
                      <Form.Check key={role} inline type="checkbox" name="packRoles" value={role} label={titleize(role)} defaultChecked={role === "main"} />
                    ))}
                  </div>
                </Form>
                {packItems.length ? packItems.map((pack) => (
                  <div key={pack.packId} className="d-flex align-items-center justify-content-between gap-2 border-bottom py-2">
                    <div>
                      <strong className="small">{pack.packId}</strong>
                      <div className="text-body-secondary small">v{pack.version} · {(pack.pack?.entries || []).length} roles</div>
                    </div>
                    <Badge bg="secondary">Broker only</Badge>
                  </div>
                )) : <p className="small text-body-secondary mb-0">No saved packs yet.</p>}
                {voiceRoles.length > 0 && (
                  <div className="mt-3 small text-body-secondary"><Mic size={14} className="me-1" />Voice roles: {voiceRoles.map(titleize).join(", ")}</div>
                )}
                <div className="border-top mt-3 pt-3" data-testid="assistant-voice-loop">
                  <SectionHeader title="Voice loop readiness" text="Preview transcribe → reason → synthesize routing without opening a microphone or speaker." />
                  <div className="d-flex align-items-center justify-content-between gap-2">
                    <Badge bg={voicePreview ? (voicePreview.ready ? "success" : "warning") : "secondary"}>
                      {voicePreview ? (voicePreview.ready ? "Ready for adapter" : "Models needed") : "Not checked"}
                    </Badge>
                    <Button size="sm" variant="outline-primary" onClick={() => previewVoice(packItems[0]?.packId || "")}>Check readiness</Button>
                  </div>
                  {voicePreview && (
                    <div className="mt-2 small">
                      <div className="d-flex flex-wrap gap-2">
                        {(voicePreview.stages || []).map((stage) => <Badge key={stage.stage} bg={statusVariant(stage.status)}>{titleize(stage.stage)}: {titleize(stage.status)}</Badge>)}
                      </div>
                      {(voicePreview.blockers || []).length > 0 && <div className="text-danger mt-2">Blocked: {voicePreview.blockers.join(", ")}</div>}
                      <div className="text-body-secondary mt-2"><ShieldCheck size={13} className="me-1" />Audio I/O started: {voicePreview.execution?.audioIoStarted ? "yes" : "no"}</div>
                    </div>
                  )}
                  <VoiceConsole />
                </div>
              </Card.Body>
            </Card>
          </Col>

          <Col xl={7}>
            <Card className="settings-card shadow-sm h-100" data-testid="assistant-plan-ledger">
              <Card.Body>
                <SectionHeader title="Plan ledger" text="Review plans before any future broker adapter can act on them." />
                {planItems.length ? planItems.map((record) => {
                  const plan = record.plan || {};
                  const operations = plan.localControl?.operations || [];
                  return (
                    <div key={record.id} className="border-bottom py-3" data-testid={`assistant-plan-${record.id}`}>
                      <div className="d-flex flex-wrap justify-content-between align-items-start gap-2">
                        <div>
                          <strong>{plan.objective || "Assistant plan"}</strong>
                          <div className="small text-body-secondary">{record.id} · {plan.modelPackSource || "inline"} model pack</div>
                        </div>
                        <Badge bg={statusVariant(record.status)}>{titleize(record.status)}</Badge>
                      </div>
                      {(plan.blockers || []).length > 0 && <div className="small text-danger mt-2">Blocked: {plan.blockers.join(", ")}</div>}
                      <div className="d-flex flex-wrap gap-2 mt-2">
                        {record.status === "preview" && !(plan.blockers || []).length > 0 && <Button size="sm" variant="success" onClick={() => reviewPlan(record.id, "approved")}><CheckCircle2 size={13} className="me-1" />Approve review</Button>}
                        {record.status === "preview" && <Button size="sm" variant="outline-danger" onClick={() => reviewPlan(record.id, "rejected")}><XCircle size={13} className="me-1" />Reject</Button>}
                        {record.status === "approved" && operations.filter((operation) => operation.status === "planned").map((operation) => (
                          <Button key={operation.operation} size="sm" variant="outline-primary" onClick={() => requestHandoff(record.id, operation.operation)}>
                            <Link2 size={13} className="me-1" />Handoff {operation.label || titleize(operation.operation)}
                          </Button>
                        ))}
                      </div>
                    </div>
                  );
                }) : <p className="small text-body-secondary mb-0">No plans yet. Create a preview above.</p>}
              </Card.Body>
            </Card>
          </Col>
        </Row>

        <Card className="settings-card shadow-sm mt-3" data-testid="assistant-handoffs">
          <Card.Body>
            <SectionHeader title="Broker handoffs" text="Track the action state before Rasputin invokes an allowlisted local adapter." />
            {handoffItems.length ? handoffItems.map((handoff) => (
              <div key={handoff.id} className="d-flex flex-wrap align-items-center justify-content-between gap-2 border-bottom py-2" data-testid={`assistant-handoff-${handoff.id}`}>
                <div className="d-flex align-items-center gap-2">
                  {handoff.actionState === "failed" ? <XCircle size={16} className="text-danger" aria-hidden="true" /> : ["approved", "prepared", "completed"].includes(handoff.actionState) ? <CheckCircle2 size={16} className="text-success" aria-hidden="true" /> : <Clock3 size={16} className="text-warning" aria-hidden="true" />}
                  <span>
                    <strong>{titleize(handoff.operation)}</strong> <span className="small text-body-secondary">· {handoff.id}</span>
                    {brokerOperationMetadata[handoff.operation]?.sideEffects && <Badge bg="warning" text="dark" className="ms-2">Host action</Badge>}
                    {handoff.request?.executionStarted && (
                      <div className="small text-success mt-1" data-testid={`assistant-handoff-receipt-${handoff.id}`} aria-live="polite">
                        {handoff.request?.result?.taskId
                          ? <>Governed Code task started: <code>{handoff.request.result.taskId}</code></>
                          : "Approved broker action completed."}
                      </div>
                    )}
                  </span>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <Badge bg={statusVariant(handoff.actionState || handoff.brokerStatus)}>{titleize(handoff.actionState || handoff.brokerStatus)}</Badge>
                  {handoff.brokerStatus === "approved_for_broker" && <Button size="sm" variant="outline-primary" onClick={() => prepareHandoff(handoff.id)}>Prepare broker</Button>}
                  {handoff.brokerStatus === "ready_for_broker" && handoff.operation === "docker_status" && <Button size="sm" variant="outline-success" onClick={() => dispatchHandoff(handoff.id, handoff.operation)}>Inspect Docker</Button>}
                  {handoff.brokerStatus === "ready_for_broker" && handoff.operation === "open_vscode" && <Button size="sm" variant="outline-warning" onClick={() => dispatchHandoff(handoff.id, handoff.operation)}>Open VS Code</Button>}
                  {handoff.brokerStatus === "ready_for_broker" && handoff.operation === "start_coding_task" && <Button size="sm" variant="outline-primary" onClick={() => dispatchHandoff(handoff.id, handoff.operation)}>Start Code task</Button>}
                </div>
              </div>
            )) : <p className="small text-body-secondary mb-0"><Volume2 size={14} className="me-1" />No broker handoffs requested.</p>}
          </Card.Body>
        </Card>
      </div>
    </section>
  );
}
