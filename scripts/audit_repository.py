"""Measure Rasputin's tracked maintenance surface without external packages.

The audit reads Git-tracked files only. Generated dependencies, runtime state,
build output, and secondary worktrees must not inflate the handoff baseline.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tokenize
from collections import Counter
from pathlib import Path
from typing import Iterable


SOURCE_EXTENSIONS = {
    ".cjs", ".css", ".html", ".js", ".jsx", ".mjs", ".nsh", ".ps1",
    ".py", ".pyi", ".sh", ".ts", ".tsx",
}
TEXT_EXTENSIONS = SOURCE_EXTENSIONS | {
    ".cfg", ".dockerignore", ".example", ".gitignore", ".ini", ".json",
    ".md", ".spec", ".toml", ".txt", ".yaml", ".yml",
}
JS_EXTENSIONS = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}
DOCUMENT_EXTENSIONS = {".docx", ".md", ".pdf"}
ASSET_EXTENSIONS = {".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
OWNED_SOURCE_CATEGORIES = {
    "backend source",
    "desktop source",
    "frontend source",
    "scripts/tooling",
}
TEST_NAME = re.compile(
    r"(^|/)(tests?|fixtures)(/|$)|(^|/)test[^/]*\.(?:py|js|jsx|mjs|cjs)$|\.(?:test|spec)\."
)
JS_EXPORT = re.compile(
    r"(?m)^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+"
)


def tracked_paths(root: Path) -> list[str]:
    """Return paths in Git's index, normalized to forward slashes."""

    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot read tracked files from {root}: {exc}") from exc
    return sorted(
        item.decode("utf-8", "surrogateescape").replace("\\", "/")
        for item in output.split(b"\0")
        if item
    )


def is_test_path(relative: str) -> bool:
    """Return whether a repository-relative path belongs to test support."""

    return bool(TEST_NAME.search(relative.lower()))


def category_for(relative: str) -> str:
    """Assign one non-overlapping maintenance category to a tracked path."""

    relative = relative.replace("\\", "/")
    lower = relative.lower()
    path = Path(relative)
    extension = path.suffix.lower()
    if lower.startswith("docs/") or extension in DOCUMENT_EXTENSIONS:
        return "documentation"
    if is_test_path(lower):
        return "tests"
    if (lower.startswith("backend/") or lower == "server.py") and extension in SOURCE_EXTENSIONS:
        return "backend source"
    if lower.startswith("frontend-src/") and extension in SOURCE_EXTENSIONS:
        return "frontend source"
    if lower.startswith("desktop/") and extension in SOURCE_EXTENSIONS:
        return "desktop source"
    if (
        lower.startswith("scripts/")
        or ("/" not in lower and extension in {".nsh", ".ps1", ".sh"})
    ) and extension in SOURCE_EXTENSIONS:
        return "scripts/tooling"
    if lower.startswith(("assets/", "build/", "deploy/", "runtime/")) or extension in ASSET_EXTENSIONS:
        return "runtime/assets/packaging"
    if extension in {".json", ".toml", ".yaml", ".yml", ".example", ".gitignore", ".dockerignore"}:
        return "configuration/dependencies"
    if path.name in {"Dockerfile", "requirements.txt", "requirements-desktop.txt"}:
        return "configuration/dependencies"
    return "other"


def _read_text(path: Path) -> str | None:
    """Read UTF-8-compatible repository text without failing the whole audit."""

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _python_documentation(path: Path) -> Counter:
    """Measure module, public API, and comment coverage for one Python file."""

    metrics = Counter()
    text = _read_text(path)
    if text is None:
        metrics["unreadableFiles"] += 1
        return metrics
    try:
        tree = ast.parse(text)
    except SyntaxError:
        metrics["parseFailures"] += 1
        return metrics

    metrics["modules"] += 1
    metrics["documentedModules"] += bool(ast.get_docstring(tree, clean=False))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics["functions"] += 1
            if not node.name.startswith("_"):
                metrics["publicFunctions"] += 1
                metrics["documentedPublicFunctions"] += bool(
                    ast.get_docstring(node, clean=False)
                )
            if getattr(node, "end_lineno", None):
                metrics["functionsOver100Lines"] += (
                    node.end_lineno - node.lineno + 1 > 100
                )
        elif isinstance(node, ast.ClassDef):
            metrics["classes"] += 1
            if not node.name.startswith("_"):
                metrics["publicClasses"] += 1
                metrics["documentedPublicClasses"] += bool(
                    ast.get_docstring(node, clean=False)
                )

    try:
        with path.open("rb") as handle:
            comment_lines = {
                token.start[0]
                for token in tokenize.tokenize(handle.readline)
                if token.type == tokenize.COMMENT
            }
        metrics["commentLines"] += len(comment_lines)
    except (OSError, IndentationError, tokenize.TokenError):
        metrics["tokenizeFailures"] += 1
    return metrics


def _javascript_documentation(path: Path) -> Counter:
    """Measure exported declarations and JSDoc blocks for one JS-family file."""

    metrics = Counter()
    text = _read_text(path)
    if text is None:
        metrics["unreadableFiles"] += 1
        return metrics
    metrics["files"] += 1
    metrics["exports"] += len(JS_EXPORT.findall(text))
    metrics["jsdocBlocks"] += text.count("/**")
    return metrics


def analyze(root: Path, paths: Iterable[str] | None = None, *, top: int = 20) -> dict:
    """Build a deterministic handoff report for tracked repository content."""

    root = root.resolve()
    paths = list(tracked_paths(root) if paths is None else paths)
    categories: Counter = Counter()
    category_lines: Counter = Counter()
    source_sizes: list[tuple[int, str]] = []
    python_docs: Counter = Counter()
    javascript_docs: Counter = Counter()
    missing_paths: list[str] = []

    for raw_relative in paths:
        relative = raw_relative.replace("\\", "/")
        path = root / relative
        category = category_for(relative)
        categories[category] += 1
        if not path.is_file():
            missing_paths.append(relative)
            continue
        extension = path.suffix.lower()
        text = (
            _read_text(path)
            if extension in TEXT_EXTENSIONS or path.name == "Dockerfile"
            else None
        )
        if text is not None:
            lines = len(text.splitlines())
            category_lines[category] += lines
            if extension in SOURCE_EXTENSIONS and category in OWNED_SOURCE_CATEGORIES:
                source_sizes.append((lines, relative))

        owned_python = (
            extension == ".py"
            and category in OWNED_SOURCE_CATEGORIES
        )
        owned_javascript = (
            extension in JS_EXTENSIONS
            and category in OWNED_SOURCE_CATEGORIES
        )
        if owned_python:
            python_docs.update(_python_documentation(path))
        if owned_javascript:
            javascript_docs.update(_javascript_documentation(path))

    source_file_count = sum(
        count
        for name, count in categories.items()
        if name in OWNED_SOURCE_CATEGORIES
    )
    return {
        "trackedFileCount": len(paths),
        "missingTrackedPaths": missing_paths,
        "categories": {
            name: {"files": categories[name], "lines": category_lines[name]}
            for name in sorted(categories)
        },
        "ownedSourceFileCount": source_file_count,
        "sourceThresholds": {
            "over300Lines": sum(lines > 300 for lines, _ in source_sizes),
            "over500Lines": sum(lines > 500 for lines, _ in source_sizes),
            "over1000Lines": sum(lines > 1000 for lines, _ in source_sizes),
        },
        "largestSourceFiles": [
            {"path": relative, "lines": lines}
            for lines, relative in sorted(source_sizes, reverse=True)[: max(0, top)]
        ],
        "pythonDocumentation": dict(sorted(python_docs.items())),
        "javascriptDocumentation": dict(sorted(javascript_docs.items())),
    }


def _print_summary(report: dict) -> None:
    """Render a compact human-readable report for local maintainer use."""

    print(f"Tracked files: {report['trackedFileCount']}")
    print(f"Owned source files: {report['ownedSourceFileCount']}")
    print("\nCategories:")
    for name, values in report["categories"].items():
        print(
            f"  {name:28} {values['files']:4} files  "
            f"{values['lines']:7} lines"
        )
    print("\nLarge owned source files:")
    thresholds = report["sourceThresholds"]
    print(
        f"  >300: {thresholds['over300Lines']}  "
        f">500: {thresholds['over500Lines']}  "
        f">1000: {thresholds['over1000Lines']}"
    )
    for item in report["largestSourceFiles"]:
        print(f"  {item['lines']:6}  {item['path']}")
    print("\nDocumentation coverage inputs:")
    print(f"  Python: {report['pythonDocumentation']}")
    print(f"  JavaScript: {report['javascriptDocumentation']}")
    if report["missingTrackedPaths"]:
        print("\nTracked paths missing from the working tree:")
        for relative in report["missingTrackedPaths"]:
            print(f"  {relative}")


def main(argv: list[str] | None = None) -> int:
    """Run the repository audit command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="number of largest source files to report",
    )
    args = parser.parse_args(argv)
    try:
        report = analyze(args.root, top=args.top)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
