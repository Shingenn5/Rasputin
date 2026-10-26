---
name: verify
description: Build, launch, and drive Rasputin locally to verify changes end-to-end without Docker.
---

# Verifying Rasputin changes locally

## Build + launch (no Docker needed)

```bash
npm run build                      # vite → outputs to frontend/ (served by backend)
RASPUTIN_DATA_DIR=<session-scratch-dir> PORT=8899 python server.py
```

- Put the isolated data directory in the session scratchpad (for example under `C:\tmp`), never in
  the repository. Native runtime data otherwise defaults to `%LOCALAPPDATA%\Rasputin\data`. Never run a test
  backend against the installed app's live store. Identify the owner from `desktop-runtime.json`
  or `native-host.json` before a requested update/restart.
- Auth is real. On a fresh isolated data directory, read the first-run admin password from the
  server console, then log in through `POST /api/auth/login`. Browser verification should use the
  returned httponly `rasputin_session` cookie; scripted API calls need a cookie jar.
- App URL: `http://127.0.0.1:8899/#chat` (hash routes: #home, #chat, #models, #settings/...).

## Fake model endpoint (observe engine → provider payloads)

Register a mock OpenAI-compatible server (see scratchpad pattern: HTTP server on 127.0.0.1
that answers `GET /v1/models` and `POST /v1/chat/completions`, including `stream: true`
as SSE `data:` lines, and appends request bodies to a JSONL file):

```bash
curl -c <cookie-jar> -H "Content-Type: application/json" -X POST :8899/api/auth/login -d '{"username":"admin","password":"<printed-password>"}'
curl -b <cookie-jar> -H "Content-Type: application/json" -X POST :8899/api/model-registry/upsert -d '{"key":"mock-local","provider":"openai-compatible","role":"main","baseUrl":"http://127.0.0.1:9911/v1","model":"mock-model","runtime":"external-local","enabled":true}'
curl -b <cookie-jar> -H "Content-Type: application/json" -X POST :8899/api/model-registry/test -d '{"key":"mock-local"}'   # marks it reachable → UI "healthy"
curl -b <cookie-jar> -H "Content-Type: application/json" -X POST :8899/api/preferences -d '{"selectedModel":"mock-local"}'
```

Add a `time.sleep(3.5)` in the mock's POST handler to widen the busy window when testing
queueing/generating states.

## Drive the UI

Playwright is installed; import from the project copy when scripting outside the repo dir:

```js
import { chromium } from "file:///C:/Users/elliott/OneDrive/Documents/WrapperProject/node_modules/playwright/index.mjs";
```

Wait for `body[data-ready='true']`. Useful testids: `header-model-indicator`,
`chat-mode-chip`, `chat-model-chip`, `chat-reasoning-chip`, `command-menu`,
`command-item`, `queue-strip`, `queued-message`, `model-side-panel`, `mode-side-panel`.

## Gotchas

- Switching mode (`chooseTaskMode` in App.jsx) re-routes `selectedModel` to the mode's
  role model — a healthy selection can silently become an unhealthy one; the header
  indicator will show STOPPED.
- `tests/ui/rasputinSmoke.spec.mjs` predates the cc-layout chat UI (references
  `#homeView`, `agent-lanes`, `#welcomePanel`) and fails independently of new changes.
- `npm run testHarness` / `scripts/test.ps1` is a retired container harness, not the native
  verification workflow. Do not start it for this product.
