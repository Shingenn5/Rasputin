import React, { useState } from "react";
import { Badge, Button, Card, Col, Form, ListGroup, Row, Stack } from "react-bootstrap";
import { Trash2 } from "lucide-react";
import { displayWorkspaceName } from "../../lib/display.js";
import { PageHeader } from "./RuntimePrimitives.jsx";

export function SessionsView({
  view,
  sessions,
  chatFolders,
  activeChatFolder,
  setActiveChatFolder,
  selectedSession,
  loadSession,
  resumeSession,
  createChatFolder,
  assignSessionFolder,
  deleteSession,
  cleanupEmptySessions,
  canDeleteSessions = false,
  createSkillFromSession,
}) {
  const folders = chatFolders?.folders || [];
  const sessionItems = sessions?.sessions || [];
  // The list is capped server-side (most recent 100); `total` is the real
  // table count, so the header/"All" chip agree with the folder counts.
  const totalSessions = sessions?.total ?? sessionItems.length;
  const emptySessions = sessions?.emptyTotal ?? sessionItems.filter((session) => session.isEmpty).length;
  const [sessionSearch, setSessionSearch] = useState("");
  const selectedId = selectedSession?.session?.id;
  const needle = sessionSearch.trim().toLowerCase();
  const filteredSessions = sessionItems.filter((session) => {
    if (activeChatFolder === "unfiled" && session.folder) return false;
    if (!["all", "unfiled"].includes(activeChatFolder) && session.folder !== activeChatFolder) return false;
    return !needle || String(session.title || "").toLowerCase().includes(needle);
  });
  return (
    <section className={`app-view ${view === "sessions" ? "active" : ""}`} id="sessionsView" data-app-view="sessions">
      <PageHeader title="Sessions" text="Persistent conversations, chat folders, and task history stored locally in SQLite." />
      <div className="task-dashboard">
        <Row className="g-3">
          <Col lg={4}>
            <Card className="settings-card shadow-sm h-100">
              <Card.Body className="d-flex flex-column">
                <div className="section-row">
                  <div>
                    <h2>Chats</h2>
                    <p className="text-body-secondary mb-0">
                      {totalSessions} stored conversation{totalSessions === 1 ? "" : "s"}.
                      {totalSessions > sessionItems.length ? ` Showing the ${sessionItems.length} most recent.` : ""}
                    </p>
                  </div>
                  {canDeleteSessions && emptySessions > 0 && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline-danger"
                      data-testid="sessions-clear-empty"
                      onClick={() => cleanupEmptySessions?.()}
                    >
                      <Trash2 size={14} className="me-1" aria-hidden="true" />
                      Remove empty ({emptySessions})
                    </Button>
                  )}
                </div>
                <Form.Control
                  type="search"
                  className="mt-2"
                  placeholder="Search chats..."
                  aria-label="Search chats"
                  data-testid="session-search"
                  value={sessionSearch}
                  onChange={(event) => setSessionSearch(event.target.value)}
                />
                <div className="chat-filter-chips mt-2" data-testid="chat-folder-list" aria-label="Chat folders">
                  <button type="button" className={activeChatFolder === "all" ? "is-active" : ""} onClick={() => setActiveChatFolder?.("all")}>
                    All <small>{totalSessions}</small>
                  </button>
                  <button type="button" className={activeChatFolder === "unfiled" ? "is-active" : ""} onClick={() => setActiveChatFolder?.("unfiled")}>
                    Unfiled <small>{chatFolders?.unfiledCount || 0}</small>
                  </button>
                  {folders.map((folder) => (
                    <button key={folder.id} type="button" className={activeChatFolder === folder.name ? "is-active" : ""} onClick={() => setActiveChatFolder?.(folder.name)}>
                      {folder.name} <small>{folder.sessionCount || 0}</small>
                    </button>
                  ))}
                </div>
                <ListGroup className="runtime-list session-scroll-list mt-2">
                  {filteredSessions.map((session) => (
                    <ListGroup.Item key={session.id} className={`session-list-item${session.id === selectedId ? " is-active" : ""}`}>
                      <button type="button" className="session-open-button" onClick={() => loadSession(session.id)}>
                        <strong>{session.title}</strong>
                        <small>{session.status} / {session.mode} / {displayWorkspaceName(session.workspace)}</small>
                      </button>
                      <div className="session-list-controls">
                        <Form.Select
                          size="sm"
                          aria-label={`Move ${session.title} to folder`}
                          value={session.folder || ""}
                          onChange={(event) => assignSessionFolder?.(session.id, event.target.value || null)}
                        >
                          <option value="">Unfiled</option>
                          {folders.map((folder) => <option key={folder.id} value={folder.name}>{folder.name}</option>)}
                        </Form.Select>
                        {canDeleteSessions && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline-danger"
                            data-testid={`sessions-delete-${session.id}`}
                            aria-label={`Delete ${session.title || "Untitled chat"}`}
                            title={session.isEmpty ? "Delete empty chat" : "Delete chat"}
                            onClick={() => deleteSession?.(session)}
                          >
                            <Trash2 size={14} aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </ListGroup.Item>
                  ))}
                  {!filteredSessions.length && (
                    <ListGroup.Item className="text-body-secondary">
                      {needle ? "No chats match your search." : "No chats in this folder."}
                    </ListGroup.Item>
                  )}
                </ListGroup>
                <form className="chat-folder-create mt-auto" data-testid="chat-folder-create" onSubmit={createChatFolder}>
                  <Form.Label htmlFor="chatFolderName">New folder</Form.Label>
                  <div>
                    <Form.Control id="chatFolderName" name="name" placeholder="Writing, Coding, Research" />
                    <Button type="submit">Create</Button>
                  </div>
                </form>
              </Card.Body>
            </Card>
          </Col>
          <Col lg={8}>
            <Card className="settings-card shadow-sm h-100">
              <Card.Body>
                <div className="section-row">
                  <div>
                    <h2>{selectedSession?.session?.title || "Select a session"}</h2>
                    <p className="text-body-secondary mb-0">
                      {selectedSession?.session
                        ? `${sessionFolderName(selectedSession.session.folder)} / ${displayWorkspaceName(selectedSession.session.workspace)}`
                        : "Review messages, tasks, and saved context."}
                    </p>
                  </div>
                  {selectedSession?.session && (
                    <Stack direction="horizontal" gap={2}>
                      <Button variant="outline-secondary" onClick={() => resumeSession?.(selectedSession.session.id)}>Resume Chat</Button>
                      <Button variant="outline-secondary" onClick={() => createSkillFromSession(selectedSession.session.id)}>Preview Skill</Button>
                    </Stack>
                  )}
                </div>
                {selectedSession?.session && (
                  <div className="session-folder-control mt-3">
                    <Form.Label htmlFor="selectedSessionFolder">Folder</Form.Label>
                    <Form.Select
                      id="selectedSessionFolder"
                      value={selectedSession.session.folder || ""}
                      onChange={(event) => assignSessionFolder?.(selectedSession.session.id, event.target.value || null)}
                    >
                      <option value="">Unfiled</option>
                      {folders.map((folder) => <option key={folder.id} value={folder.name}>{folder.name}</option>)}
                    </Form.Select>
                  </div>
                )}
                <Stack gap={2} className="mt-3">
                  {(selectedSession?.messages || []).map((message, index) => (
                    <Card className="message-card" key={`${message.createdAt || message.created_at}-${index}`}>
                      <Card.Body>
                        <Badge bg={message.role === "assistant" ? "primary" : "secondary"}>{message.role}</Badge>
                        <p className="mb-0 mt-2">{message.content}</p>
                      </Card.Body>
                    </Card>
                  ))}
                </Stack>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </div>
    </section>
  );
}

function sessionFolderName(folder) {
  return folder || "Unfiled";
}
