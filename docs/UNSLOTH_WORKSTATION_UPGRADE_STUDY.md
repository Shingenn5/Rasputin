# Unsloth workstation upgrade study

Study date: October 27, 2026. Target: the installed Unsloth Desktop 0.1.911-beta application, its shipped Studio code, and current official documentation. This study supports the requested Rasputin upgrade; it does not certify either application's inference or training performance.

## Evidence and identity

The executable is unchanged from the [October 26 investigation](UNSLOTH_REVERSE_ENGINEERING_2026-10-26.md): 38,833,984 bytes, SHA-256 `c4ecb646ae2c9d2e8d31b92baf94b4c957ac38f03ba68595aa6002622ed7c27a`. A fresh REA frontend inventory also matches the previous digest, `3b88819dec802b0a7349419b0c43379fb405f5fca82acfff6385a7d48b621a95`.

This pass adds actual installed-window observation through Windows Computer Use: Chat, the More navigation menu, API monitor, API settings, Train configuration, and Library were displayed. Only navigation and opening/closing the settings dialog were performed. No model was downloaded, loaded, unloaded, trained, or queried. No token was created or revoked, no preference was changed, and no private file content was opened. Account names, token prefixes, chat titles, and local filenames visible in the existing UI are deliberately excluded from this report.

A fresh REA CLI 6.8.0 analysis selected only `assets/api-keys-tab-C7-5rFvQ.js` from the packaged frontend:

- Parent Evidence: `ev_b36185fdf7d13ee8f72d0d45d8a54964f5074fad68faca06055abe1027c4e04f`.
- Summary Evidence: `ev_1762f5540b439653698645169805c4251e65dfc11570d80d4f1665ac267208b9`.
- One source parsed, 28,696 text bytes, 6,983 visited AST nodes, 185 findings, zero parse failures.
- 722 other inventoried files were outside this selected analysis. The application and semantic graphs remain partial; unknown relationships are not negative findings.
- JavaScript was parsed as inert text. REA did not execute this bundle or prove endpoint reachability.

The full 21,591,181-byte Evidence bundle and summary remain in this session's scratch artifacts rather than Git. The first attempt was denied filesystem read access; the read-only elevated run completed analysis but failed export because its temporary parent directory was unavailable. A corrected export into the existing session directory succeeded with CLI exit 0. No MCP configuration was changed, and no native disassembler was needed. The successful export reproduced the same parent Evidence identity.

## What the running interface shows

### Navigation and visual hierarchy

**Observed live.** The app uses a dark neutral sidebar, a slightly darker main canvas, small line icons, rounded selected navigation rows, restrained green accents, and generous spacing. The sidebar was 280 pixels wide according to its accessible resize control. A narrow titlebar contains the sidebar toggle and back/forward controls; account and settings controls remain at the bottom.

Primary destinations were New chat, Model hub, Library, Images, Train, API, and More. Projects and recent chats occupy separate sidebar groups on Chat, API, and Library. The training page omits those long groups in the observed state. More revealed Projects, Video, Audio, Recipes, Export, Scheduled, and Customize sidebar. These are findings about the current installed configuration, not a universal immutable navigation list.

The sidebar exposes a thumb named **Resize or collapse sidebar** with value 280. Dragging or keyboard resizing was not performed because it would change the user's saved preference. The previous static Hub study separately established accessible separator, pointer/keyboard handling, bounds, persistence, and reset for the Hub's internal split pane; that is a different resize control.

**Design inference for Rasputin.** Keep a small primary navigation group; give API, Training, Scheduled, Library, and Model Hub actual routes and meaningful empty states. Use bounded persistent sidebar width, an accessible keyboard-operable separator, a visible reset action, and a mobile overlay. Preserve Rasputin's existing chat composer and ownership/authentication boundaries. Cosmetic resemblance is a design choice; copying another product's trust exceptions is not required.

### Library and Model Hub have different jobs

**Observed live.** Library is `/library`: a content library with search, Filter, Sort, grid/list switches, New, Library settings, and Suggested/Favorites/Folders/Chats/Images/All sections. It is not the model inventory. No listed document was opened.

**Observed shipped code, reused from the previous study.** Model Hub provides Discover and On Device, search/filter/sort, precise variants, local downloads/fine-tunes, details, README, and a persistent list/detail split. Discovery combines remote catalog records with local artifact and download state. Feed/detail caches and cancellation reduce repeat work; they do not establish offline search or runtime speed.

**Rasputin adaptation.** A downloaded-model destination may reasonably be named Model library, but that is an intentional adaptation. A claim that it duplicates Unsloth's content Library would be incorrect. Model identity, exact artifact, and resident runtime should remain distinct states.

### API is an operational workspace

**Observed live.** `/api-monitor` displays a copyable loopback `/v1` base URL, current model state, load/reload/eject controls, and a request log. Summary fields include in-flight requests, recent requests, errors, average latency, generation speed, and token totals. The empty log explains how to begin. Search, All/In flight/Completed/Errors/Cancelled filters, pause, refresh, and clear controls surround it. Examples switch between API families, curl/Python/JavaScript, and Windows/Linux-style commands.

API settings is a separate dialog. Access tokens have a friendly name, Never/7d/30d/90d expiry choices, creation, and existing-token actions. The token-creation action was not invoked.

**Observed source.** The shipped `backend/routes/auth.py:768` creates a token and returns its raw value once; `:836` lists metadata, and `:848` revokes. Creation inherits an expiring parent credential's upper bound instead of allowing an expiring key to mint an unlimited one. Account-scoped key records prevent a same-name replacement account from inheriting prior credentials. `backend/auth/storage.py:1703` declares the public prefix; `:1714` uses cryptographic random bytes and stores a fenced PBKDF2-derived hash, prefix, metadata, and optional expiry. `:1817` soft-revokes within account/username scope. `backend/auth/x_api_key.py:16` normalizes eligible Anthropic-style `x-api-key` credentials into Bearer authentication, with existing Authorization taking precedence.

**Important observed difference.** The installed monitor example used a real-key placeholder while one API settings example used `Bearer not-needed`. Keyless policy modules are present in the shipped backend. That discrepancy is not proof that every endpoint is publicly callable. Rasputin should require explicit API keys on its external compatibility surface, including Desktop, and keep cookie/Desktop administrator access separate from inference-key access.

Current [official API documentation](https://unsloth.ai/docs/basics/api) describes OpenAI and Anthropic compatibility, once-only keys, expiry and revocation, and client integration. Its examples are documentation claims, not an exhaustive conformance test. For Rasputin, publish only implemented protocols and supported request options; do not imply that Chat Completions alone supports clients requiring Responses or Messages.

## How training differs from inference

### The live configuration flow

**Observed live.** Train is `/studio`, with Configure, Current Run, and History tabs. Current Run was disabled without an active job. The page groups Model, Dataset, Parameters, and Configuration into rounded cards, with a Run preview and explicit readiness blockers.

The observed defaults were QLoRA, 60 steps, context 2048, and learning rate 0.0002. Parameters have Simple and Advanced modes. The dataset area offers browsing, upload, subset/train/evaluation selection, and advanced options. The preview summarizes method, steps, effective batch, context, learning rate, hardware, and missing inputs. Start remained disabled until model and dataset were chosen. These defaults are observations, not recommendations for all models.

The Unsloth upload control advertises several document and tabular formats. That UI text does not prove each ingestion path works, and it is not a reason to advertise those formats before Rasputin implements them.

### Worker, artifacts, and resources

**Observed shipped source.** `backend/core/training/training.py:696` selects multiprocessing `spawn`; `worker.py:4` explains the fresh-interpreter boundary used when switching Transformers environments. Training has separate start requests/acknowledgement, preflight, start/stop, status, metrics, and progress contracts. Model/data identity and resume provenance have their own validation. Existing inference and competing GPU-intensive jobs are considered before training obtains resources.

`backend/routes/training.py:1004` rejects a GGUF request with a structured error. `:1304` rejects GGUF-only local models. A downloaded inference quantization therefore cannot become a training base by changing the UI label. A supported original model checkpoint, configuration, tokenizer, and appropriate weights are needed; adapter continuation additionally requires a compatible base. `backend/models/training.py:167` distinguishes LoRA/QLoRA, full fine-tuning, and continued pretraining.

**Observed Rasputin environment.** A module-discovery probe in the repository's required `.venv` found no torch, unsloth, transformers, trl, peft, or datasets. This is an environment inventory, not an installation or execution test. Native Windows training is supported by current [official Windows documentation](https://unsloth.ai/docs/get-started/install/windows-installation); Rasputin does not need to introduce a container or WSL requirement.

### Implementation contract for Rasputin

These are proposed design requirements, not claims of completed implementation:

1. Own a separate optional training runtime so model-training packages do not destabilize the packaged inference backend. Detect its actual versions and acceleration before offering Start.
2. Accept supported trainable local checkpoints and validated datasets. Reject GGUF-only bases, missing tokenizer/weights, unsupported methods, and unavailable acceleration before creating a running job. Do not silently fetch a remote base.
3. Begin with supervised adapter fine-tuning over a bounded text dataset. Preserve a clear distinction between supported LoRA/QLoRA and unimplemented full training, continued pretraining, vision, or reinforcement learning.
4. Use a backend-owned job with stable identity, observable queued/starting/running/completed/failed/cancelled states, metrics, bounded logs, and owned worker cancellation. Navigating away must not own job lifetime.
5. Coordinate inference and training GPU ownership. Do not silently kill an active inference response to make room.
6. Save adapters with base-model/configuration provenance. Adapter output is not automatically a new GGUF: merging/export and subsequent model registration require their own supported path.
7. Keep local-only model/data loading and `trust_remote_code=False` as the initial supported boundary. Loading arbitrary model repository code is a separate execution decision, not a prerequisite to adding a Train tab.

The [official security explanation](https://unsloth.ai/blog/security) also treats custom repository code and account/tool permissions as explicit boundaries. Its described controls are vendor claims; this study did not audit them.

### Rasputin's initial worker is a deliberate adaptation

The scoped Rasputin implementation uses a separately configured maintainer interpreter through `RASPUTIN_TRAINING_PYTHON`, standard Transformers/PEFT/TRL, local safetensors checkpoints, a bounded text dataset, CUDA, and LoRA. It does not copy Unsloth's optimized training engine, multi-environment management, QLoRA quantization, full fine-tuning, or checkpoint-family coverage. No Unsloth speed or VRAM claim applies to this worker. The packaged inference backend must remain usable when the optional interpreter or packages are absent. Completing this source implementation does not certify an actual training run or make training a bundled installer capability.

The worker API uses `SFTConfig(max_length=..., dataset_text_field="text")`, `SFTTrainer(processing_class=...)`, and PEFT `LoraConfig(target_modules="all-linear")`. These names are supported by [versioned TRL 0.23.1 documentation](https://huggingface.co/docs/trl/v0.23.1/en/sft_trainer), [TRL 0.27.2 documentation](https://huggingface.co/docs/trl/v0.27.2/en/sft_trainer), and [PEFT 0.18.0 documentation](https://huggingface.co/docs/peft/v0.18.0/package_reference/lora). Older examples using `max_seq_length` directly on the trainer are not the same API. All-linear LoRA describes adapter placement; it does not itself provide 4-bit QLoRA.

For reproducibility, the current installed Unsloth environment's package metadata identifies torch `2.13.0+cu130`, Transformers `5.5.0`, TRL `0.23.1`, PEFT `0.18.1`, and datasets `4.3.0`. Its TRL package metadata requires Transformers >=4.56.1, accelerate >=1.4.0, and datasets >=3.0.0. Those are metadata constraints, not proof of a safe standalone combination; Unsloth may patch or switch environments. The installed TRL source confirms the requested field/signature names at `trl/trainer/sft_config.py:152,182` and `trl/trainer/sft_trainer.py:601`.

No existing interpreter is certified for Rasputin training by this inspection. Do not set `RASPUTIN_TRAINING_PYTHON` to Unsloth's environment automatically or modify its dependencies. Select and pin a separate environment, then verify imports, CUDA operation, worker signature compatibility, and a tiny local-only training job before recording a supported version matrix. A tiny generated random-weight model can exercise mechanics without downloading a checkpoint, but it does not establish useful fine-tuning quality or production-model compatibility.

### Bounded worker mechanics probe

An explicitly selected diagnostic used the installed interpreter without changing its dependencies, application data, or Rasputin runtime configuration. Both GPUs had more than 10 GiB free before the probe. The helper generated a random two-layer, 32-dimensional GPT-2 model with 30,080 parameters, a tiny WordLevel tokenizer, and three synthetic JSONL examples in isolated session scratch. The safetensors weights occupied 122,920 bytes. Network/model downloads were disabled through Hugging Face offline flags; caches and temporary files were redirected to scratch, with Python bytecode writing disabled.

Model generation succeeded in 28.64 seconds. The actual Rasputin training worker was invoked for one optimizer step, rank 4, context 128, with a hard 60-second process deadline. It exited 1 after 49.80 seconds, following local checkpoint loading and parsing all three dataset records. It emitted a structured `ImportError` failure and produced no adapter files. It did not reach successful training. No timeout termination was necessary. This is useful negative compatibility evidence for the selected environment, not training certification.

A second bounded diagnostic called the same worker's `run()` function with traceback capture and exited 1 after 36.50 seconds. It localized the failure to adapter injection: TRL `prepare_peft_model` calls PEFT `get_peft_model`, whose optional TorchAO dispatcher imports `LinearActivationQuantizedTensor` from `torchao.quantization`; that symbol is unavailable in the installed TorchAO package. This is an installed dependency mismatch before `trainer.train()`, rather than a dataset/weight-format or GPU-memory failure. No target package was patched, installed, or removed to make the probe pass. The required next gate is a separately provisioned, pinned compatible runtime and a successful repeat of the tiny worker test.

## Performance evidence and remaining work

The installed window navigated among Chat, API, settings, Train, and Library and produced readable accessible trees and screenshots. The observed form states settled between Computer Use calls. This establishes that those pages rendered on this workstation. It does not establish first-paint time, frame rate, memory efficiency, inference throughput, training speed, accessibility compliance, or responsive behavior at other widths.

Computer Use call durations include UI automation, host permission, transport, capture, and model/tool scheduling. They are not application latency measurements. No throughput claim or Rasputin-versus-Unsloth speed comparison is supported here. In particular, package-level training speed claims cannot be transferred to this workstation or to a new Rasputin runner.

Useful future performance scenarios are cold/warm navigation with fixed build and viewport; Hub search with network timing and cache state; sidebar drag with frame/long-task traces; API time-to-first-token and decoding tokens/second for a fixed model/settings; and training step time/peak VRAM using a fixed checkpoint/dataset/seed. Those runs need explicit workload selection and resource ownership. They were not executed as a side effect of UI research.

| Investigation question | Result |
| --- | --- |
| Installed app identity and relation to prior static study | Answered: executable and packaged frontend hashes match. |
| Actual sidebar appearance, destinations, resize control | Answered by live window observation; resize behavior itself untested. |
| Library versus model inventory | Answered live plus prior static Hub evidence. |
| API monitor and key-management UX | Answered live; no credential mutation performed. |
| Key lifecycle and compatibility architecture | Answered in selected shipped source and official docs; full protocol conformance untested. |
| Training configuration and blockers | Answered live; no training started. |
| Training artifacts and worker architecture | Answered in selected shipped source; bounded Rasputin worker probe reached adapter injection but failed on an installed PEFT/TorchAO mismatch. Successful training/resume/cancel behavior remains unverified. |
| UI and ML performance | Partially answered: successful navigation only; controlled benchmarks remain open. |

**TL;DR:** Unsloth's useful pattern is a coherent workstation around explicit artifacts, API credentials, observable jobs, and resource ownership. Its appearance can guide Rasputin; its performance and training capabilities still require Rasputin-specific implementation and evidence.
