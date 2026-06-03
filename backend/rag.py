import hashlib
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from threading import Lock

from . import workspace

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INDEX_FILE = DATA_DIR / "rag_index.json"

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
SKIP_EXTS = {".pyc", ".log", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".exe", ".dll", ".zip"}
TEXT_EXTS = {
    ".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".csv", ".tsv",
    ".yml", ".yaml", ".toml", ".ini", ".sql", ".xml", ".svg"
}
VECTOR_DIMS = 384

_lock = Lock()


def _blank():
    return {"version": 2, "updated_at": None, "docs": [], "chunks": []}


def _load():
    DATA_DIR.mkdir(exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(json.dumps(_blank(), indent=2), encoding="utf-8")
    with _lock:
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = _blank()
    if data.get("version") != 2:
        return _blank()
    return data


def raw_index():
    return _load()


def _save(index):
    DATA_DIR.mkdir(exist_ok=True)
    index["updated_at"] = time.time()
    with _lock:
        INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")


def query_terms(text):
    return _tokenize(text)


def _tokenize(text):
    return [t for t in re.findall(r"[a-zA-Z0-9_./-]{2,}", str(text or "").lower()) if len(t) < 60]


def _hash_dim(term):
    digest = hashlib.blake2b(term.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % VECTOR_DIMS


def _embed(text):
    vec = Counter()
    for term in _tokenize(text):
        vec[str(_hash_dim(term))] += 1
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: round(v / norm, 6) for k, v in vec.items()}


def _cosine(left, right):
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0) for key, value in left.items())


def _read_text(path):
    if path.suffix.lower() not in TEXT_EXTS:
        return None
    if path.stat().st_size > 1_500_000:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    except Exception:
        return None


def _chunk_text(text, lines_per_chunk=80, overlap=12):
    lines = str(text or "").splitlines()
    if not lines:
        return []
    chunks = []
    step = max(1, lines_per_chunk - overlap)
    for start in range(0, len(lines), step):
        part = lines[start:start + lines_per_chunk]
        if not part:
            break
        joined = "\n".join(part).strip()
        if joined:
            chunks.append((joined, start + 1, start + len(part)))
        if start + lines_per_chunk >= len(lines):
            break
    return chunks


def _walk(target):
    if target.is_file():
        return [target]
    files = []
    for p in target.rglob("*"):
        if any(x in SKIP_DIRS for x in p.parts):
            continue
        if p.is_file() and p.suffix.lower() not in SKIP_EXTS:
            if p.resolve() == INDEX_FILE.resolve():
                continue
            files.append(p)
    return files


def _scope(path="."):
    active = workspace.get_active()
    target = workspace.resolve_path(path or active.get("active_path") or ".")
    item = workspace.workspace_for_path(target)
    if not item:
        raise ValueError("path outside approved workspaces")
    root = Path(item.get("absolute_path") or workspace.resolve_path(item.get("id"))).resolve()
    if root not in target.parents and target != root:
        raise ValueError("path outside approved workspace")
    return target, item, root


def _source(file_path, item, root):
    rel = str(file_path.relative_to(root)).replace("\\", "/")
    wid = item.get("id") or "workspace"
    return f"{wid}/{rel}"


def ingest(path=".", label=None):
    target, item, root = _scope(path)
    index = _load()
    files = _walk(target)
    touched = []
    new_chunks = []
    docs = []

    for file_path in files:
        text = _read_text(file_path)
        if text is None:
            continue
        source = _source(file_path, item, root)
        touched.append(source)
        rel = str(file_path.relative_to(root)).replace("\\", "/")
        doc = {
            "source": source,
            "workspace_id": item.get("id"),
            "workspace_name": item.get("name"),
            "path": rel,
            "label": label or rel,
            "mtime": file_path.stat().st_mtime,
            "bytes": file_path.stat().st_size,
        }
        docs.append(doc)
        for n, (chunk, line_start, line_end) in enumerate(_chunk_text(text)):
            terms = Counter(_tokenize(chunk))
            if not terms:
                continue
            new_chunks.append({
                "id": f"{source}#{n}",
                "source": source,
                "workspace_id": item.get("id"),
                "path": rel,
                "chunk": n,
                "line_start": line_start,
                "line_end": line_end,
                "text": chunk[:5000],
                "terms": dict(terms),
                "term_count": sum(terms.values()),
                "vector": _embed(chunk),
                "mtime": file_path.stat().st_mtime,
            })

    kept_docs = [d for d in index["docs"] if d.get("source") not in touched]
    kept_chunks = [c for c in index["chunks"] if c.get("source") not in touched]
    index["docs"] = kept_docs + docs
    index["chunks"] = kept_chunks + new_chunks
    _save(index)
    workspace.mark_indexed(item.get("id"), True)
    return {
        "path": str(target),
        "workspace_id": item.get("id"),
        "files_seen": len(files),
        "docs_indexed": len(docs),
        "chunks_indexed": len(new_chunks),
        "total_docs": len(index["docs"]),
        "total_chunks": len(index["chunks"]),
    }


def stats():
    index = _load()
    return {
        "version": index.get("version", 2),
        "docs": len(index["docs"]),
        "chunks": len(index["chunks"]),
        "updated_at": index.get("updated_at"),
        "sources": index["docs"][-25:],
    }


def _filter_chunks(chunks, path=None):
    if not path or path == ".":
        active = workspace.get_active()
        wid = active.get("active_id")
        return [c for c in chunks if c.get("workspace_id") == wid]
    target, item, root = _scope(path)
    prefix = str(target.relative_to(root)).replace("\\", "/") if target != root else ""
    out = []
    for chunk in chunks:
        if chunk.get("workspace_id") != item.get("id"):
            continue
        cpath = chunk.get("path", "")
        if not prefix or cpath == prefix or cpath.startswith(prefix + "/"):
            out.append(chunk)
    return out


def search(query, limit=6, path=None):
    index = _load()
    q_terms = Counter(_tokenize(query))
    q_vec = _embed(query)
    if not q_terms:
        return {"query": query, "hits": []}

    chunks = _filter_chunks(index["chunks"], path)
    doc_freq = Counter()
    for chunk in chunks:
        for term in chunk.get("terms", {}):
            doc_freq[term] += 1
    total = max(1, len(chunks))
    scored = []
    for chunk in chunks:
        terms = chunk.get("terms", {})
        lexical = 0.0
        for term, q_count in q_terms.items():
            c_count = terms.get(term, 0)
            if not c_count:
                continue
            idf = math.log((1 + total) / (1 + doc_freq[term])) + 1
            lexical += (q_count * c_count * idf) / max(1, chunk.get("term_count", 1))
        semantic = _cosine(q_vec, chunk.get("vector", {}))
        score = lexical + (semantic * 0.35)
        if score > 0:
            scored.append((score, chunk, lexical, semantic))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, chunk, lexical, semantic in scored[:max(1, min(int(limit), 20))]:
        hits.append({
            "score": round(score, 5),
            "lexical_score": round(lexical, 5),
            "semantic_score": round(semantic, 5),
            "source": chunk["source"],
            "workspace_id": chunk.get("workspace_id"),
            "path": chunk.get("path"),
            "chunk": chunk["chunk"],
            "line_start": chunk.get("line_start"),
            "line_end": chunk.get("line_end"),
            "mtime": chunk.get("mtime"),
            "text": chunk["text"],
            "citation": {
                "workspace_id": chunk.get("workspace_id"),
                "path": chunk.get("path"),
                "chunk": chunk.get("chunk"),
                "line_start": chunk.get("line_start"),
                "line_end": chunk.get("line_end"),
                "mtime": chunk.get("mtime"),
            },
        })
    return {"query": query, "hits": hits}


def chunks_for_path(path=None):
    index = _load()
    return _filter_chunks(index["chunks"], path)


def reset():
    _save(_blank())
    return stats()
