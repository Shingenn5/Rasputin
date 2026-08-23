# Native llama.cpp runtime manifest

This directory contains only the pinned `manifest.json` contract. It does not
bundle `llama-server.exe` or any runtime binaries. On first use, Rasputin Desktop
selects a CPU or compatible CUDA asset, downloads it over HTTPS, verifies its
SHA-256, runs `llama-server --version`, and records the install under the user
data directory.

The same manifest is used from a development checkout and from packaged
Electron resources. If installation is incomplete or the active executable is
missing, the runtime status remains repairable instead of reporting a bundled
runtime.
