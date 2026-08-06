"""HTTP surface for Rasputin identity and preview-only orchestration."""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import Field

from backend.api.core import CamelModel, current_user, require_member
from backend.assistant import runtime
from backend.core import audit
from backend.core import workspace
from backend.core.response import ok


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
    return ok(runtime.capabilities())


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
    return ok(await asyncio.to_thread(runtime.dispatch_handoff, _user["username"], handoff_id))


@router.get("/handoffs")
async def assistant_handoff_list(limit: int = 50, _user=Depends(current_user)):
    return ok({"handoffs": runtime.list_handoffs(_user["username"], limit)})


@router.get("/handoffs/{handoff_id}")
async def assistant_handoff_get(handoff_id: str, _user=Depends(current_user)):
    handoff = runtime.get_handoff(_user["username"], handoff_id)
    if not handoff:
        raise ValueError("assistant handoff missing")
    return ok(handoff)
