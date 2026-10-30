r"""Measure current retrieval with synthetic data in a disposable SQLite store.

Run from the repository root with .venv\Scripts\python.exe.
No server, model, network, or existing application data is used.
"""

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch


def measure(operation, repeats):
    operation()  # Warm imports, schema, and filesystem cache before sampling.
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {"median_ms": round(statistics.median(samples), 3),
            "max_ms": round(max(samples), 3), "samples": repeats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or any(count < 1 for count in args.chunks):
        parser.error("chunk counts and repeats must be positive")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    previous_data_dir = os.environ.get("RASPUTIN_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="rasputin-retrieval-benchmark-") as scratch:
            os.environ["RASPUTIN_DATA_DIR"] = scratch
            # The data-directory override MUST precede all backend imports.
            from backend.core import runtime_store as store
            from backend.rag import vector

            assert store.DATA_DIR.resolve() == Path(scratch).resolve()
            results = []
            for count in args.chunks:
                chunks = []
                for number in range(count):
                    text = (f"workspace module{number} native runtime model streaming "
                            "retrieval benchmark approval cancellation sqlite " * 8)
                    terms = vector.Counter(vector.query_terms(text))
                    chunks.append({"source": f"fixture/module{number}.py",
                                   "workspace_id": "benchmark", "path": f"module{number}.py",
                                   "chunk": 0, "text": text, "terms": dict(terms),
                                   "term_count": sum(terms.values()), "vector": vector._embed(text)})
                index = {"version": 2, "docs": [], "chunks": chunks}
                store.set_kv("rag_vector", index)
                query = "native runtime streaming"
                with patch.object(vector.workspace, "get_active", return_value={"active_id": "benchmark"}):
                    expected = vector.search(query)
                    assert len(expected["hits"]) == min(6, count)
                    assert all(hit["workspace_id"] == "benchmark" for hit in expected["hits"])
                    loaded = measure(vector._load, args.repeats)
                    end_to_end = measure(lambda: vector.search(query), args.repeats)
                    with patch.object(vector, "_load", return_value=index):
                        assert vector.search(query) == expected
                        ranking = measure(lambda: vector.search(query), args.repeats)
                results.append({"chunks": count, "serialized_bytes": len(store._json(index).encode()),
                                "load_sqlite_json": loaded, "search_with_load": end_to_end,
                                "search_in_memory": ranking})
            print(json.dumps({"python": sys.version.split()[0], "platform": sys.platform,
                              "fixture": "synthetic; warm cache; single process; no inference",
                              "results": results}, indent=2))
    finally:
        if previous_data_dir is None:
            os.environ.pop("RASPUTIN_DATA_DIR", None)
        else:
            os.environ["RASPUTIN_DATA_DIR"] = previous_data_dir


if __name__ == "__main__":
    main()
