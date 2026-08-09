"""Local-only speech adapters for the assistant voice vertical slice.

The adapters speak the OpenAI-compatible ``/audio/transcriptions`` and
``/audio/speech`` contracts used by common local Whisper and Piper gateways.
They never open a microphone or speaker; the API layer owns authenticated
request/response handling and the operator decides which local model endpoint
to register.
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.request
from typing import Any

from backend.core import security
from backend.core.response import AppError
from backend.models import registry as model_registry


VOICE_CONTRACT_VERSION = "0.1"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 8000
MAX_SYNTHESIS_BYTES = 16 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 90
SUPPORTED_AUDIO_FORMATS = frozenset({"wav", "mp3", "opus", "aac", "flac"})


def capabilities() -> dict[str, Any]:
    return {
        "contract_version": VOICE_CONTRACT_VERSION,
        "transport": "openai_compatible_local_audio_v1",
        "transcription_path": "/audio/transcriptions",
        "synthesis_path": "/audio/speech",
        "local_only": True,
        "microphone_access": "caller_supplied_audio_only",
        "speaker_access": "response_stream_only",
        "max_audio_bytes": MAX_AUDIO_BYTES,
        "max_text_chars": MAX_TEXT_CHARS,
        "supported_response_formats": sorted(SUPPORTED_AUDIO_FORMATS),
    }


def resolve_model(model_key: str | None, role: str) -> dict[str, Any]:
    key = str(model_key or "").strip()
    model = model_registry.get_model(key) if key else None
    if model is None and not key:
        model = next(
            (
                item for item in model_registry.all_models()
                if item.get("role") == role and item.get("enabled", True)
            ),
            None,
        )
    if not model:
        raise AppError("voice_model_missing", f"No enabled {role} model is registered.", 409)
    if str(model.get("role") or "") != role:
        raise AppError("voice_model_role_mismatch", f"Model '{model.get('key') or key}' is not registered for {role}.", 409)
    if not model.get("enabled", True):
        raise AppError("voice_model_disabled", "The selected voice model is disabled.", 409)
    if str(model.get("runtime_status") or "").lower() in {"unhealthy", "stopped", "unreachable", "error"}:
        raise AppError("voice_model_unhealthy", "The selected voice model is not reachable.", 409)
    return dict(model)


def _base_url(model: dict[str, Any]) -> str:
    base = str(model.get("base_url") or model.get("baseUrl") or "").strip().rstrip("/")
    if not base:
        raise AppError("voice_model_endpoint_missing", "The selected voice model has no local base URL.", 409)
    if not security.is_local_url(base):
        raise AppError("voice_model_not_local", "Voice adapters only support local model endpoints.", 403)
    security.require_local_url(base)
    return base


def _bounded_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise AppError("voice_text_missing", "Text to synthesize is required.", 400)
    if len(text) > MAX_TEXT_CHARS:
        raise AppError("voice_text_too_large", f"Text to synthesize is limited to {MAX_TEXT_CHARS} characters.", 413)
    return text


def _multipart_form(model_name: str, audio: bytes, filename: str, mime_type: str) -> tuple[bytes, str]:
    boundary = f"----rasputin-{uuid.uuid4().hex}"
    chunks = []

    def field(name: str, value: str) -> None:
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode("utf-8"),
            b"\r\n",
        ])

    field("model", model_name)
    safe_name = os.path.basename(str(filename or "audio.wav")) or "audio.wav"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'.encode(),
        f"Content-Type: {mime_type or 'application/octet-stream'}\r\n\r\n".encode(),
        audio,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _json_error(exc: urllib.error.HTTPError, operation: str) -> AppError:
    # Do not reflect an adapter's response body into the user-facing error;
    # local model gateways can include prompts, paths, or other private data.
    return AppError("voice_adapter_failed", f"Local voice {operation} adapter returned HTTP {exc.code}.", 502)


def transcribe(model: dict[str, Any], audio: bytes, filename: str = "audio.wav", mime_type: str = "audio/wav") -> dict[str, Any]:
    if not isinstance(audio, (bytes, bytearray)) or not audio:
        raise AppError("voice_audio_missing", "Audio input is required.", 400)
    if len(audio) > MAX_AUDIO_BYTES:
        raise AppError("voice_audio_too_large", f"Audio input is limited to {MAX_AUDIO_BYTES} bytes.", 413)
    body, content_type = _multipart_form(str(model.get("model") or model.get("key") or ""), bytes(audio), filename, mime_type)
    request = urllib.request.Request(
        f"{_base_url(model)}/audio/transcriptions",
        data=body,
        headers={"Accept": "application/json", "Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _json_error(exc, "transcription") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AppError("voice_adapter_unreachable", f"Local voice transcription adapter is unreachable: {exc}", 503) from None
    except (ValueError, json.JSONDecodeError):
        raise AppError("voice_adapter_invalid_response", "Local transcription adapter returned invalid JSON.", 502) from None
    if not isinstance(payload, dict):
        raise AppError("voice_adapter_invalid_response", "Local transcription adapter returned an invalid object.", 502)
    text = str((payload or {}).get("text") or (payload or {}).get("transcript") or "").strip()[:MAX_TEXT_CHARS]
    if not text:
        raise AppError("voice_adapter_empty_transcript", "Local transcription adapter returned no transcript.", 502)
    return {
        "contract_version": VOICE_CONTRACT_VERSION,
        "operation": "transcribe",
        "model_key": model.get("key"),
        "text": text,
        "stage": "transcribed",
        "audio_io_started": False,
        "microphone_access": "caller_supplied_audio_only",
    }


def synthesize(model: dict[str, Any], text: str, voice: str | None = None, response_format: str = "wav") -> dict[str, Any]:
    clean_text = _bounded_text(text)
    fmt = str(response_format or "wav").strip().lower().lstrip(".")
    if fmt not in SUPPORTED_AUDIO_FORMATS:
        raise AppError("voice_format_invalid", f"Response format must be one of: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}.", 400)
    payload = {
        "model": str(model.get("model") or model.get("key") or ""),
        "input": clean_text,
        "response_format": fmt,
    }
    if voice:
        payload["voice"] = str(voice).strip()[:120]
    request = urllib.request.Request(
        f"{_base_url(model)}/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": f"audio/{fmt}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            content = response.read(MAX_SYNTHESIS_BYTES + 1)
            headers = getattr(response, "headers", None)
            get_content_type = getattr(headers, "get_content_type", None)
            content_type = get_content_type() if callable(get_content_type) else (headers.get("Content-Type") if headers else None)
    except urllib.error.HTTPError as exc:
        raise _json_error(exc, "synthesis") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AppError("voice_adapter_unreachable", f"Local voice synthesis adapter is unreachable: {exc}", 503) from None
    if len(content) > MAX_SYNTHESIS_BYTES:
        raise AppError("voice_audio_too_large", f"Synthesized audio is limited to {MAX_SYNTHESIS_BYTES} bytes.", 502)
    if not content:
        raise AppError("voice_adapter_empty_audio", "Local synthesis adapter returned no audio.", 502)
    return {
        "contract_version": VOICE_CONTRACT_VERSION,
        "operation": "synthesize",
        "model_key": model.get("key"),
        "response_format": fmt,
        "content_type": content_type or mimetypes.guess_type(f"speech.{fmt}")[0] or "application/octet-stream",
        "audio": content,
        "stage": "synthesized",
        "speaker_access": "response_stream_only",
    }
