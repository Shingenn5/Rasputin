# Warsat And Cookbook Plan

Warsat is Rasputin's model-runtime control plane. It turns known model server patterns into reviewed launch plans before Rasputin is allowed to pull Docker images, start containers, or register new model endpoints.

This is not a copy of Odysseus Cookbook. Rasputin borrows the useful product pattern: curated recipes, hardware-aware runtime guidance, safe defaults, and visible operations. The implementation is Rasputin-native and keeps local privacy and user control as the primary constraints.

## Product Rule

Rasputin is a companion, not an autopilot.

- Normal chat stays manual.
- Agent work is started by the user.
- File changes, web broker use, shell commands, Docker actions, and model registry edits require approval.
- Warsat starts in planning mode.
- Docker execution is disabled until the admin explicitly enables Docker control.

## Current Implementation

The current pass adds the safe foundation:

- Built-in recipe files in `cookbook/recipes/`.
- Backend recipe loading and validation in `backend/warsat/`.
- `GET /api/warsat/status`.
- `GET /api/warsat/recipes`.
- `POST /api/warsat/plan`.
- Bootstrap summary under `warsat`.
- A React `Warsat` view with recipe cards and dry-run launch plans.
- Backend and Playwright smoke coverage.

The planner returns:

- recipe metadata
- runtime image
- model role
- local endpoint
- health URL
- command preview
- model registry entry preview
- safety checks
- warnings
- next steps

It does not execute Docker.

## Recipe Format

Recipes are JSON so the project does not need a YAML dependency yet.

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

Before Rasputin can pull images or start containers, add these controls:

1. Docker control remains disabled by default.
2. Docker socket access is available only through the explicit docker-control compose profile.
3. Every pull/start/stop action creates an approval.
4. Approved actions use one-time approval ids with TTL.
5. Containers bind only to `127.0.0.1`.
6. Host networking is rejected by default.
7. Model folders mount read-only.
8. Container commands are generated from validated recipes, not raw user shell.
9. Runtime health is tested before model registry registration.
10. Every action is audited.

## Next Build Phases

### Phase 1: Recipe Expansion

Add more curated recipes:

- vLLM CUDA
- llama.cpp GGUF
- Ollama bridge
- text-generation-inference
- embeddings server
- reranker server

Add recipe validation tests for every runtime.

### Phase 2: Hardware Inventory

Add a read-only hardware probe:

- OS
- Docker availability
- GPU visibility
- NVIDIA runtime status
- available VRAM when visible
- mounted model folders

This should never install drivers or edit host config.

### Phase 3: Approval-Gated Execution

Add:

- `POST /api/warsat/pull`
- `POST /api/warsat/start`
- `POST /api/warsat/stop`
- `GET /api/warsat/containers`
- `GET /api/warsat/logs/{containerId}`
- `POST /api/warsat/register-model`

Execution must be blocked unless Docker control is enabled and the approval is valid.

### Phase 4: Cookbook Workflows

Unify Warsat recipes with broader Rasputin workflows:

- code review
- folder cleanup
- local document draft
- RAG index workspace
- Graphify workspace
- paper writing
- research summary

These should map to existing skills and agent modes.

### Phase 5: Document Artifacts

Add a Claude-style document workspace:

- markdown editor
- preview pane
- version history
- AI suggestions
- accept/reject edits
- export to Markdown first

Rasputin should help the user write. It should not overwrite the user's document without approval.
