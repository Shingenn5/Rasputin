import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock

from . import rag

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GRAPH_FILE = DATA_DIR / "graph.json"

_lock = Lock()
STOP_ENTITIES = {
    "the", "then", "task", "true", "false", "none", "exception", "path", "root",
    "data_dir", "lock", "counter", "valueerror", "json", "time", "return"
}


def _blank():
    return {"version": 2, "updated_at": None, "nodes": [], "edges": []}


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not GRAPH_FILE.exists():
        GRAPH_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if data.get("version") != 2:
        return _blank()
    return data


def _save(graph):
    DATA_DIR.mkdir(exist_ok=True)
    graph["updated_at"] = time.time()
    with _lock:
        GRAPH_FILE.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def _clean(text):
    text = re.sub(r"[^A-Za-z0-9_./ -]", " ", str(text or ""))
    text = " ".join(text.split()).strip(" -_./")
    if len(text) < 2 or len(text) > 90:
        return ""
    return text


def _node_id(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:100] or "node"


def _kind(name):
    if "/" in name or "." in name:
        return "file" if "." in name.split("/")[-1] else "folder"
    if name.endswith("()"):
        return "function"
    if re.match(r"^[A-Z][A-Za-z0-9_]+$", name):
        return "class"
    if " " in name and any(part[:1].isupper() for part in name.split()):
        return "concept"
    return "concept"


def _entities(text, source):
    found = {source}
    for item in re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]+)", text):
        found.add(_clean(item))
    for item in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        found.add(_clean(f"{item}()"))
    for item in re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        found.add(_clean(f"{item}()"))
    for item in re.findall(r"\b[A-Z][A-Za-z0-9_]*(?:\s+[A-Z][A-Za-z0-9_]*){0,3}\b", text):
        ent = _clean(item)
        if ent and ent.lower() not in STOP_ENTITIES:
            found.add(ent)
    for item in re.findall(r"\b[a-zA-Z_][A-Za-z0-9_]*\.(?:py|js|html|css|json|md)\b", text):
        ent = _clean(item)
        if ent:
            found.add(ent)
    return sorted(x for x in found if x)


def _edge(edges, source, relation, target, evidence, weight=1):
    if not source or not target or source == target:
        return
    key = (source, relation, target)
    edges[key]["weight"] += weight
    edges[key]["evidence"].append(evidence)


def _import_edges(text, source, evidence, edges):
    for item in re.findall(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_., ]+))", text, re.M):
        target = _clean(item[0] or item[1].split(",")[0])
        if target:
            _edge(edges, source, "imports", target, evidence, 3)


def _definition_edges(text, source, evidence, edges):
    for item in re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]+)", text):
        _edge(edges, source, "defines", _clean(item), evidence, 3)
    for item in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        _edge(edges, source, "defines", _clean(f"{item}()"), evidence, 2)


def build(path=None):
    index = rag.raw_index()
    if not index.get("chunks"):
        rag.ingest(path or ".")
        index = rag.raw_index()

    node_counts = Counter()
    node_sources = defaultdict(set)
    node_evidence = defaultdict(list)
    edges = defaultdict(lambda: {"weight": 0, "evidence": []})

    scoped_chunks = rag.chunks_for_path(path)

    for chunk in scoped_chunks:
        source = chunk.get("source", "")
        text = chunk.get("text", "")
        evidence = {
            "source": source,
            "path": chunk.get("path"),
            "chunk": chunk.get("chunk"),
            "line_start": chunk.get("line_start"),
            "line_end": chunk.get("line_end"),
            "text": text[:500],
        }
        ents = _entities(text, source)
        for ent in ents:
            node_counts[ent] += 1
            node_sources[ent].add(source)
            if len(node_evidence[ent]) < 5:
                node_evidence[ent].append(evidence)
            _edge(edges, source, "mentions", ent, evidence)

        _import_edges(text, source, evidence, edges)
        _definition_edges(text, source, evidence, edges)

        for i, left in enumerate(ents[:12]):
            for right in ents[i + 1:i + 4]:
                _edge(edges, left, "related_to", right, evidence)

    nodes = []
    for name, count in node_counts.items():
        nodes.append({
            "id": _node_id(name),
            "name": name,
            "kind": _kind(name),
            "weight": count,
            "sources": sorted(node_sources[name])[:8],
            "evidence": node_evidence[name][:5],
        })

    out_edges = []
    for (source, relation, target), data in edges.items():
        out_edges.append({
            "source": source,
            "relation": relation,
            "target": target,
            "weight": data["weight"],
            "evidence": data["evidence"][:5],
        })

    nodes.sort(key=lambda x: x["weight"], reverse=True)
    out_edges.sort(key=lambda x: x["weight"], reverse=True)
    graph = {"version": 2, "updated_at": None, "nodes": nodes, "edges": out_edges}
    _save(graph)
    return stats()


def stats():
    graph = _load()
    return {
        "version": graph.get("version", 2),
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
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
        hay = " ".join([node.get("name", ""), node.get("kind", ""), " ".join(node.get("sources", []))]).lower()
        score = sum(1 for t in terms if t in hay) * max(1, node.get("weight", 1))
        if score:
            item = dict(node)
            item["score"] = score
            nodes.append(item)
    nodes.sort(key=lambda x: x["score"], reverse=True)
    names = {n["name"] for n in nodes[:limit]}
    edges = []
    for edge in graph.get("edges", []):
        hay = f"{edge.get('source','')} {edge.get('relation','')} {edge.get('target','')}".lower()
        if edge.get("source") in names or edge.get("target") in names or any(t in hay for t in terms):
            edges.append(edge)
    return {"query": query, "nodes": nodes[:limit], "edges": edges[:limit]}


def reset():
    _save(_blank())
    return stats()
