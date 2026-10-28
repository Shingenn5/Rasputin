# Rasputin workstation upgrade

The upgrade branch adds a workstation navigation shell, a dedicated local API workspace,
and a separate supervised LoRA training workflow. The installed Unsloth application was
examined through REA static analysis and live window observation; see
[the evidence and design study](UNSLOTH_WORKSTATION_UPGRADE_STUDY.md).

## Navigation and rollback

- Library opens the existing installed-model workflow; Model Hub opens discovery. This model
  library is an intentional Rasputin adaptation, not Unsloth's content library.
- API, Training and Scheduled have direct hash routes. Administrator access is required.
- Library and Model Hub render inline so the navigation remains available. Chat's structure
  and composer are preserved; Settings retains its dialog.
- Sidebar width persists locally between 220 and 400 pixels. Drag the separator, use arrow
  keys (Shift for larger steps), Home/End for bounds, or Enter/double-click to reset to 260.
  Collapsing preserves the saved width. Phones use the existing overlay drawer.
- Sidebar styling is isolated in `sidebar-workstation.css`; new page styling is in
  `features/workstation/workstation.css`. Reverting the upgrade commit restores the prior
  tracked layout without requiring a data migration.
- Scheduled exposes existing durable schedule definitions. The existing backend does not
  dispatch these definitions as recurring autonomous jobs; this upgrade does not claim a
  working recurring scheduler.

## Local API

The API page creates a named key for each client and displays the current `/v1` base URL.
Keys appear once, persist only as SHA-256 digests of cryptographically random secrets,
and can be revoked independently. Account identity, role and enabled state are checked
on use, including deletion/recreation of an account with the same name.

| Route | Contract |
| --- | --- |
| `GET /api/model-serving/keys` | Owner/admin key metadata; requires a member/admin UI session. |
| `POST /api/model-serving/keys` | Admin creates `{name}`; returns the secret once and enables serving. |
| `DELETE /api/model-serving/keys/{id}` | Owner/admin revocation. |
| `GET /v1/models` | Bearer key; available local inference model IDs. |
| `POST /v1/chat/completions` | Bearer key; normal and SSE streaming responses. |

Named keys grant local inference only. They do not grant UI sessions, MCP execution,
native metrics or management privileges. Existing singleton gateway keys retain their
previous opt-in protocol behavior. Host/Origin checks and loopback defaults remain in
force; creating a key does not enable LAN access. The application and loaded model must
remain running. Chat Completions support does not imply Responses API conformance.

## Training workflow and runtime boundary

Training is a separate subprocess lifecycle, not an inference mode. The page accepts an
absolute local Transformers model directory with config, original tokenizer and
safetensors weights, plus JSONL examples with a nonempty `text` field. It supports
CUDA FP16 causal-LM LoRA, batch size one and gradient accumulation four. It does not
implement QLoRA, full-weight training, resume, evaluation, GGUF merging or automatic model
registration. GGUF inference files cannot be used as training bases.

Data limits are 4 MB, 2–10,000 records, 1–10,000 steps, rank 4–64 and sequence length
128–8192. Readiness and job submission validate these inputs independently. Native model
loading and training admission share a lock; loaded native inference models must be stopped
before a run. Externally managed GPU processes remain outside Rasputin's resource ownership.

Readiness checks also exercise tiny in-memory LoRA adapter injection and the TRL configuration
API, so package presence alone cannot label an incompatible environment ready.

The maintainer provisions a separate compatible CUDA/PyTorch, Transformers, PEFT, TRL,
datasets and accelerate environment, selected with `RASPUTIN_TRAINING_PYTHON`. Source runs
may inspect their own interpreter; packaged builds require an explicit external training
runtime. No dependencies, models or remote Python code are installed or downloaded by the
training action. The worker uses local-only model loading and safetensors; datasets and
adapters remain in app-owned training storage. The bundled worker source is included in
the packaging spec, but including the worker does not install its ML dependencies.

Jobs retain progress, loss and terminal status. Stop terminates the owned worker;
buffered progress cannot overwrite cancellation. Shutdown waits and escalates to kill
after a bounded timeout. A worker-side parent-process watcher exits on abrupt owner death.
Interrupted jobs are recorded after restart. Completed adapters export as an immutable ZIP
containing adapter/tokenizer files; source datasets are excluded. Adapters require their
original base model. Training storage persists until the operator manages it separately.

| Route | Contract |
| --- | --- |
| `GET /api/training` | Runtime capability and durable jobs. |
| `GET /api/training/jobs` | Lightweight progress polling. |
| `POST /api/training/preflight` | Validate model directory, dataset and resource/runtime admission. |
| `POST /api/training/jobs` | Revalidate and start a worker. |
| `POST /api/training/jobs/{id}/cancel` | Stop an active owned worker. |
| `GET /api/training/jobs/{id}/adapter` | Download a completed adapter. |

Every training route requires an administrator UI session. Inference API keys do not grant
training access. Training errors exclude third-party exception text because it can contain
private paths, dataset contents or credentials.

## Verification boundaries

Source build, focused backend tests, Desktop lifecycle tests, and live source-app browser
checks are recorded in the delivery report. API key creation/revocation is exercised against
the actual isolated backend; inference protocol tests use deterministic model fixtures.
Responsive checks cover 1440, 768 and 390 pixels. No installer was built or installed by
this upgrade. A source build does not update the installed daily-driver application.

The existing source environment has no ML training packages. Any tiny random-model worker
probe described in the Unsloth study is mechanics evidence for that selected runtime only,
not useful model quality or certification of arbitrary model families. Do not call this
a provisioned end-user training product until a separate supported runtime and packaged
workflow have been verified.

### Recorded source verification, October 27, 2026

- `npm run build`: passed. Existing Pyodide externalization/vendor size warnings remain.
- Focused API, training and native-runtime Python suite: 62 tests passed.
- The exact scoped-source snapshot also passed the full backend smoke suite together with
  the focused checks: 230/230 tests. Its standalone frontend build passed.
- Sidebar/navigation/model JavaScript checks: 14 passed. Desktop syntax passed; Desktop
  lifecycle tests passed 5/5 when run with usable temporary storage and process permissions.
- Five final focused Chromium checks passed against an isolated authenticated backend:
  drag/keyboard/persistence/reset, Library↔Hub/Scheduled navigation, actual key lifecycle,
  training validation, and responsive API/Training layouts at 1440/768/390 pixels.
- Integration on top of the other chat's `b47a6f1` popup change passed the complete combined
  browser suite: 11/11, including its hardware/model popup, model picker and responsive
  checks. Its approved source and test changes are retained. An earlier unintegrated
  snapshot had a phone composer-position assertion failure after focus restoration;
  the final combined suite supersedes that UI result.
- A broader combined backend run passed 193/199. Six shell/coding-trial assertions failed
  in code carrying pre-existing native-validation changes; those edits are excluded from
  this upgrade. This is not a claim that the full mixed checkout passes.
- A one-step random-model probe reached local weight/dataset loading but failed adapter
  injection because the selected Unsloth environment's PEFT/TorchAO packages conflict.
  No adapter was produced. The strengthened capability check independently rejected that
  environment with `ready=false` before any new job submission.
- Documentation and whitespace validation passed. Installed-app and installer validation
  were not performed. Existing/concurrent unrelated changes remain outside the commit.
