"""Validate Rasputin's local documentation contracts without network access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(\S+)")
STATUS_TOKENS = ("IMPLEMENTED", "VERIFIED", "PARTIAL", "PLANNED", "BLOCKED")
REQUIRED_ONBOARDING_SNIPPETS = (
    "python -m unittest tests.testBackendSmoke",
    "npm run build",
    "RASPUTIN_DATA_DIR=<temp-dir> PORT=8899 python server.py",
)


def markdown_files(root: Path) -> list[Path]:
    """Return user-facing Markdown files covered by this validator."""

    files = []
    readme = root / "README.md"
    if readme.is_file():
        files.append(readme)
    docs = root / "docs"
    if docs.is_dir():
        files.extend(sorted(path for path in docs.rglob("*.md") if path.is_file()))
    return sorted(set(files))


def _content_lines(path: Path):
    in_fence = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        yield 1, f"cannot decode as UTF-8: {exc}"
        return
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield number, line


def _target(raw_target: str) -> str:
    value = raw_target.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split()[0] if value else ""


def _is_external_or_route(target: str) -> bool:
    if not target or target.startswith("#") or target.startswith("/"):
        return True
    parsed = urlsplit(target)
    return parsed.scheme.lower() in {"http", "https", "mailto", "tel", "data", "file"}


def _local_target(source: Path, raw_target: str) -> Path | None:
    target = unquote(_target(raw_target))
    if _is_external_or_route(target):
        return None
    parsed = urlsplit(target)
    path_part = parsed.path
    if not path_part:
        return None
    return (source.parent / path_part).resolve()


def _stale_frontend_instruction(line: str) -> bool:
    lower = line.lower()
    if "frontend/" not in lower:
        return False
    if "never" in lower and re.search(r"\b(?:hand[- ]edit|edit|modify|change)\b", lower):
        return False
    if "source of truth" in lower and "frontend-src/" not in lower:
        return True
    return bool(
        re.search(
            r"\b(?:hand[- ]edit|edit|modify|change)\b\s+(?:the\s+)?(?:generated\s+)?[`']?frontend/",
            lower,
        )
    )


def validate(root: Path, *, check_project_contracts: bool = True) -> dict:
    """Return deterministic documentation findings for ``root``."""

    root = root.resolve()
    errors: list[dict] = []
    files = markdown_files(root)
    for path in files:
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = str(path)
        for number, line in _content_lines(path):
            if line.startswith("cannot decode"):
                errors.append({"kind": "encoding", "file": relative, "line": number, "detail": line})
                continue
            targets = MARKDOWN_LINK.findall(line)
            reference = REFERENCE_LINK.match(line)
            if reference:
                targets.append(reference.group(1))
            for raw_target in targets:
                local_path = _local_target(path, raw_target)
                if local_path is not None and not local_path.exists():
                    errors.append({
                        "kind": "missing-local-link",
                        "file": relative,
                        "line": number,
                        "target": _target(raw_target),
                    })
            if _stale_frontend_instruction(line):
                errors.append({
                    "kind": "stale-generated-frontend-instruction",
                    "file": relative,
                    "line": number,
                    "detail": "Edit frontend-src/ and rebuild generated frontend/; do not edit frontend/ directly.",
                })

    if check_project_contracts:
        onboarding = root / "docs" / "CODEX_ONBOARDING.md"
        if not onboarding.is_file():
            errors.append({"kind": "missing-required-file", "file": "docs/CODEX_ONBOARDING.md"})
        else:
            content = onboarding.read_text(encoding="utf-8")
            for snippet in REQUIRED_ONBOARDING_SNIPPETS:
                if snippet not in content:
                    errors.append({"kind": "missing-onboarding-command", "file": "docs/CODEX_ONBOARDING.md", "detail": snippet})

        ledger = root / "docs" / "RASPUTIN_IMPLEMENTATION_LEDGER.md"
        if not ledger.is_file():
            errors.append({"kind": "missing-required-file", "file": "docs/RASPUTIN_IMPLEMENTATION_LEDGER.md"})
        else:
            content = ledger.read_text(encoding="utf-8")
            for status in STATUS_TOKENS:
                if status not in content:
                    errors.append({"kind": "missing-ledger-status", "file": "docs/RASPUTIN_IMPLEMENTATION_LEDGER.md", "detail": status})

    return {"passed": not errors, "filesChecked": len(files), "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    result = validate(args.root)
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["passed"]:
        print(f"Documentation validation passed ({result['filesChecked']} Markdown files checked).")
    else:
        for error in result["errors"]:
            location = error.get("file", "repository")
            if error.get("line"):
                location += f":{error['line']}"
            detail = error.get("target") or error.get("detail") or error.get("kind")
            print(f"ERROR {location}: {detail}")
        print(f"Documentation validation failed with {len(result['errors'])} error(s).")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
