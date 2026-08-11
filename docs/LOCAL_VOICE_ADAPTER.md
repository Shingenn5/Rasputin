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

For one complete local conversation turn, the authenticated caller can send
the same caller-supplied audio to:

```text
POST /api/assistant/voice/turn
Content-Type: audio/wav
X-Filename: sample.wav
<audio bytes>
```

The JSON response contains the bounded `transcript`, Rasputin `response`, a
`conversationId`, and base64-encoded `audioBase64` with its `contentType`.
This route uses registered `speech_to_text`, `main`, and `text_to_speech`
models, persists the turn to an owner-scoped Assistant chat, and advertises
contract version `0.2`. It never starts host actions or mutates a workspace.

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

## Browser push-to-talk

The Assistant view now includes a push-to-talk console. It requests
`getUserMedia({audio:true})` only after the operator presses **Start push to
talk**, records at most 60 seconds with `MediaRecorder`, and sends the caller
supplied blob to the authenticated transcription route. The returned
blob to the authenticated voice-turn route. The local Assistant response and
returned audio are shown in the transcript/response view and HTML audio
player; no microphone is opened on page load and no host command is started by
the voice turn. Browser permission prompts, microphone hardware, registered
speech models, and speaker output still require a live operator verification.
