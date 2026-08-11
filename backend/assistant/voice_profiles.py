"""Discoverable local STT/TTS pairing profiles.

Profiles describe the transport and registration contract only. They do not
name a remote provider, download weights, start a runtime, or open audio
devices. Operators can use the profile with any local gateway that implements
the documented OpenAI-compatible audio paths.
"""

from __future__ import annotations

from copy import deepcopy


VOICE_PROFILE_CONTRACT_VERSION = "0.1"

_PROFILES = (
    {
        "id": "local-openai-compatible-voice-v1",
        "label": "Local OpenAI-compatible voice pair",
        "description": "Pair a local Whisper-compatible STT gateway with a local Piper-compatible TTS gateway.",
        "local_only": True,
        "roles": {
            "speech_to_text": {
                "registration": {
                    "role": "speech_to_text",
                    "provider": "whisper",
                    "runtime": "local-voice",
                    "base_url_example": "http://127.0.0.1:9911/v1",
                },
                "request": {
                    "method": "POST",
                    "path": "/audio/transcriptions",
                    "content_type": "multipart/form-data",
                    "required_fields": ["file", "model"],
                    "response_field": "text",
                },
            },
            "text_to_speech": {
                "registration": {
                    "role": "text_to_speech",
                    "provider": "piper",
                    "runtime": "local-voice",
                    "base_url_example": "http://127.0.0.1:9912/v1",
                },
                "request": {
                    "method": "POST",
                    "path": "/audio/speech",
                    "content_type": "application/json",
                    "required_fields": ["model", "input", "response_format"],
                    "response": "audio bytes",
                },
            },
        },
        "health_check": {
            "operation": "model_registry_test",
            "required_before_voice_turn": True,
            "side_effects": False,
        },
        "policy": {
            "remote_endpoints_allowed": False,
            "microphone_access": "caller_supplied_audio_only",
            "speaker_access": "response_stream_only",
            "models_started": False,
        },
    },
)


def list_profiles() -> dict:
    """Return a JSON-safe, immutable-by-convention profile catalog."""

    return {
        "contract_version": VOICE_PROFILE_CONTRACT_VERSION,
        "local_only": True,
        "profiles": deepcopy(list(_PROFILES)),
        "next_actions": [
            "Register one local speech_to_text endpoint and one local text_to_speech endpoint.",
            "Run each model's health check before starting a voice turn.",
            "Use the voice readiness route to verify both roles without opening audio devices.",
        ],
    }


__all__ = ["VOICE_PROFILE_CONTRACT_VERSION", "list_profiles"]
