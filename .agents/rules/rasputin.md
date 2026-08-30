---
trigger: always_on
---

## Rasputin native product direction

Rasputin is a Windows native AI workstation. The installed Electron application owns a
packaged backend and bundled llama.cpp. The source Native Host is a separate browser/headless
workflow. Models are GGUF artifacts served by native child processes. Docker infrastructure is retired.

Read `docs/CODEX_ONBOARDING.md`, `docs/DEPLOYMENT_MATRIX.md`, and
`docs/WRAPPER_RUNTIME_CONTRACT.md` for implementation-grounded instructions.

### Model workflow

Discover → select exact compatible GGUF → download/import → verify/register →
plan native placement → load with llama.cpp → infer → monitor → stop.

Keep installed files separate from loaded processes. Use the existing catalog, acquisition,
registry, load-profile, runtime-service, and provider boundaries. Prefer a fitting single GPU;
only use combined devices when supported by the artifact, runtime, and hardware evidence.

Native model actions use the native runtime provider. Old managed entries should offer GGUF
recovery. Unsupported artifacts must show a clear blocker and next action. There is no Docker
control feature in the current product; do not document one or revive retired infrastructure.

### Ownership and safety

- Identify the live owner from `desktop-runtime.json` or `native-host.json`, not an assumed port.
- Never run two backends against the same store or delete an ownership record to bypass a live owner.
- An installed package must be rebuilt/updated to receive source changes; restarting source does
  not update installed binaries.
- Respect existing user approval for the requested restart/update; ask before unrelated or
  destructive operations. Preserve accounts, models, workspaces, and network configuration.
- Use isolated native data and processes for tests. Do not start retired infrastructure.
- Skills are declarative instructions; governed file, Git, and other tool checks still apply.
  Native Windows Host Shell remains fail-closed pending a verified AppContainer runner.
- Record validation, resource estimates, progress, clear errors, lifecycle state, and audit evidence.
  A plan or health response is not proof that a model can produce an answer.

### Retained code and future work

WarSat-named modules include shared hardware/runtime services and legacy container providers.
Their names do not make containerization the product architecture. Do not require every action
to pass through a container deployment console or add Kubernetes/remote-node work to native fixes.
Preserve legacy behavior when unrelated, but document it as compatibility code rather than the
current installation or model-loading path.
