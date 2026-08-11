# Model resource manifest

Rasputin catalog entries now carry a versioned `resourceManifest` under the
`rasputin.model-resource.v1` schema. The manifest is deliberately portable:
it can be stored with a model card, inspected by the resource broker, or sent
to the UI without coupling it to one inference runtime.

## What it records

- `identity`: model id, optional checksum/revision, license, and source.
- `weights`: parameter count, canonical quantization name, bits-per-weight,
  and a conservative weight-memory estimate when the inputs are sufficient.
- `runtimeEnvelope`: the catalog's total VRAM estimate and its confidence.
- `kvCache`: context window and measured/estimated KV-cache evidence. New
  catalog entries remain `unmeasured` until a benchmark records this data.
- `backends`: declared runtime protocols and their support status.
- `placement`: the default largest-fitting-single-GPU policy and whether the
  selected runtime may combine VRAM. Combined capacity never implies vLLM
  tensor-parallel compatibility.
- `roleFit`: purpose, capabilities, and recommended strength profile.
- `fit`: dynamic hardware evidence, including score, label, available VRAM,
  headroom, basis, and blocked reasons.

The legacy catalog fields (`vramEstimateGb`, `fitScore`, and so on) remain in
the response for compatibility. They are enriched by the manifest rather than
silently reinterpreted. `resource_manifest.validate_manifest()` checks the
stable sections before future persistence or broker admission uses them.

## Evidence boundary

The manifest does not claim that a model has been loaded successfully. A
catalog estimate is heuristic, and `kvCache.status=unmeasured` is intentional.
Slice 5 will add measured runtime certificates; only those certificates should
upgrade the manifest's confidence or authorize runtime-specific multi-GPU
placement.
