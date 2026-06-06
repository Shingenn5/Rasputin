# Warsat Launch Protocols Plan

Warsat is Rasputin's model-runtime control plane. It turns known local model server patterns into reviewed launch plans before Rasputin is allowed to pull Docker images, start containers, or register new model endpoints.

The implementation is Rasputin-native: protocol-driven, local-first, approval-gated, and designed around user control.

## Product Rule

Rasputin is a companion, not an autopilot.

- Normal chat stays manual.
- Agent work is started by the user.
- File changes, web broker use, shell commands, Docker actions, and model registry edits require approval.
- Warsat starts in planning mode.
- Docker execution is disabled until the admin explicitly enables Docker control.

## Current Implementation

The current pass adds the safe foundation plus approval-gated deployment:

- Built-in protocol files in `warsat/protocols/`.
- Backend protocol loading and validation in `backend/warsat/`.
- `GET /api/warsat/status`.
- `GET /api/warsat/protocols`.
- `POST /api/warsat/plan`.
- `POST /api/warsat/deploy`.
- Bootstrap summary under `warsat`.
- A React `Warsat` view with protocol cards, launch plans, deploy approval requests, and deploy status.
- Backend and Playwright smoke coverage.

The planner returns:

- protocol metadata
- runtime image
- model role
- local endpoint
- health URL
- command preview
- model registry entry preview
- safety checks
- warnings
- next steps

Deployment is two-step:

1. A deploy request validates the generated plan and creates a redacted `warsat_deploy` approval.
2. After the approval is approved, the same deploy request consumes the one-time approval, pulls the image, replaces the managed container name if it exists, starts the container, and writes the model registry entry.

Docker execution is still blocked unless the wrapper is started with the docker-control compose overlay and Docker control is enabled in Safety settings.

## Protocol Format

Protocols are JSON so the project does not need a YAML dependency yet.

Required fields:

- `id`
- `name`
- `runtime`
- `image`
- `modelFormat`
- `defaultHostPort`
- `containerPort`

Important optional fields:

- `defaultRole`
- `capabilities`
- `gpu`
- `modelMount`
- `dataMounts`
- `modelArgument`
- `defaultArguments`
- `healthPath`
- `security`
- `notes`

## Warsat Execution Requirements

Implemented controls:

1. Docker control remains disabled by default.
2. Docker socket access is available only through the explicit docker-control compose profile.
3. Deploy creates an approval before pull/start.
4. Approved deploy actions use one-time approval ids with TTL.
5. Containers bind only to `127.0.0.1`.
6. Host networking is rejected by default.
7. Model folders mount read-only.
8. Container commands are generated from validated protocols, not raw user shell.
9. Model registry writes require the model registry edit permission.
10. Every action is audited.

Remaining controls:

- Add Warsat-specific stop, restart, logs, and status endpoints.
- Run runtime health checks before presenting a deployed model as healthy.
- Add hardware inventory for Docker, GPU runtime, and VRAM visibility.

## Next Build Phases

### Phase 1: Protocol Expansion

Add more curated protocols:

- vLLM CUDA
- llama.cpp GGUF
- Ollama bridge
- text-generation-inference
- embeddings server
- reranker server

Add protocol validation tests for every runtime.

### Phase 2: Hardware Inventory

Add a read-only hardware probe:

- OS
- Docker availability
- GPU visibility
- NVIDIA runtime status
- available VRAM when visible
- mounted model folders

This should never install drivers or edit host config.

### Phase 3: Runtime Operations

Add:

- `POST /api/warsat/stop`
- `GET /api/warsat/containers`
- `GET /api/warsat/logs/{containerId}`

Operations must remain blocked unless Docker control is enabled and the approval is valid.

### Phase 4: Rasputin Operation Protocols

Unify Warsat model protocols with broader Rasputin workflows:

- code review
- folder cleanup
- local document draft
- RAG index workspace
- Graphify workspace
- paper writing
- research summary

These should map to existing skills and agent modes.

### Phase 5: Document Outputs

Add a Rasputin document workspace:

- markdown editor
- preview pane
- version history
- AI suggestions
- accept/reject edits
- export to Markdown first

Rasputin should help the user write. It should not overwrite the user's document without approval.
