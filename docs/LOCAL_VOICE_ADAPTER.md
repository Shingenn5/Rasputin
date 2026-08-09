# Local voice adapter

Rasputin now has a first local voice transport for registered speech models.
The adapter is intentionally device-free: it accepts caller-supplied audio for
transcription and returns synthesized audio as an HTTP response. Microphone and
speaker ownership stays with the desktop/browser layer until a later, explicit
device adapter is approved.

## Endpoints

After authentication:

```text
POST /api/assistant/voice/transcribe?modelKey=<speech-to-text-model>
Content-Type: audio/wav
X-Filename: sample.wav
<audio bytes>
```

The response is JSON containing the bounded transcript and
`contractVersion: "0.1"`.

```text
POST /api/assistant/voice/synthesize
Content-Type: application/json
{"modelKey":"local-piper","text":"Hello from Rasputin","responseFormat":"wav"}
```

The response body is the audio stream. `X-Rasputin-Voice-Contract` and
`X-Rasputin-Voice-Model` identify the adapter and selected model.

## Model contract and safety

Models must be registered with role `speech_to_text` or `text_to_speech`, be
enabled, and expose a local base URL. The adapter calls the common local
OpenAI-compatible paths `/v1/audio/transcriptions` and `/v1/audio/speech`.
Remote URLs are rejected even when general remote-model access is enabled.

Payloads are bounded at 25 MiB for input audio, 16 MiB for synthesized output,
and 8,000 characters for synthesis text. The adapter never opens a device,
executes a command, creates an approval, or starts a model container. The
existing `POST /api/assistant/voice-preview` endpoint remains the place to
validate a complete speech-to-text → main model → text-to-speech model pack
before a voice turn is attempted.
