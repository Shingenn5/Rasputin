"""Coding-subtask trials: blind-compare models on a real coding task.

Unlike the chat quick-compare, outputs are scored objectively — syntax
check, expected-content hits, and (when shell execution is permitted)
actually running the operator-supplied tests against each candidate.
Runs share the legacy trials store so the existing Trials UI, reveal
flow, and routing endpoints work on them unchanged; model identity
stays hidden behind A/B/C/D labels until reveal.
"""

import ast
import asyncio
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from backend.core import audit
from backend.core import runtime_store as rts
from backend.core import security
from backend.core.response import AppError
from backend.models import registry as model_registry
from . import legacy
from .legacy import _chat, _load, _save, _public

TEST_TIMEOUT_SECONDS = 20
_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.S)


def _build_prompt(objective, code):
    parts = [
        "You are competing in a blind coding trial. Solve the coding subtask below.",
        f"Objective: {objective}",
    ]
    if code:
        parts.append("Starting code:\n```python\n" + code + "\n```")
    parts.append(
        "Return ONLY the complete final code in a single fenced code block. "
        "No explanations outside the block."
    )
    return "\n\n".join(parts)


def _extract_code(text):
    match = _FENCE_RE.search(str(text or ""))
    return (match.group(1) if match else str(text or "")).strip()


def _syntax_ok(candidate):
    try:
        ast.parse(candidate)
        return True
    except SyntaxError:
        return False


def _run_tests(candidate, tests):
    """Execute candidate code + operator tests in an isolated subprocess.

    -I gives isolated mode (no site-packages, no inherited env hooks); the
    file runs in a throwaway temp dir. Exit 0 means the asserts passed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trial_candidate.py"
        path.write_text(candidate + "\n\n" + tests + "\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(path)],
                capture_output=True, text=True, cwd=tmp,
                timeout=TEST_TIMEOUT_SECONDS,
            )
            return {"ran": True, "passed": proc.returncode == 0,
                    "output": (proc.stdout + proc.stderr).strip()[-2000:]}
        except subprocess.TimeoutExpired:
            return {"ran": True, "passed": False, "output": f"timed out after {TEST_TIMEOUT_SECONDS}s"}
        except Exception as exc:
            return {"ran": False, "passed": False, "output": str(exc)}


def _score_output(candidate, tests, expect, tests_allowed):
    expect = [item for item in (expect or []) if str(item or "").strip()]
    syntax_ok = _syntax_ok(candidate)
    expect_hits = sum(1 for item in expect if str(item) in candidate)
    result = {
        "syntaxOk": syntax_ok,
        "expectHits": expect_hits,
        "expectTotal": len(expect),
        "testsRan": False,
        "testsPassed": False,
        "testOutput": "",
    }
    if tests and tests_allowed and syntax_ok:
        run = _run_tests(candidate, tests)
        result["testsRan"] = run["ran"]
        result["testsPassed"] = run["ran"] and run["passed"]
        result["testOutput"] = run["output"]
    score = 0.0
    if result["testsPassed"]:
        score += 2.0
    if syntax_ok:
        score += 0.5
    if expect:
        score += 0.5 * (expect_hits / len(expect))
    result["score"] = round(score, 3)
    return result


async def coding_compare(objective, code="", tests="", expect=None, model_keys=None):
    objective = str(objective or "").strip()
    if not objective:
        raise ValueError("coding trial objective required")
    code = str(code or "")
    tests = str(tests or "")

    chosen = [key for key in (model_keys or []) if model_registry.get_model(key)]
    if not chosen:
        chosen = ["dry-run"]
    chosen = chosen[:4]

    # Executing operator tests against generated code is real local code
    # execution — only do it when shell execution is already permitted.
    tests_allowed = bool(security.load().get("allow_shell_execution", False))

    prompt = _build_prompt(objective, code)
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    outputs = []
    for index, key in enumerate(chosen):
        started = time.perf_counter()
        try:
            text = await _chat(key, [{"role": "user", "content": prompt}], temperature=0.2)
            status = "done"
            error = ""
        except Exception as exc:
            text = ""
            status = "error"
            error = str(exc)
        candidate = _extract_code(text) if status == "done" else ""
        scoring = (
            _score_output(candidate, tests, expect, tests_allowed)
            if status == "done"
            else {"syntaxOk": False, "expectHits": 0, "expectTotal": len(expect or []),
                  "testsRan": False, "testsPassed": False, "testOutput": "", "score": 0.0}
        )
        outputs.append({
            "id": rts.new_id("trialout"),
            "label": labels[index],
            "model_key": key,
            "status": status,
            "text": text,
            "error": error,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "scoring": scoring,
        })
        await asyncio.sleep(0)

    scored = [o for o in outputs if o["status"] == "done"]
    scored.sort(key=lambda o: (-o["scoring"]["score"], o["latency_ms"]))
    suggested = scored[0]["label"] if scored else ""

    run = {
        "id": rts.new_id("trial"),
        "kind": "coding",
        "prompt": objective,
        "objective": objective,
        "code": code,
        "tests": tests,
        "tests_executed": tests_allowed and bool(tests),
        "suggested_label": suggested,
        "outputs": outputs,
        "revealed": False,
        "created_at": time.time(),
    }
    data = _load()
    data["runs"] = [run] + data.get("runs", [])[:49]
    _save(data)
    audit.log("trial_coding_compare", {
        "runId": run["id"],
        "models": chosen,
        "testsExecuted": run["tests_executed"],
    })
    return _public(run, reveal=False)


def pin_role(run_id, output_id, role="coder"):
    """Assign the winning output's model to a registry role (default coder).

    Registry-level pin, unlike save_routing's preference override: after
    this, key_for_role(role) — and therefore code mode's execution phase —
    resolves to the pinned model immediately, no restart involved.
    """
    role = str(role or "coder").strip().lower()
    output_id = str(output_id or "").strip()
    if role not in model_registry.MODEL_ROLES:
        raise ValueError("unsupported registry role")
    if not output_id:
        raise ValueError("trial output required")

    data = _load()
    for item in data.get("runs", []):
        if item.get("id") != run_id:
            continue
        if not item.get("revealed"):
            raise ValueError("reveal trial before pinning a model role")
        output = next(
            (candidate for candidate in item.get("outputs", [])
             if candidate.get("id") == output_id or candidate.get("label") == output_id),
            None,
        )
        if not output:
            raise ValueError("trial output missing")
        if output.get("status") != "done":
            raise ValueError("only completed trial outputs can be pinned")
        model_key = output.get("model_key")
        updated = model_registry.set_role(model_key, role)
        route = {
            "role": role,
            "previous_role": updated.get("previous_role"),
            "model_key": model_key,
            "model_name": updated.get("name") or model_key,
            "output_id": output.get("id"),
            "output_label": output.get("label"),
        }
        item.setdefault("role_pins", {})[role] = {**route, "saved_at": time.time()}
        _save(data)
        audit.log("trial_role_pinned", route)
        return {"route": route, "run": _public(item, reveal=True)}
    raise ValueError("trial run missing")
