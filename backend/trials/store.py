"""SQLite persistence layer for Trials."""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock

from backend.core.datadir import data_dir

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = data_dir()
DB_PATH = DATA_DIR / "trials.sqlite3"

_lock = Lock()


def _connect():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _new_id(prefix="trial"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _now():
    return time.time()


def _json_dumps(obj):
    return json.dumps(obj) if obj is not None else None


def _json_loads(text):
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def init_db():
    """Create tables if they don't exist."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'model',
                status TEXT NOT NULL DEFAULT 'draft',
                workspace TEXT DEFAULT '',
                owner TEXT DEFAULT 'admin',
                config TEXT DEFAULT '{}',
                metrics TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                inputs TEXT DEFAULT '{}',
                outputs TEXT DEFAULT '[]',
                metrics TEXT DEFAULT '{}',
                duration_ms INTEGER DEFAULT 0,
                error TEXT DEFAULT '',
                created_at REAL NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'questions',
                entries TEXT DEFAULT '[]',
                version INTEGER DEFAULT 1,
                tags TEXT DEFAULT '[]',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS benchmarks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                experiment_ids TEXT DEFAULT '[]',
                config TEXT DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                scores TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scorecards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                subject_type TEXT DEFAULT '',
                subject_id TEXT DEFAULT '',
                scores TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comparisons (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                experiment_ids TEXT DEFAULT '[]',
                winner TEXT DEFAULT '',
                metrics TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'experiment',
                content_md TEXT DEFAULT '',
                experiment_ids TEXT DEFAULT '[]',
                created_at REAL NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ─── Experiments ───

def list_experiments(type_filter=None, status_filter=None, limit=100):
    conn = _connect()
    try:
        sql = "SELECT * FROM experiments"
        params = []
        conditions = []
        if type_filter:
            conditions.append("type = ?")
            params.append(type_filter)
        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_experiment(r) for r in rows]
    finally:
        conn.close()


def get_experiment(experiment_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        if not row:
            return None
        exp = _row_to_experiment(row)
        runs = conn.execute(
            "SELECT * FROM runs WHERE experiment_id = ? ORDER BY created_at DESC",
            (experiment_id,),
        ).fetchall()
        exp["runs"] = [_row_to_run(r) for r in runs]
        return exp
    finally:
        conn.close()


def create_experiment(name, exp_type="model", config=None, workspace="", owner="admin", tags=None):
    exp_id = _new_id("exp")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO experiments (id, name, type, status, workspace, owner, config, metrics, tags, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?, '{}', ?, ?, ?)",
            (exp_id, name, exp_type, workspace, owner, _json_dumps(config or {}), _json_dumps(tags or []), now, now),
        )
        conn.commit()
        return get_experiment(exp_id)
    finally:
        conn.close()


def update_experiment(experiment_id, **fields):
    conn = _connect()
    try:
        sets = []
        params = []
        for key in ("name", "status", "workspace", "owner"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        for key in ("config", "metrics", "tags"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(_json_dumps(fields[key]))
        if not sets:
            return get_experiment(experiment_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(experiment_id)
        conn.execute(f"UPDATE experiments SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return get_experiment(experiment_id)
    finally:
        conn.close()


def delete_experiment(experiment_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()
        return {"deleted": True, "id": experiment_id}
    finally:
        conn.close()


# ─── Runs ───

def list_runs(experiment_id):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM runs WHERE experiment_id = ? ORDER BY created_at DESC",
            (experiment_id,),
        ).fetchall()
        return [_row_to_run(r) for r in rows]
    finally:
        conn.close()


def get_run(run_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None
    finally:
        conn.close()


def create_run(experiment_id, inputs=None):
    run_id = _new_id("run")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO runs (id, experiment_id, status, inputs, outputs, metrics, duration_ms, error, created_at) VALUES (?, ?, 'running', ?, '[]', '{}', 0, '', ?)",
            (run_id, experiment_id, _json_dumps(inputs or {}), now),
        )
        conn.commit()
        return get_run(run_id)
    finally:
        conn.close()


def update_run(run_id, **fields):
    conn = _connect()
    try:
        sets = []
        params = []
        for key in ("status", "error"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        for key in ("inputs", "outputs", "metrics"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(_json_dumps(fields[key]))
        if "duration_ms" in fields:
            sets.append("duration_ms = ?")
            params.append(int(fields["duration_ms"]))
        if not sets:
            return get_run(run_id)
        params.append(run_id)
        conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return get_run(run_id)
    finally:
        conn.close()


# ─── Datasets ───

def list_datasets():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
        return [_row_to_dataset(r) for r in rows]
    finally:
        conn.close()


def get_dataset(dataset_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
        return _row_to_dataset(row) if row else None
    finally:
        conn.close()


def create_dataset(name, ds_type="questions", entries=None, tags=None):
    ds_id = _new_id("ds")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO datasets (id, name, type, entries, version, tags, created_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
            (ds_id, name, ds_type, _json_dumps(entries or []), _json_dumps(tags or []), now),
        )
        conn.commit()
        return get_dataset(ds_id)
    finally:
        conn.close()


def delete_dataset(dataset_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        conn.commit()
        return {"deleted": True, "id": dataset_id}
    finally:
        conn.close()


# ─── Benchmarks ───

def list_benchmarks():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM benchmarks ORDER BY created_at DESC").fetchall()
        return [_row_to_benchmark(r) for r in rows]
    finally:
        conn.close()


def get_benchmark(benchmark_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM benchmarks WHERE id = ?", (benchmark_id,)).fetchone()
        return _row_to_benchmark(row) if row else None
    finally:
        conn.close()


def create_benchmark(name, experiment_ids=None, config=None, status="pending", scores=None):
    bm_id = _new_id("bm")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO benchmarks (id, name, experiment_ids, config, status, scores, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bm_id, name, _json_dumps(experiment_ids or []), _json_dumps(config or {}), status, _json_dumps(scores or {}), now),
        )
        conn.commit()
        return get_benchmark(bm_id)
    finally:
        conn.close()


def update_benchmark(benchmark_id, **fields):
    conn = _connect()
    try:
        sets = []
        params = []
        for key in ("name", "status"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        for key in ("experiment_ids", "config", "scores"):
            if key in fields:
                sets.append(f"{key} = ?")
                params.append(_json_dumps(fields[key]))
        if not sets:
            return get_benchmark(benchmark_id)
        params.append(benchmark_id)
        conn.execute(f"UPDATE benchmarks SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return get_benchmark(benchmark_id)
    finally:
        conn.close()


# ─── Comparisons ───

def list_comparisons():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM comparisons ORDER BY created_at DESC").fetchall()
        return [_row_to_comparison(r) for r in rows]
    finally:
        conn.close()


def get_comparison(comparison_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
        return _row_to_comparison(row) if row else None
    finally:
        conn.close()


def create_comparison(name, experiment_ids=None, winner="", metrics=None):
    comp_id = _new_id("cmp")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO comparisons (id, name, experiment_ids, winner, metrics, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (comp_id, name, _json_dumps(experiment_ids or []), winner, _json_dumps(metrics or {}), now),
        )
        conn.commit()
        return get_comparison(comp_id)
    finally:
        conn.close()


# ─── Scorecards ───

def list_scorecards():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM scorecards ORDER BY created_at DESC").fetchall()
        return [_row_to_scorecard(r) for r in rows]
    finally:
        conn.close()


def get_scorecard(scorecard_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM scorecards WHERE id = ?", (scorecard_id,)).fetchone()
        return _row_to_scorecard(row) if row else None
    finally:
        conn.close()


def create_scorecard(name, subject_type="", subject_id="", scores=None):
    sc_id = _new_id("sc")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO scorecards (id, name, subject_type, subject_id, scores, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sc_id, name, subject_type, subject_id, _json_dumps(scores or {}), now),
        )
        conn.commit()
        return get_scorecard(sc_id)
    finally:
        conn.close()


# ─── Reports ───

def list_reports():
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()
        return [_row_to_report(r) for r in rows]
    finally:
        conn.close()


def get_report(report_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return _row_to_report(row) if row else None
    finally:
        conn.close()


def create_report(name, report_type="experiment", content_md="", experiment_ids=None):
    rpt_id = _new_id("rpt")
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO reports (id, name, type, content_md, experiment_ids, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (rpt_id, name, report_type, content_md, _json_dumps(experiment_ids or []), now),
        )
        conn.commit()
        return get_report(rpt_id)
    finally:
        conn.close()


# ─── Row converters ───

def _row_to_experiment(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "status": row["status"],
        "workspace": row["workspace"],
        "owner": row["owner"],
        "config": _json_loads(row["config"]),
        "metrics": _json_loads(row["metrics"]),
        "tags": _json_loads(row["tags"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _row_to_run(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "experimentId": row["experiment_id"],
        "status": row["status"],
        "inputs": _json_loads(row["inputs"]),
        "outputs": _json_loads(row["outputs"]),
        "metrics": _json_loads(row["metrics"]),
        "durationMs": row["duration_ms"],
        "error": row["error"],
        "createdAt": row["created_at"],
    }


def _row_to_dataset(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "entries": _json_loads(row["entries"]),
        "version": row["version"],
        "tags": _json_loads(row["tags"]),
        "createdAt": row["created_at"],
    }


def _row_to_benchmark(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "experimentIds": _json_loads(row["experiment_ids"]),
        "config": _json_loads(row["config"]),
        "status": row["status"],
        "scores": _json_loads(row["scores"]),
        "createdAt": row["created_at"],
    }


def _row_to_scorecard(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "subjectType": row["subject_type"],
        "subjectId": row["subject_id"],
        "scores": _json_loads(row["scores"]),
        "createdAt": row["created_at"],
    }


def _row_to_comparison(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "experimentIds": _json_loads(row["experiment_ids"]),
        "winner": row["winner"],
        "metrics": _json_loads(row["metrics"]),
        "createdAt": row["created_at"],
    }


def _row_to_report(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "contentMd": row["content_md"],
        "experimentIds": _json_loads(row["experiment_ids"]),
        "createdAt": row["created_at"],
    }
