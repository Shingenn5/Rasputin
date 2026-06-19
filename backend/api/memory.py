from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user
from backend.rag.memory import load_memory, remember
from backend.rag import memory as memory_store

router = APIRouter(prefix="/api/memory", tags=["memory"])

class MemoryIn(CamelModel):
    kind: str = "fact"
    value: object

class MemorySearchIn(CamelModel):
    query: str
    limit: int = 10

class MemoryReviewIn(CamelModel):
    id: str
    action: str = "approve"

@router.get("")
async def memory(_user=Depends(current_user)):
    return ok(load_memory())

@router.post("")
async def add_memory(req: MemoryIn, _user=Depends(current_user)):
    return ok(remember(req.kind, req.value))

@router.get("/review")
async def memory_review(_user=Depends(current_user)):
    return ok(memory_store.pending_review())

@router.post("/review")
async def memory_review_decide(req: MemoryReviewIn, _user=Depends(current_user)):
    if req.action == "approve":
        return ok(memory_store.approve_item(req.id))
    if req.action in {"deny", "reject"}:
        return ok(memory_store.reject_item(req.id))
    raise ValueError("memory review action must be approve or reject")

@router.post("/search")
async def memory_search(req: MemorySearchIn, _user=Depends(current_user)):
    return ok(memory_store.search(req.query, req.limit))
