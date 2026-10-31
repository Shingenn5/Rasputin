# Native LoRA runtime verification

## Verified scope — 2026-10-31

The source application completed an actual CUDA LoRA run using its authenticated
training API, worker subprocess, job monitor, export endpoint, and cancellation
endpoint. The API harness used a real login and session cookie through the ASGI
test client. It did not override authorization or mock training, CUDA, weights,
the worker, or adapter export. Application state, caches, dataset, and runtime
were in external disposable storage. The installed application's data and
processes were not changed.

The verified environment is CPython 3.12.13 on Windows x64, PyTorch 2.9.1+cu128,
Transformers 4.57.1, PEFT 0.17.1, TRL 0.24.0, Datasets 4.3.0, and Accelerate
1.11.0. No TorchAO was installed. `pip check` reported no broken requirements.
The complete package versions are pinned in
[`runtime/training/requirements-windows-x64-cu128.txt`](../runtime/training/requirements-windows-x64-cu128.txt).
This environment is independent of the application's lightweight `.venv`.

The base was official `Qwen/Qwen3-0.6B` at revision
`c1899de289a04d12100db370d81485cdf75e47ca`. Its safetensors SHA-256 was checked
against Hugging Face's file metadata. Only original tokenizer/configuration,
license, and safetensors assets were acquired. The worker then ran offline with
`local_files_only=True`, `trust_remote_code=False`, and `use_safetensors=True`.

## Actual outcomes

- On the RTX 5060 Ti, the worker completed four optimizer steps using 16 synthetic
  text examples, sequence length 128, rank 8, and learning rate 0.0002. Reported
  training loss decreased from 6.2874 to 4.4599 before final summary telemetry.
- The authenticated export contained the adapter weights/configuration and
  tokenizer assets, with no dataset. A second run was cancelled after reporting
  its first real training step. Its status became `cancelled` and its owned
  process was removed from the active-worker registry.
- The exported adapter loaded with the original base through PEFT on CUDA.
  All 392 adapter tensors were finite; trained `lora_B` weights were nonzero.
  For the synthetic evaluation text, loss changed from 6.273619 to 3.801028,
  and the maximum final-position logit change was 6.583984. These measurements
  demonstrate an effective adapter for this fixture, not general model quality.

The run exposed a progress-monitor bug: TRL's final summary has no `loss`, and
the monitor overwrote the last finite value with `null`. The monitor now preserves
the last finite loss when a progress event omits loss or supplies null, nonfinite,
or boolean values. The training regression test covers these events and verifies
that the job endpoint remains JSON-serializable. All 13 training tests pass.
A second actual two-step run through the authenticated API verified the fix:
the completed job retained its last finite loss, 4.9374, after final summary
telemetry. It also produced a valid adapter export.
The combined backend/native-validation/agent-evidence/training gate ran 193
tests: 187 passed, with the same six existing legacy native-shell expectation
failures. Documentation validation passed for 52 Markdown files.

## Maintainer reproduction environment

Provision only into a separate absolute directory outside the repository and
live Rasputin data. Do not install these packages into the backend build/runtime.
With the repository's CPython 3.12 interpreter, create a disposable venv. Then run
its `Scripts/python.exe` with:

```text
-m pip --isolated install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128 --only-binary=:all:
-m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: -r runtime/training/requirements-windows-x64-cu128.txt
-m pip --isolated check
```

Set `RASPUTIN_TRAINING_PYTHON` to that venv's absolute interpreter path and
`RASPUTIN_DATA_DIR` to fresh external application storage before importing the
backend. Select a suitable CUDA device for the verification process. Use the
pinned local base and a synthetic JSONL dataset through the normal authenticated
`/api/training/preflight` and `/api/training/jobs` endpoints. Poll
`/api/training/jobs`, inspect the completed adapter export, and stop a separate
active run with `/api/training/jobs/{id}/cancel`. Never reuse the installed app's
data or stop an inference process owned by another application.

Evidence retained for this session includes `model-acquisition.json`,
`verified-environment.txt`, `service-report.json`, `adapter-evaluation.json`,
the exported adapter, synthetic dataset, and worker artifacts. None of the
weights, dataset, credentials, logs, or machine paths are committed.

## Remaining product work

This verifies source training and direct local PEFT inference. It does not
verify the installed Electron training workflow, app-managed training-runtime
acquisition, clean-machine setup, general training quality, or using the adapter
in Rasputin's native llama.cpp Chat workflow. Packaged builds still require a
separate configured training runtime. End-user provisioning, base-model intake,
adapter/base identity checks, evaluation UX, and native serving integration remain
acceptance gates for the combined workstation goal.

## Primary references

- [Official PyTorch Windows CUDA installation matrix](https://pytorch.org/get-started/previous-versions/#v291)
- [TRL 0.24 SFT trainer and PEFT integration](https://huggingface.co/docs/trl/v0.24.0/en/sft_trainer)
- [Official Qwen3-0.6B model and Transformers support](https://huggingface.co/Qwen/Qwen3-0.6B)
