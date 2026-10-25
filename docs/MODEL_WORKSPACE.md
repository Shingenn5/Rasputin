# Unified model workspace

Models is the single sidebar destination for Discover, My Models, Loaded, Serving,
and Advanced. Existing `#discover` links open Discover inside the same workspace.
The desktop dialog follows the window viewport and switches to wrapping navigation
and stacked content in smaller windows. The layout changes live in
`frontend-src/src/features/models/modelWorkspace.css` for a narrow rollback path.
Chat's welcome content now shrinks and scrolls when window height is reduced,
keeping the existing composer pill in view. Those rules are isolated in
`frontend-src/src/styles/window-layout.css`.

## Reuse models from other apps

In **Models → My Models → Import from other apps**:

- **Scan known model folders** registers valid GGUF files from LM Studio's default,
  legacy, and configured download directories; the Hugging Face cache; and Unsloth
  Studio's exports and legacy cache. Environment overrides for HF and Unsloth roots
  are honored when present in Rasputin's environment.
- **Scan and import folder** adds an explicitly selected model folder to Rasputin's
  allowed model locations and registers its GGUF files. It rejects missing folders,
  filesystem roots, and the home directory. No model files are copied or deleted.
- **Connect a running local engine** lists models from an explicitly entered
  loopback OpenAI-compatible endpoint, with an optional API key, and connects the
  selected model. Unsloth, LM Studio, and Ollama can be used through their compatible
  APIs. Their owning application controls loading and stopping those models.

These actions require an administrator and the model-registry permission. Folder
scanning also requires file-read permission. Scans are bounded, check the GGUF
signature, skip projector files and secondary shards, and reuse existing registrations.
Resolved files outside the allowed model roots remain excluded.
Endpoint probes disable proxies and redirects and do not persist the supplied key.
Connecting a model uses the existing model secret store.

Safetensors, adapters, and Ollama blobs are not silently converted into native models.
Export a compatible GGUF or connect to the engine serving the original model.
Registered files must remain available at their original locations. GGUF recognition
does not guarantee architecture compatibility or enough memory to load a model.

## Model settings

**Load Model** provides automatic, lower-memory, and CPU-only presets, plus context,
GPU layers, RAM/VRAM placement, batch sizes, threads, KV precision, and device splits.
Placement is checked before launch. Changing weight quantization requires a different
GGUF artifact. These controls configure inference, not training or model architecture.

**Inference → Save inference settings** persists temperature, model instructions,
an optional response limit, and up to four stop strings for local model requests.
The request path consumes those values; response limits cannot exceed the governed
context budget. Model instructions participate in context composition. Chat retains
its reasoning control. GPU/context/thread changes require a new native load.

## Verification scope

`tests/ui/unifiedModels.spec.mjs` exercises six viewport sizes, legacy links and
keyboard tabs, local engine discovery and profile settings reaching a controlled
HTTP inference server, and GGUF import followed by a selected load-preset request.
The GGUF browser fixture intercepts launch: it is not proof of real weight inference.
`tests/testLocalModelSources.py` covers permissions, import idempotency, unsupported
files, endpoint containment, key handling, profile validation, and request settings.

These are source-app checks. They do not update or certify an installed Electron
application or prove inference for every model architecture.

Upstream storage and export references:
[Unsloth storage roots](https://github.com/unslothai/unsloth/blob/main/studio/backend/utils/paths/storage_roots.py),
[Unsloth GGUF deployment](https://unsloth.ai/docs/basics/inference-and-deployment/lm-studio).
