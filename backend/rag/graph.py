import ast
import builtins
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock

from backend.core import workspace
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
# Only these produce structural (imports/defines/calls) edges; prose/markup
# still gets mentions/references edges but not fake call edges.
SCRIPT_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx"}
MAX_AST_BYTES = 1_500_000
_PY_BUILTINS = frozenset(dir(builtins))
# Regex fallback (non-Python scripts, unparseable Python) deny-list: control-flow
# keywords the `identifier(` pattern would otherwise report as function calls.
_REGEX_CALL_KEYWORDS = {
    "assert", "async", "await", "catch", "constructor", "del", "elif", "except",
    "export", "import", "lambda", "new", "raise", "require", "super", "switch",
    "typeof", "yield",
}


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


def _entities(text, source, code_refs=None):
    """code_refs: pre-extracted (AST-accurate) class/function node refs for this
    chunk. When given, the regex class/def scan is skipped for them; the
    concept and file-path scans are text-level and always apply."""
    found = []
    seen = set()

    def add(kind, name):
        name = _clean(name)
        key = (kind, name)
        if name and key not in seen and name.lower() not in STOP_ENTITIES:
            seen.add(key)
            found.append(_node_ref(kind, name))

    if code_refs is None:
        for item in re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]+)", text):
            add("class", item)
        for item in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
            add("function", f"{item}()")
        for item in re.findall(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
            add("function", f"{item}()")
    else:
        for ref in code_refs:
            key = (ref["kind"], ref["name"])
            if ref["name"] and key not in seen:
                seen.add(key)
                found.append(ref)
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
        low = item.lower()
        if low in STOP_ENTITIES or low in _REGEX_CALL_KEYWORDS:
            continue
        if item in {"def", "class", "function"}:
            continue
        target_ref = _node_ref("function", f"{item}()")
        _node(nodes, target_ref, evidence)
        _edge(edges, source, "calls", target_ref, evidence)


def _workspace_file_text(chunk):
    """Full on-disk text for a chunk's file, or None when the file can't be
    read safely or changed since indexing (AST line numbers would no longer
    line up with the chunk's line ranges — fall back to regex on chunk text)."""
    rel = str(chunk.get("path") or "")
    if not rel:
        return None
    try:
        root = Path(workspace.resolve_path(chunk.get("workspace_id"))).resolve()
        file_path = (root / rel).resolve()
        if file_path != root and root not in file_path.parents:
            return None
        stat = file_path.stat()
        if stat.st_size > MAX_AST_BYTES:
            return None
        if chunk.get("mtime") is not None and stat.st_mtime != chunk.get("mtime"):
            return None
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _python_ast_facts(text):
    """Structural facts (with line numbers) from real AST parsing, so a call
    edge means an actual ast.Call — not any `identifier(` in a comment,
    string, or keyword position. Returns None when unparseable."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None
    imports, defines, calls = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or (node.names[0].name if node.names else "")
            if module:
                imports.append((module, node.lineno))
        elif isinstance(node, ast.ClassDef):
            defines.append(("class", node.name, node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defines.append(("function", f"{node.name}()", node.lineno))
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name and name not in _PY_BUILTINS and name.lower() not in STOP_ENTITIES:
                calls.append((f"{name}()", node.lineno))
    return {"imports": imports, "defines": defines, "calls": calls}


def _ast_facts_for(chunk, cache):
    source = chunk.get("source") or chunk.get("path") or ""
    if source not in cache:
        facts = None
        if Path(str(chunk.get("path") or "")).suffix.lower() == ".py":
            text = _workspace_file_text(chunk)
            if text is not None:
                facts = _python_ast_facts(text)
        cache[source] = facts
    return cache[source]


def _ast_fact_edges(facts, chunk, source_ref, evidence, edges, nodes, emitted):
    """Emit imports/defines/calls edges for AST facts inside this chunk's line
    range, so evidence cites the chunk that actually contains the statement.
    `emitted` dedupes facts that fall in the 12-line overlap between chunks.
    Returns the defined class/function refs for the mentions/related_to pass."""
    start = chunk.get("line_start") or 1
    end = chunk.get("line_end")

    def covered(lineno):
        return lineno >= start and (end is None or lineno <= end)

    chunk_defines = []
    for module, lineno in facts["imports"]:
        key = ("imports", module, lineno)
        if key in emitted or not covered(lineno):
            continue
        emitted.add(key)
        target_ref = _node_ref("concept", module)
        if not target_ref["name"]:
            continue
        _node(nodes, target_ref, evidence)
        _edge(edges, source_ref, "imports", target_ref, evidence, 3)
    for kind, name, lineno in facts["defines"]:
        key = ("defines", kind, name, lineno)
        if key in emitted or not covered(lineno):
            continue
        emitted.add(key)
        target_ref = _node_ref(kind, name)
        if not target_ref["name"]:
            continue
        weight = 3 if kind == "class" else 2
        _node(nodes, target_ref, evidence, weight)
        _edge(edges, source_ref, "defines", target_ref, evidence, weight)
        chunk_defines.append(target_ref)
    for name, lineno in facts["calls"]:
        key = ("calls", name, lineno)
        if key in emitted or not covered(lineno):
            continue
        emitted.add(key)
        target_ref = _node_ref("function", name)
        if not target_ref["name"]:
            continue
        _node(nodes, target_ref, evidence)
        _edge(edges, source_ref, "calls", target_ref, evidence)
    return chunk_defines


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
    ast_cache = {}
    ast_emitted = defaultdict(set)

    for chunk in scoped_chunks:
        path_name = chunk.get("path") or chunk.get("source", "")
        text = chunk.get("text", "")
        evidence = _evidence(chunk)
        file_ref = _node_ref(_path_kind(path_name, chunk.get("parser")), path_name)
        folder_ref = _folder_ref(path_name)
        _node(nodes, file_ref, evidence, 3)
        _node(nodes, folder_ref, evidence)
        _edge(edges, file_ref, "located_in", folder_ref, evidence, 2)

        suffix = Path(str(path_name)).suffix.lower()
        facts = _ast_facts_for(chunk, ast_cache)
        if facts is not None:
            code_refs = _ast_fact_edges(
                facts, chunk, file_ref, evidence, edges, nodes,
                ast_emitted[chunk.get("source") or path_name],
            )
            ents = _entities(text, path_name, code_refs=code_refs)
        else:
            ents = _entities(text, path_name)
            if suffix in SCRIPT_EXTS:
                _import_edges(text, file_ref, evidence, edges, nodes)
                _definition_edges(text, file_ref, evidence, edges, nodes)
                _call_edges(text, file_ref, evidence, edges, nodes)
        _reference_edges(text, file_ref, evidence, edges, nodes)

        for ent in ents:
            _node(nodes, ent, evidence)
            _edge(edges, file_ref, "mentions", ent, evidence)

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


RELATION_TYPES = {"calls", "imports", "defines", "references", "mentions", "related_to", "located_in"}


def query_relations(entity, relation=None, direction="both", limit=25):
    """Answer structural queries ("what calls X", "what does Y import") by
    traversing typed edges, instead of the keyword-overlap scoring search()
    uses. direction is relative to the entity: "out" = entity is the edge
    source, "in" = entity is the edge target."""
    graph = _load()
    needle = str(entity or "").strip().lower()
    if needle.endswith("()"):
        needle = needle[:-2]
    rel = str(relation or "").strip().lower()
    if rel in {"", "any", "all"}:
        rel = None
    if direction not in {"in", "out", "both"}:
        direction = "both"
    empty = {"entity": entity, "relation": rel or "any", "direction": direction,
             "matched_nodes": [], "edges": [], "count": 0}
    if not needle:
        return empty

    def matches(name, kind):
        raw = str(name or "").lower()
        base = raw[:-2] if raw.endswith("()") else raw
        if base == needle:
            return True
        # Paths also match on basename so "engine.py" finds "src/engine.py".
        if kind in {"file", "folder", "document"}:
            return base.split("/")[-1] == needle or base.endswith("/" + needle)
        return False

    matched = [n for n in graph.get("nodes", []) if matches(n.get("name"), n.get("kind"))]
    out_edges = []
    for edge in graph.get("edges", []):
        e_rel = edge.get("relation") or edge.get("type")
        if rel and e_rel != rel:
            continue
        src_hit = matches(edge.get("source"), edge.get("source_kind"))
        tgt_hit = matches(edge.get("target"), edge.get("target_kind"))
        if direction == "out" and not src_hit:
            continue
        if direction == "in" and not tgt_hit:
            continue
        if not (src_hit or tgt_hit):
            continue
        out_edges.append({
            "source": edge.get("source"),
            "source_kind": edge.get("source_kind"),
            "relation": e_rel,
            "target": edge.get("target"),
            "target_kind": edge.get("target_kind"),
            "direction": "out" if src_hit else "in",
            "weight": edge.get("weight", 1),
            "confidence": edge.get("confidence"),
            "why": edge.get("why"),
            "evidence": (edge.get("evidence") or [])[:3],
        })
    out_edges.sort(key=lambda e: e.get("weight", 0), reverse=True)
    try:
        cap = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        cap = 25
    out_edges = out_edges[:cap]
    return {
        "entity": entity,
        "relation": rel or "any",
        "direction": direction,
        "matched_nodes": [
            {"id": n["id"], "name": n["name"], "kind": n["kind"], "weight": n.get("weight", 1)}
            for n in matched[:10]
        ],
        "edges": out_edges,
        "count": len(out_edges),
    }


def reset():
    _save(_blank())
    return stats()
