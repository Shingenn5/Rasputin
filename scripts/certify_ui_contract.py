"""Certify the source-level UI contract for the Rasputin v1 finish line.

This is a deliberately bounded companion to the authenticated browser pass.
It checks that the shipped frontend source still exposes the separate
Workstation/Assistant entry points and the operator-facing memory, voice,
model-admission, and governed-command surfaces.  It never starts a server,
opens a browser, reads runtime data, or edits generated frontend output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rasputin.ui-contract-certification.v1"


REQUIRED_MARKERS: dict[str, tuple[str, ...]] = {
    "workstationAssistantEntryPoints": (
        "frontend-src/src/features/dashboard/DashboardView.jsx",
        'data-testid="work-mode-switcher"',
        'data-testid="dashboard-open-workstation"',
        'data-testid="dashboard-open-assistant"',
        'aria-label="Workstation and Assistant modes"',
    ),
    "assistantContracts": (
        "frontend-src/src/features/assistant/AssistantView.jsx",
        'data-testid="assistant-capability-contracts"',
        'data-testid="assistant-command-contract"',
        'data-testid="assistant-voice-model-readiness"',
        'data-testid="assistant-mcp-contract"',
        'data-testid="assistant-command-preview"',
    ),
    "voiceInteraction": (
        "frontend-src/src/features/assistant/AssistantView.jsx",
        'data-testid="assistant-voice-console"',
        'data-testid="assistant-voice-toggle"',
        'data-testid="assistant-voice-audio"',
        "/api/assistant/voice/turn",
        "getUserMedia({ audio: true })",
    ),
    "lastingMemory": (
        "frontend-src/src/features/runtime/RuntimeViews.jsx",
        'data-testid="memory-create-form"',
        'data-testid="memory-recall-explainer"',
        'data-testid="memory-recall-explanation"',
        "Why was this recalled?",
        "supersedesId",
    ),
    "modelPlacementAndAdmission": (
        "frontend-src/src/features/models/ModelsView.jsx",
        "blockedReasons",
        "Why it fits:",
        "prepareCatalogModelForWarsat",
        "frontend-src/src/features/warsat/WarsatView.jsx",
        'data-testid="warsat-resource-admission"',
        "Resource admission:",
    ),
}


def certify(root: Path = ROOT) -> dict:
    checks: dict[str, bool] = {}
    missing: dict[str, list[str]] = {}
    files_checked: set[str] = set()

    for check_id, markers in REQUIRED_MARKERS.items():
        current_file: Path | None = None
        current_text = ""
        check_passed = True
        missing_markers: list[str] = []
        for marker in markers:
            if marker.startswith("frontend-src/"):
                current_file = root / marker
                relative = marker
                files_checked.add(relative)
                if not current_file.is_file():
                    check_passed = False
                    missing_markers.append(marker)
                    current_text = ""
                else:
                    current_text = current_file.read_text(encoding="utf-8")
                continue
            if marker not in current_text:
                check_passed = False
                missing_markers.append(marker)
        checks[check_id] = check_passed
        if missing_markers:
            missing[check_id] = missing_markers

    passed = all(checks.values())
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "checks": checks,
        "missing": missing,
        "evidence": {
            "sourceFilesChecked": sorted(files_checked),
            "generatedFrontendTouched": False,
            "browserInteraction": False,
            "runtimeStarted": False,
        },
        "nextActions": [] if passed else ["Restore the missing source-level UI contract markers and rerun this certification."],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to inspect")
    args = parser.parse_args(argv)
    try:
        report = certify(args.root.expanduser().resolve())
    except (OSError, UnicodeError, ValueError) as exc:
        report = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed",
            "passed": False,
            "error": str(exc)[:1000],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
