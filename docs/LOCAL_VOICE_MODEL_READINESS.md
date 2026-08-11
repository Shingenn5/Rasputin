# Local voice model readiness

Rasputin's voice path is intentionally split into two operator-verifiable
boundaries:

1. `GET /api/assistant/voice/models` reports whether registered
   `speech_to_text` and `text_to_speech` models have local endpoints and known
   runtime reachability.
2. `POST /api/assistant/voice/turn` performs one caller-supplied-audio
   STT -> Assistant -> TTS turn after the operator has selected or registered
   compatible models.

The readiness route never starts a container, calls a model endpoint, opens a
microphone, or opens a speaker. It returns only redacted model identity and
endpoint state:

- `ready` means the registry has an enabled local endpoint whose runtime status
  is already `reachable`.
- `needs_health_check` means the endpoint is local and enabled, but its runtime
  status is unknown or still starting. Run the model's normal health check
  before relying on a voice turn.
- `blocked` means a required role is missing, disabled, unreachable, missing a
  local endpoint, or points at a remote endpoint.

The response deliberately omits endpoint URLs, API keys, and provider-private
fields. `local_only` remains true even if the global model settings are later
changed; voice adapters do not permit remote endpoints.

This is model registration evidence, not hardware certification. Browser
microphone permission, speaker playback, and a real end-to-end voice turn are
still separate acceptance checks.
