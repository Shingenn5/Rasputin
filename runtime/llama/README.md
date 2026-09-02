# Native llama.cpp runtime manifest

The manifest pins Windows llama.cpp CPU and CUDA builds available to Desktop.
The packaging check validates manifest identity, approved download origins,
asset sizes, and SHA-256 values without downloading runtime binaries.

On first model load, Rasputin detects local GPU/driver compatibility, chooses
one matching runtime, downloads only that runtime's assets, verifies every
SHA-256, extracts safely, smoke-checks llama-server, and activates it. Machines
without a compatible NVIDIA runtime receive the CPU build. Later loads reuse
the installed runtime.

The manifest is also retained for runtime identity and compatibility selection.
Development checkouts may still use the repository's native Python launch path,
but packaged Electron resolves its engine from the verified user-local runtime
store.
