# Model discovery and coding-harness hosting

Verified 2026-09-18 against isolated source Native Host and fresh Desktop-mode stores.

## Changes

- Native catalog searches request GGUF repositories. Discover defaults to text-generation
  models; exact repository references remain inspectable. Non-GGUF references report
  `GGUF required` instead of looking like downloadable native models.
- Parameter estimates use Hugging Face GGUF/Safetensors metadata before name heuristics,
  including models named in millions of parameters. Estimates are not load guarantees.
- Search and local scans run off the HTTP event loop. Manual scans register valid GGUF
  files, skip companion files and later shards, and preserve existing registrations.
- Failed detail requests display their error instead of silently becoming an empty variant list.
- Serving advertises only reachable models. It exposes model IDs and the gateway base URL,
  with copyable Pi and OpenCode Chat Completions configurations and environment credentials.
- Successful native loads record the runtime's effective context. Pi configuration requires
  more than 4,096 context tokens because the tested Pi client reserves that amount.

## Live evidence

- The reported `cross-encoder/ms-marco-MiniLM-L6-v2` repository returns no GGUF files.
  Exact lookup now identifies its unsupported format. It is excluded from native browsing.
- Fresh Desktop-mode UI: Discover → search `bartowski/SmolLM2-135M-Instruct-GGUF` →
  Download selected the Q4_K_M variant. All 105,454,432 bytes downloaded, verification
  completed, and the artifact registered in My Models.
- Native startup discovered an existing Qwen3-0.6B Q8_0 file without downloading it again.
- That model loaded with llama.cpp, and Rasputin served authenticated streaming chat.
  Missing-key requests returned HTTP 401.
- A real function call and returned tool result survived a complete gateway round trip.
- Current Pi CLI used the UI-generated configuration and Rasputin key to read a scratch
  file through its own read tool and return the exact contents (exit 0). The model was
  loaded with 16,384 context tokens. This is protocol/tool-loop evidence, not certification
  of that small model for general coding work.
- Pi/OpenCode configuration copy controls were exercised in Chromium. The new connection
  section was inspected at 1440, 1024, and 390 px. OpenCode itself was not executed.

## Regression scope

- Focused Python: 44 tests and 19 subtests passed.
- Focused JavaScript: 33 tests passed. Frontend production build passed.
- Backend smoke: 161 passed, 7 failed. All seven failures reproduced with this change's
  backend modules replaced in memory by their HEAD versions, retaining the other existing
  workspace changes. Six concern existing coding-validation expectations; one expects a
  single catalog entry despite existing local cache entries.
- Existing unrelated workspace edits were preserved and excluded from this commit.

## Harness setup

Load the desired model, open Models → Serving, generate an API key, and copy the
configuration for the selected model. Set `RASPUTIN_API_KEY` in the terminal launching
the harness. Merge the copied config into `opencode.json` or `~/.pi/agent/models.json`.
Keep Rasputin and the model running. The base URL is for the current running instance;
if its port changes, copy the new URL.

References: [OpenCode custom providers](https://opencode.ai/docs/providers),
[Pi custom models](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md).
