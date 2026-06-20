import json
import re
import time
from pathlib import Path
from threading import Lock

from backend.engine import output
from backend.rag import graph as graphify
from backend.rag import vector as rag
from backend.core import runtime_store as store

from .models import ArchiveItem, ArchiveRetentionRule
from .service import ArchiveService

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARCHIVE_FILE = DATA_DIR / "archive_sessions.json"
_lock = Lock()


def _blank():
    return {"sessions": []}


def _load():
    data = store.get_kv("archive")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if ARCHIVE_FILE.exists():
            with _lock:
                try:
                    data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = _blank()
        else:
            data = _blank()
        store.set_kv("archive", data)
    if "sessions" not in data:
        data = _blank()
    return data


def _save(data):
    DATA_DIR.mkdir(exist_ok=True)
    with _lock:
        store.set_kv("archive", data)


def _slug(text):
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(text or "")).strip("-").lower()[:64] or "archive"


def _clip(text, limit=420):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _citation_location(item):
    if item.get("page_start"):
        end = item.get("page_end")
        return f"Page {item.get('page_start')}" + (f"-{end}" if end and end != item.get("page_start") else "")
    if item.get("sheet_name"):
        start = item.get("row_start") or item.get("line_start")
        end = item.get("row_end") or item.get("line_end")
        rows = f" rows {start}-{end}" if start and end else ""
        return f"{item.get('sheet_name')}{rows}"
    if item.get("line_start"):
        end = item.get("line_end")
        return f"Lines {item.get('line_start')}" + (f"-{end}" if end and end != item.get("line_start") else "")
    return f"Chunk {item.get('chunk', 0)}"


def citation_search(query, path=None, limit=6):
    clean_query = str(query or "").strip()
    safe_limit = max(1, min(int(limit or 6), 12))
    if not clean_query:
        return {"query": "", "path": path, "rag_hits": [], "graph_nodes": [], "graph_edges": [], "total": 0}

    rag_result = rag.search(clean_query, safe_limit, path)
    graph_result = graphify.search(clean_query, safe_limit)
    rag_hits = []
    for hit in rag_result.get("hits", [])[:safe_limit]:
        rag_hits.append({
            "id": f"rag:{hit.get('path')}:{hit.get('chunk')}",
            "kind": "rag",
            "title": hit.get("path") or hit.get("source") or "Indexed source",
            "path": hit.get("path"),
            "location": _citation_location(hit),
            "parser": hit.get("parser") or "text",
            "score": hit.get("score"),
            "snippet": _clip(hit.get("text")),
            "citation": hit.get("citation") or {},
        })

    graph_nodes = []
    for node in graph_result.get("nodes", [])[:safe_limit]:
        graph_nodes.append({
            "id": f"node:{node.get('kind')}:{node.get('name')}",
            "kind": node.get("kind") or "node",
            "name": node.get("name") or "Graph node",
            "weight": node.get("weight", 0),
            "sources": node.get("sources", [])[:4],
            "snippet": _clip(" ".join((item.get("snippet") or "") for item in node.get("evidence", [])[:2])),
        })

    graph_edges = []
    for edge in graph_result.get("edges", [])[:safe_limit]:
        graph_edges.append({
            "id": f"edge:{edge.get('source')}:{edge.get('relation')}:{edge.get('target')}",
            "source": edge.get("source"),
            "target": edge.get("target"),
            "relation": edge.get("relation") or edge.get("type") or "related_to",
            "weight": edge.get("weight", 0),
            "why": _clip(edge.get("why") or ""),
            "snippet": _clip(" ".join((item.get("snippet") or "") for item in edge.get("evidence", [])[:2])),
        })

    return {
        "query": clean_query,
        "path": path,
        "rag_hits": rag_hits,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "total": len(rag_hits) + len(graph_nodes) + len(graph_edges),
    }


def sessions():
    data = _load()
    return {"sessions": sorted(data.get("sessions", []), key=lambda item: item.get("updated_at", 0), reverse=True)}


def save_session(payload):
    payload = payload or {}
    stamp = time.time()
    session_id = payload.get("id") or store.new_id("arch")
    title = str(payload.get("title") or "Untitled archive draft").strip()[:160]
    content = str(payload.get("content") or "")
    session = {
        "id": session_id,
        "title": title,
        "content": content,
        "format": "markdown",
        "created_at": stamp,
        "updated_at": stamp,
        "word_count": len([word for word in re.split(r"\s+", content.strip()) if word]),
    }
    data = _load()
    existing = next((item for item in data.get("sessions", []) if item.get("id") == session_id), None)
    if existing:
        session["created_at"] = existing.get("created_at") or stamp
    data["sessions"] = [item for item in data.get("sessions", []) if item.get("id") != session_id] + [session]
    _save(data)
    return session


def export_session(session_id, folder=None):
    data = _load()
    session = next((item for item in data.get("sessions", []) if item.get("id") == session_id), None)
    if not session:
        raise ValueError("archive session missing")
    cfg = output.get_config()
    target = output._safe_path(folder or cfg.get("markdownFolder") or cfg.get("markdown_folder"))
    target.mkdir(parents=True, exist_ok=True)
    filename = f"{time.strftime('%Y%m%d-%H%M%S')}-{_slug(session.get('title'))}.md"
    path = target / filename
    path.write_text(session.get("content") or "", encoding="utf-8")
    return {"path": output._rel(path), "absolute_path": str(path), "title": session.get("title")}
