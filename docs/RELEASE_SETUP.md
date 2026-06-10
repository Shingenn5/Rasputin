# Rasputin Release Setup Guide

This guide is for a clean local clone. It avoids machine-specific paths and does not require committing any runtime data.

## 1. Start The Wrapper

```powershell
.\start-wrapper.ps1
```

Open the browser manually:

```text
http://127.0.0.1:8787
```

Rasputin binds to localhost. It starts when you start the Docker container or launcher.

## 2. Get The First-Run Password

The first generated admin password is printed in container logs:

```powershell
docker compose logs rasputin-wrapper
```

Use the `admin` username unless you configured `RASPUTIN_ADMIN_USER`.

The password is not displayed in the browser. Do not copy it into Git, screenshots, docs, tickets, or issue comments.

## 3. Change The Admin Password

After login:

1. Open Settings.
2. Open Admin.
3. Enter the generated password as the current password.
4. Save a new local admin password.

The password hash stays in ignored local runtime data under `data/`.

## 4. Run The Setup Checklist

Open Settings -> General. The Release setup checklist should show:

- admin password state
- chat model connection state
- active workspace state
- privacy lock state
- Markdown output folder state

Use the checklist buttons to jump to Models, Workspaces, Safety, Output, or Admin.

## 5. Connect A Model

For an already-running local model endpoint:

1. Open Models.
2. Register or select the local endpoint.
3. Run Discover or Test health.
4. Confirm the model is reachable.

Privacy lock blocks non-local model URLs by default. Remote APIs require an explicit Safety change and API keys must come from environment variables or the ignored local secret store.

## 6. Select A Workspace

Open Workspaces and choose a mounted folder. Docker can only browse folders that are mounted into the wrapper or already visible inside the container.

New folder access should start read-only. File writes, moves, shell execution, Docker control, and web-search broker use remain governed by Safety and approvals.

## 7. Check Output

Open Settings -> Output and confirm the Markdown export folder. Exports must stay inside Rasputin-visible paths.

## 8. Validate Before Sharing

Run:

```powershell
npm run checkRepoSafety
.\scripts\test.ps1 -Ui
```

Before pushing or packaging, verify Git does not stage:

- `data/`
- `workspace/`
- `models/`
- `testdata/`
- logs
- screenshots
- API keys
- generated RAG or graph indexes

