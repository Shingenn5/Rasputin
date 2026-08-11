"""HTTP surface for Rasputin identity and approval-aware orchestration."""

import asyncio
import base64

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from backend.api.core import CamelModel, current_user, require_member
from backend.assistant import runtime
from backend.assistant import voice
from backend.assistant import voice_models
from backend.core import audit
from backend.core import workspace
from backend.core.response import AppError, ok
from backend.engine import context as context_governor
from backend.models import providers as model_providers


router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ProfilePatchIn(CamelModel):
    display_name: str | None = None
    persona: dict | None = None
    mission: str | None = None
    voice_policy: dict | None = None


class PlanPreviewIn(CamelModel):
    objective: str
    workspace_path: str | None = None
    session_id: str | None = None
    context_query: str | None = None
    context_capsule_id: str | None = None
    model_pack: dict | None = None
    model_pack_id: str | None = None
    agents: list[dict] = Field(default_factory=list)
    requested_operations: list[str] = Field(default_factory=list)
    include_sensitive: bool = False


class CommandPreviewIn(CamelModel):
    command: str
    workspace_path: str | None = None


class PlanReviewIn(CamelModel):
    note: str | None = ""


class ModelPackIn(CamelModel):
    pack_id: str
    version: str = "0.1"
    entries: list[dict] = Field(default_factory=list)


class HandoffIn(CamelModel):
    operation: str


class VoicePreviewIn(CamelModel):
    model_pack: dict | None = None
    model_pack_id: str | None = None
    input_model_key: str | None = None
    main_model_key: str | None = None
    output_model_key: str | None = None
    conversation_id: str | None = None


class VoiceSynthesisIn(CamelModel):
    text: str
    model_key: str | None = None
    voice: str | None = None
    response_format: str = "wav"


VOICE_TURN_CONTRACT_VERSION = "0.2"


def _voice_system_prompt(profile: dict) -> str:
    persona = profile.get("persona") or {}
    summary = str(persona.get("summary") or "A local, respectful assistant.").strip()[:1000]
    display_name = str(profile.get("display_name") or "Rasputin").strip()[:80]
    return (
        f"You are {display_name}, a local voice conversation layer. {summary} "
        "Answer clearly and briefly for spoken playback. Do not execute commands, change files, "
        "open applications, or start model containers from a voice turn. If the user asks for "
        "an action, explain that it must be converted into an explicit reviewed plan first."
    )


class ContextPreviewIn(CamelModel):
    objective: str = ""
    workspace_path: str | None = None
    session_id: str | None = None
    context_query: str | None = None
    include_sensitive: bool = False
    expires_in_seconds: int = Field(default=3600, ge=300, le=604800)


def _workspace_for_request(req: PlanPreviewIn, user: dict) -> str:
    workspace_ref = req.workspace_path or workspace.get_active(
        user["username"], user.get("role") == "admin"
    ).get("active_path") or "."
    workspace.require_user_access(workspace_ref, user["username"], "viewer", user.get("role") == "admin")
    return workspace_ref


def _assert_sensitive_allowed(req: PlanPreviewIn, user: dict) -> None:
    if req.include_sensitive and user.get("role") != "admin":
        raise PermissionError("sensitive context preview requires administrator access")


@router.get("/capabilities")
async def assistant_capabilities(_user=Depends(current_user)):
    payload = runtime.capabilities()
    payload["voice_models"] = voice_models.readiness()
    return ok(payload)


@router.get("/voice/models")
async def assistant_voice_models(_user=Depends(require_member)):
    """Return redacted local STT/TTS registration and readiness evidence."""

    return ok(voice_models.readiness())


@router.post("/command-preview")
async def assistant_command_preview(req: CommandPreviewIn, _user=Depends(require_member)):
    workspace_ref = _workspace_for_request(req, _user)
    return ok(runtime.route_command_preview(req.command, workspace_ref=workspace_ref))


@router.post("/voice-preview")
async def assistant_voice_preview(req: VoicePreviewIn, _user=Depends(require_member)):
    return ok(
        runtime.build_voice_loop_preview(
            owner_id=_user["username"],
            model_pack=req.model_pack,
            model_pack_id=req.model_pack_id,
            input_model_key=req.input_model_key,
            main_model_key=req.main_model_key,
            output_model_key=req.output_model_key,
            conversation_id=req.conversation_id,
        )
    )


@router.post("/voice/transcribe")
async def assistant_voice_transcribe(request: Request, model_key: str | None = None, _user=Depends(require_member)):
    content_length = int(request.headers.get("content-length") or 0)
    if content_length > voice.MAX_AUDIO_BYTES:
        raise ValueError(f"Audio input is limited to {voice.MAX_AUDIO_BYTES} bytes.")
    audio = await request.body()
    if not audio:
        raise ValueError("Audio input is required.")
    if len(audio) > voice.MAX_AUDIO_BYTES:
        raise ValueError(f"Audio input is limited to {voice.MAX_AUDIO_BYTES} bytes.")
    model = voice.resolve_model(model_key, "speech_to_text")
    result = await asyncio.to_thread(
        voice.transcribe,
        model,
        audio,
        request.headers.get("x-filename") or "audio.wav",
        request.headers.get("content-type") or "audio/wav",
    )
    return ok(result)


@router.post("/voice/synthesize")
async def assistant_voice_synthesize(req: VoiceSynthesisIn, _user=Depends(require_member)):
    model = voice.resolve_model(req.model_key, "text_to_speech")
    result = await asyncio.to_thread(
        voice.synthesize,
        model,
        req.text,
        req.voice,
        req.response_format,
    )
    return Response(
        content=result["audio"],
        media_type=result["content_type"],
        headers={
            "X-Rasputin-Voice-Contract": result["contract_version"],
            "X-Rasputin-Voice-Model": str(result.get("model_key") or ""),
            "Content-Disposition": f'inline; filename="rasputin-speech.{result["response_format"]}"',
        },
    )


@router.post("/voice/turn")
async def assistant_voice_turn(
    request: Request,
    input_model_key: str | None = None,
    main_model_key: str | None = None,
    output_model_key: str | None = None,
    conversation_id: str | None = None,
    _user=Depends(require_member),
):
    """Run one local STT -> Assistant -> TTS turn without host actions."""

    content_length = int(request.headers.get("content-length") or 0)
    if content_length > voice.MAX_AUDIO_BYTES:
        raise ValueError(f"Audio input is limited to {voice.MAX_AUDIO_BYTES} bytes.")
    audio = await request.body()
    if not audio:
        raise ValueError("Audio input is required.")
    if len(audio) > voice.MAX_AUDIO_BYTES:
        raise ValueError(f"Audio input is limited to {voice.MAX_AUDIO_BYTES} bytes.")

    stt_model = voice.resolve_model(input_model_key, "speech_to_text")
    main_model = voice.resolve_model(main_model_key, "main")
    tts_model = voice.resolve_model(output_model_key, "text_to_speech")
    transcript = await asyncio.to_thread(
        voice.transcribe,
        stt_model,
        audio,
        request.headers.get("x-filename") or "audio.wav",
        request.headers.get("content-type") or "audio/wav",
    )
    transcript_text = str(transcript.get("text") or "").strip()[:voice.MAX_TEXT_CHARS]
    if not transcript_text:
        raise ValueError("The local speech adapter returned an empty transcript.")

    from backend.api.core import hub

    owner_id = _user["username"]
    if conversation_id:
        session = hub.session(conversation_id, owner_id)
        if str(session["session"].get("mode") or "chat") != "chat":
            raise AppError("voice_conversation_mode_invalid", "Voice turns can only continue an Assistant chat session.", 409)
        session_id = conversation_id
    else:
        session = hub.create_session(
            title="Rasputin voice conversation",
            workspace=".",
            model=str(main_model.get("key") or ""),
            mode="chat",
            skill="general",
            owner_id=owner_id,
        )
        session_id = session["session"]["id"]
    history = hub.recent_messages(session_id, limit=12)
    messages = [{"role": item["role"], "content": item["content"]} for item in history if item.get("role") in {"user", "assistant"}]
    messages.append({"role": "user", "content": transcript_text})
    hub._add_message(session_id, None, "user", transcript_text)

    try:
        max_tokens = min(voice.MAX_TEXT_CHARS, context_governor.output_budget(main_model, messages))
        response_text, _tool_calls = await model_providers.chat(
            main_model,
            [{"role": "system", "content": _voice_system_prompt(runtime.get_profile(owner_id))}, *messages],
            max_tokens=max_tokens,
            temperature=0.2,
            tools=None,
            reasoning="off",
        )
    except Exception as exc:
        audit.log("assistant_voice_turn_failed", {"conversation_id": session_id, "stage": "reason"}, actor=owner_id)
        raise AppError("voice_conversation_failed", "The local Assistant model could not complete this voice turn.", 502) from exc

    response_text = str(response_text or "").strip()[:voice.MAX_TEXT_CHARS]
    if not response_text:
        raise AppError("voice_conversation_empty", "The local Assistant model returned no spoken response.", 502)
    hub._add_message(session_id, None, "assistant", response_text)
    synthesized = await asyncio.to_thread(
        voice.synthesize,
        tts_model,
        response_text,
        None,
        "wav",
    )
    audit.log("assistant_voice_turn_completed", {"conversation_id": session_id}, actor=owner_id)
    return ok({
        "contract_version": VOICE_TURN_CONTRACT_VERSION,
        "operation": "voice_turn",
        "stage": "conversation",
        "conversation_id": session_id,
        "transcript": transcript_text,
        "response": response_text,
        "audio_base64": base64.b64encode(synthesized["audio"]).decode("ascii"),
        "content_type": synthesized["content_type"],
        "models": {
            "speech_to_text": stt_model.get("key"),
            "main": main_model.get("key"),
            "text_to_speech": tts_model.get("key"),
        },
        "execution": {
            "started": True,
            "audio_io_started": False,
            "models_started": False,
            "side_effects": False,
            "host_mutation": False,
        },
        "policy": {
            "owner_scoped": True,
            "local_only": True,
            "assistant_conversation_only": True,
            "host_actions": "not_started",
        },
    })


@router.post("/context-preview")
async def assistant_context_preview(req: ContextPreviewIn, _user=Depends(require_member)):
    _assert_sensitive_allowed(req, _user)
    workspace_ref = _workspace_for_request(req, _user)
    return ok(
        runtime.build_context_preview(
            owner_id=_user["username"],
            objective=req.objective,
            workspace_ref=workspace_ref,
            session_id=req.session_id,
            context_query=req.context_query,
            include_sensitive=req.include_sensitive,
        )
    )


@router.post("/context-capsules")
async def assistant_context_capsule_create(req: ContextPreviewIn, _user=Depends(require_member)):
    _assert_sensitive_allowed(req, _user)
    workspace_ref = _workspace_for_request(req, _user)
    return ok(
        runtime.create_context_capsule(
            owner_id=_user["username"],
            objective=req.objective,
            workspace_ref=workspace_ref,
            session_id=req.session_id,
            context_query=req.context_query,
            include_sensitive=req.include_sensitive,
            expires_in_seconds=req.expires_in_seconds,
        )
    )


@router.get("/context-capsules")
async def assistant_context_capsule_list(limit: int = 50, _user=Depends(current_user)):
    return ok({"capsules": runtime.list_context_capsules(_user["username"], limit)})


@router.get("/context-capsules/{capsule_id}")
async def assistant_context_capsule_get(capsule_id: str, _user=Depends(current_user)):
    capsule = runtime.get_context_capsule(_user["username"], capsule_id)
    if not capsule:
        raise ValueError("assistant context capsule missing")
    return ok(capsule)


@router.post("/context-capsules/{capsule_id}/approve")
async def assistant_context_capsule_approve(capsule_id: str, req: PlanReviewIn, _user=Depends(require_member)):
    return ok(runtime.review_context_capsule(_user["username"], capsule_id, "approved", req.note or ""))


@router.post("/context-capsules/{capsule_id}/reject")
async def assistant_context_capsule_reject(capsule_id: str, req: PlanReviewIn, _user=Depends(require_member)):
    return ok(runtime.review_context_capsule(_user["username"], capsule_id, "rejected", req.note or ""))


@router.get("/profile")
async def assistant_profile(_user=Depends(current_user)):
    return ok(runtime.get_profile(_user["username"]))


@router.patch("/profile")
async def assistant_profile_patch(req: ProfilePatchIn, _user=Depends(require_member)):
    profile = runtime.update_profile(_user["username"], req.model_dump(exclude_none=True))
    audit.log("assistant_profile_patch", {"fields": sorted(req.model_dump(exclude_none=True).keys())}, actor=_user["username"])
    return ok(profile)


@router.post("/plan-preview")
async def assistant_plan_preview(req: PlanPreviewIn, _user=Depends(require_member)):
    _assert_sensitive_allowed(req, _user)
    workspace_ref = _workspace_for_request(req, _user)
    return ok(
        runtime.build_plan_preview(
            owner_id=_user["username"],
            objective=req.objective,
            workspace_ref=workspace_ref,
            session_id=req.session_id,
            context_query=req.context_query,
            context_capsule_id=req.context_capsule_id,
            model_pack=req.model_pack,
            model_pack_id=req.model_pack_id,
            agents=req.agents,
            requested_operations=req.requested_operations,
            include_sensitive=req.include_sensitive,
        )
    )


@router.post("/plans")
async def assistant_plan_create(req: PlanPreviewIn, _user=Depends(require_member)):
    _assert_sensitive_allowed(req, _user)
    workspace_ref = _workspace_for_request(req, _user)
    return ok(
        runtime.create_persisted_plan(
            owner_id=_user["username"],
            objective=req.objective,
            workspace_ref=workspace_ref,
            session_id=req.session_id,
            context_query=req.context_query,
            context_capsule_id=req.context_capsule_id,
            model_pack=req.model_pack,
            model_pack_id=req.model_pack_id,
            agents=req.agents,
            requested_operations=req.requested_operations,
            include_sensitive=req.include_sensitive,
        )
    )


@router.post("/model-packs")
async def assistant_model_pack_save(req: ModelPackIn, _user=Depends(require_member)):
    return ok(runtime.save_model_pack(_user["username"], req.model_dump()))


@router.get("/model-packs")
async def assistant_model_pack_list(limit: int = 50, _user=Depends(current_user)):
    return ok({"packs": runtime.list_model_packs(_user["username"], limit)})


@router.get("/model-packs/{pack_id}")
async def assistant_model_pack_get(pack_id: str, _user=Depends(current_user)):
    pack = runtime.get_model_pack(_user["username"], pack_id)
    if not pack:
        raise ValueError("model pack missing")
    return ok(pack)


@router.delete("/model-packs/{pack_id}")
async def assistant_model_pack_delete(pack_id: str, _user=Depends(require_member)):
    return ok(runtime.delete_model_pack(_user["username"], pack_id))


@router.get("/plans")
async def assistant_plan_list(limit: int = 50, _user=Depends(current_user)):
    return ok({"plans": runtime.list_persisted_plans(_user["username"], limit)})


@router.get("/plans/{plan_id}")
async def assistant_plan_get(plan_id: str, _user=Depends(current_user)):
    plan = runtime.get_persisted_plan(_user["username"], plan_id)
    if not plan:
        raise ValueError("assistant plan missing")
    return ok(plan)


@router.post("/plans/{plan_id}/approve")
async def assistant_plan_approve(plan_id: str, req: PlanReviewIn, _user=Depends(require_member)):
    return ok(runtime.review_persisted_plan(_user["username"], plan_id, "approved", req.note or ""))


@router.post("/plans/{plan_id}/reject")
async def assistant_plan_reject(plan_id: str, req: PlanReviewIn, _user=Depends(require_member)):
    return ok(runtime.review_persisted_plan(_user["username"], plan_id, "rejected", req.note or ""))


@router.post("/plans/{plan_id}/handoffs")
async def assistant_plan_handoff(plan_id: str, req: HandoffIn, _user=Depends(require_member)):
    return ok(runtime.request_handoff(_user["username"], plan_id, req.operation))


@router.post("/handoffs/{handoff_id}/prepare")
async def assistant_handoff_prepare(handoff_id: str, _user=Depends(require_member)):
    return ok(runtime.prepare_handoff(_user["username"], handoff_id))


@router.post("/handoffs/{handoff_id}/dispatch")
async def assistant_handoff_dispatch(handoff_id: str, _user=Depends(require_member)):
    # The governed Code adapter schedules through the request's running event
    # loop; dispatch_handoff still contains only bounded broker work and fixed
    # host adapters, so it is intentionally invoked directly here.
    return ok(runtime.dispatch_handoff(_user["username"], handoff_id, is_admin=_user.get("role") == "admin"))


@router.get("/handoffs")
async def assistant_handoff_list(limit: int = 50, _user=Depends(current_user)):
    return ok({"handoffs": runtime.list_handoffs(_user["username"], limit)})


@router.get("/handoffs/{handoff_id}")
async def assistant_handoff_get(handoff_id: str, _user=Depends(current_user)):
    handoff = runtime.get_handoff(_user["username"], handoff_id)
    if not handoff:
        raise ValueError("assistant handoff missing")
    return ok(handoff)
