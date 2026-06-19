from fastapi import APIRouter, Depends
from backend.core.response import ok
from backend.api.common import CamelModel, current_user
from backend.rag import vector as rag
from backend.rag import graph as graphify
from backend.core import security

router = APIRouter(prefix="/api", tags=["rag", "graph"])

class RagIn(CamelModel):
    path: str = "."
    label: str | None = None

class RagSearchIn(CamelModel):
    query: str
    limit: int = 6
    path: str | None = None

class GraphSearchIn(CamelModel):
    query: str
    limit: int = 12

class GraphBuildIn(CamelModel):
    path: str | None = None


@router.get("/rag/stats")
async def rag_stats(_user=Depends(current_user)):
    return ok(rag.stats())

@router.post("/rag/ingest")
async def rag_ingest(req: RagIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.ingest(req.path, req.label))

@router.post("/rag/search")
async def rag_search(req: RagSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(rag.search(req.query, req.limit, req.path))

@router.get("/graph/stats")
async def graph_stats(_user=Depends(current_user)):
    return ok(graphify.stats())

@router.post("/graph/build")
async def graph_build(req: GraphBuildIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.build(req.path))

@router.post("/graph/search")
async def graph_search(req: GraphSearchIn, _user=Depends(current_user)):
    security.require("allow_file_read")
    return ok(graphify.search(req.query, req.limit))
