import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock

from backend.rag import vector as rag

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GRAPH_FILE = DATA_DIR / "graph.json"
GRAPH_VERSION = 3

_lock = Lock()
STOP_ENTITIES = {
    "the", "then", "task", "true", "false", "none", "exception", "path", "root",
    "data_dir", "lock", "counter", "valueerror", "json", "time", "return",
    "print", "if", "for", "while", "with", "open", "self", "none", "true", "false",
}
DOCUMENT_EXTS = {".pdf", ".docx", ".xlsx"}
CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css"}


def _blank():
    return {"version": GRAPH_VERSION, "updated_at": None, "nodes": [], "edges": []}


from backend.core import runtime_store as store

def _load():
    data = store.get_kv("rag_graph")
    if not isinstance(data, dict):
        DATA_DIR.mkdir(exist_ok=True)
        if GRAPH_FILE.exists():
            with _lock:
                try:
                    data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = _blank()
        else:
            data = _blank()
        store.set_kv("rag_graph", data)
    if data.get("version") != GRAPH_VERSION:
        return _blank()
    return data


def _save(graph):
    DATA_DIR.mkdir(exist_ok=True)
    graph["updated_at"] = time.time()
    with _lock:
        store.set_kv("rag_graph", graph)


def _clean(text):
    text = re.sub(r"[^A-Za-z0-9_./ -]", " ", str(text or ""))
    text = " ".join(text.split()).strip(" -_./")
    if len(text) < 2 or len(text) > 90:
        return ""
    return text


def _node_id(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:100] or "node"


def _typed_node_id(kind, name):
    return f"{kind}:{_node_id(name)}"


def _path_kind(path, parser=None):
    suffix = Path(str(path or "")).suffix.lower()
    if parser in {"pdf", "docx", "xlsx"} or suffix in DOCUMENT_EXTS:
        return "document"
    if suffix in CODE_EXTS or suffix:
        return "file"
    return "folder"


def _kind(name, parser=None):
    if "/" in name or "." in name:
        return _path_kind(name, parser)
    if name.endswith("()"):
        return "function"
    if re.match(r"^[A-Z][A-Za-z0-9_]+$", name):
        return "class"
    if " " in name and any(part[:1].isupper() for part in name.split()):
        return "concept"
    return "concept"


def _node_ref(kind, name):
    clean_name = _clean(name)
    return {
        "id": _typed_node_id(kind, clean_name),
        "name": clean_name,
        "kind": kind,
    }


def _citation(chunk):
    return {
        "workspace_id": chunk.get("workspace_id"),
        "path": chunk.get("path"),
        "chunk": chunk.get("chunk"),
        "line_start": chunk.get("line_start"),
        "line_end": chunk.get("line_end"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "sheet_name": chunk.get("sheet_name"),
        "row_start": chunk.get("row_start"),
        "row_end": chunk.get("row_end"),
        "citation_kind": chunk.get("citation_kind") or "line",
        "parser": chunk.get("parser"),
        "mtime": chunk.get("mtime"),
    }


def _snippet(text):
    return " ".join(str(text or "").split())[:600]


def _evidence(chunk):
    return {
        "source": chunk.get("source"),
        "path": chunk.get("path"),
        "chunk": chunk.get("chunk"),
        "citation": _citation(chunk),
        "snippet": _snippet(chunk.get("text")),
    }


def _entities(text, source):
    found = []
    seen = set()

    def add(kind, name):
        name = _clean(name)
        key = (kind, name)
        if name and key not in seen and name.lower() not in STOP_ENTITIES:
            seen.add(key)
            found.append(_node_ref(kind, name))

    for item in re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]+)", text):
        add("class", item)
    for item in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        add("function", f"{item}()")
    for item in re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        add("function", f"{item}()")
    for item in re.findall(r"\b[A-Z][A-Za-z0-9_]*(?:\s+[A-Z][A-Za-z0-9_]*){0,3}\b", text):
        ent = _clean(item)
        if ent:
            add("concept", ent)
    for item in re.findall(r"\b[a-zA-Z0-9_./-]+\.(?:py|js|jsx|ts|tsx|html|css|json|md|pdf|docx|xlsx)\b", text):
        ent = _clean(item)
        if ent:
            add(_path_kind(ent), ent)
    return found


def _node(nodes, ref, evidence=None, weight=1):
    if not ref.get("id") or not ref.get("name"):
        return
    item = nodes[ref["id"]]
    item["id"] = ref["id"]
    item["name"] = ref["name"]
    item["kind"] = ref["kind"]
    item["type"] = ref["kind"]
    item["weight"] += weight
    if evidence:
        if evidence.get("source"):
            item["sources"].add(evidence["source"])
        if len(item["evidence"]) < 8:
            item["evidence"].append(evidence)


def _edge(edges, source, relation, target, evidence, weight=1):
    if not source or not target or source.get("id") == target.get("id"):
        return
    key = (source["id"], relation, target["id"])
    edges[key]["weight"] += weight
    edges[key]["source"] = source
    edges[key]["target"] = target
    edges[key]["relation"] = relation
    edges[key]["evidence"].append(evidence)


def _import_edges(text, source, evidence, edges, nodes):
    for item in re.findall(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_., ]+))", text, re.M):
        target = _clean(item[0] or item[1].split(",")[0])
        if target:
            target_ref = _node_ref("concept", target)
            _node(nodes, target_ref, evidence)
            _edge(edges, source, "imports", target_ref, evidence, 3)


def _definition_edges(text, source, evidence, edges, nodes):
    for item in re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]+)", text):
        target_ref = _node_ref("class", item)
        _node(nodes, target_ref, evidence, 3)
        _edge(edges, source, "defines", target_ref, evidence, 3)
    for item in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        target_ref = _node_ref("function", f"{item}()")
        _node(nodes, target_ref, evidence, 2)
        _edge(edges, source, "defines", target_ref, evidence, 2)


def _call_edges(text, source, evidence, edges, nodes):
    for item in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        if item.lower() in STOP_ENTITIES:
            continue
        if item in {"def", "class", "function"}:
            continue
        target_ref = _node_ref("function", f"{item}()")
        _node(nodes, target_ref, evidence)
        _edge(edges, source, "calls", target_ref, evidence)


def _reference_edges(text, source, evidence, edges, nodes):
    for item in re.findall(r"\b[a-zA-Z0-9_./-]+\.(?:py|js|jsx|ts|tsx|html|css|json|md|pdf|docx|xlsx)\b", text):
        target = _clean(item)
        if not target:
            continue
        target_ref = _node_ref(_path_kind(target), target)
        _node(nodes, target_ref, evidence)
        _edge(edges, source, "references", target_ref, evidence, 2)


def _folder_ref(path):
    folder = str(Path(path or "").parent).replace("\\", "/")
    if folder in {"", "."}:
        folder = "workspace root"
    return _node_ref("folder", folder)


def build(path=None):
    index = rag.raw_index()
    if not index.get("chunks"):
        rag.ingest(path or ".")
        index = rag.raw_index()

    nodes = defaultdict(lambda: {"weight": 0, "sources": set(), "evidence": []})
    edges = defaultdict(lambda: {"weight": 0, "evidence": []})

    scoped_chunks = rag.chunks_for_path(path)

    for chunk in scoped_chunks:
        path_name = chunk.get("path") or chunk.get("source", "")
        text = chunk.get("text", "")
        evidence = _evidence(chunk)
        file_ref = _node_ref(_path_kind(path_name, chunk.get("parser")), path_name)
        folder_ref = _folder_ref(path_name)
        _node(nodes, file_ref, evidence, 3)
        _node(nodes, folder_ref, evidence)
        _edge(edges, file_ref, "located_in", folder_ref, evidence, 2)

        ents = _entities(text, path_name)
        for ent in ents:
            _node(nodes, ent, evidence)
            _edge(edges, file_ref, "mentions", ent, evidence)

        _import_edges(text, file_ref, evidence, edges, nodes)
        _definition_edges(text, file_ref, evidence, edges, nodes)
        _call_edges(text, file_ref, evidence, edges, nodes)
        _reference_edges(text, file_ref, evidence, edges, nodes)

        for i, left in enumerate(ents[:12]):
            for right in ents[i + 1:i + 4]:
                _edge(edges, left, "related_to", right, evidence)

    out_nodes = []
    for item in nodes.values():
        out_nodes.append({
            "id": item["id"],
            "name": item["name"],
            "kind": item["kind"],
            "type": item["type"],
            "weight": item["weight"],
            "sources": sorted(item["sources"])[:8],
            "evidence": item["evidence"][:8],
        })

    out_edges = []
    for data in edges.values():
        source = data["source"]
        target = data["target"]
        relation = data["relation"]
        weight = data["weight"]
        out_edges.append({
            "source": source["name"],
            "source_id": source["id"],
            "source_kind": source["kind"],
            "relation": relation,
            "type": relation,
            "target": target["name"],
            "target_id": target["id"],
            "target_kind": target["kind"],
            "weight": weight,
            "confidence": round(min(0.99, 0.35 + (weight * 0.08)), 3),
            "evidence": data["evidence"][:8],
            "why": _why(relation, source, target, data["evidence"]),
        })

    out_nodes.sort(key=lambda x: x["weight"], reverse=True)
    out_edges.sort(key=lambda x: x["weight"], reverse=True)
    graph = {"version": GRAPH_VERSION, "updated_at": None, "nodes": out_nodes, "edges": out_edges}
    _save(graph)
    return stats()


def _why(relation, source, target, evidence):
    first = (evidence or [{}])[0]
    citation = first.get("citation") or {}
    location = citation.get("path") or first.get("path") or "local source"
    if citation.get("page_start"):
        location = f"{location} page {citation['page_start']}"
    elif citation.get("sheet_name"):
        location = f"{location} {citation['sheet_name']} rows {citation.get('row_start') or '?'}-{citation.get('row_end') or '?'}"
    elif citation.get("line_start"):
        location = f"{location} lines {citation.get('line_start')}-{citation.get('line_end') or citation.get('line_start')}"
    return f"{source['name']} {relation.replace('_', ' ')} {target['name']} based on {location}."


def stats():
    graph = _load()
    node_kinds = Counter(node.get("kind") for node in graph.get("nodes", []))
    edge_types = Counter(edge.get("type") or edge.get("relation") for edge in graph.get("edges", []))
    return {
        "version": graph.get("version", GRAPH_VERSION),
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "node_kinds": dict(sorted(node_kinds.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "updated_at": graph.get("updated_at"),
        "top_nodes": graph.get("nodes", [])[:15],
    }


def search(query, limit=12):
    graph = _load()
    terms = set(rag.query_terms(query))
    if not terms:
        return {"query": query, "nodes": [], "edges": []}
    nodes = []
    for node in graph.get("nodes", []):
        evidence_text = " ".join((item.get("snippet") or "") for item in node.get("evidence", [])[:3])
        hay = " ".join([node.get("name", ""), node.get("kind", ""), " ".join(node.get("sources", [])), evidence_text]).lower()
        score = sum(1 for t in terms if t in hay) * max(1, node.get("weight", 1))
        if score:
            item = dict(node)
            item["score"] = score
            nodes.append(item)
    nodes.sort(key=lambda x: x["score"], reverse=True)
    names = {n["name"] for n in nodes[:limit]}
    edges = []
    for edge in graph.get("edges", []):
        evidence_text = " ".join((item.get("snippet") or "") for item in edge.get("evidence", [])[:3])
        hay = f"{edge.get('source','')} {edge.get('source_kind','')} {edge.get('relation','')} {edge.get('target','')} {edge.get('target_kind','')} {edge.get('why','')} {evidence_text}".lower()
        if edge.get("source") in names or edge.get("target") in names or any(t in hay for t in terms):
            item = dict(edge)
            item["score"] = sum(1 for t in terms if t in hay) * max(1, edge.get("weight", 1))
            edges.append(item)
    edges.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {"query": query, "nodes": nodes[:limit], "edges": edges[:limit]}


def reset():
    _save(_blank())
    return stats()
