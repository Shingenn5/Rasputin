"""Contract tests for the dependency-free repository maintenance audit."""

import tempfile
import unittest
from pathlib import Path

from scripts import audit_repository


class RepositoryAuditTests(unittest.TestCase):
    def make_root(self):
        temp = tempfile.TemporaryDirectory(prefix="rasputin-repo-audit-")
        root = Path(temp.name)
        self.addCleanup(temp.cleanup)
        return root

    def test_categories_are_non_overlapping_and_tests_take_precedence(self):
        self.assertEqual(
            audit_repository.category_for("backend/api/core.py"),
            "backend source",
        )
        self.assertEqual(
            audit_repository.category_for("backend/api/test_core.py"),
            "tests",
        )
        self.assertEqual(
            audit_repository.category_for("frontend-src/src/App.jsx"),
            "frontend source",
        )
        self.assertEqual(
            audit_repository.category_for("desktop/main.cjs"),
            "desktop source",
        )
        self.assertEqual(
            audit_repository.category_for("server.py"),
            "backend source",
        )
        self.assertEqual(
            audit_repository.category_for("docs/guide.md"),
            "documentation",
        )

    def test_analyze_measures_size_and_public_documentation(self):
        root = self.make_root()
        backend = root / "backend"
        frontend = root / "frontend-src" / "src"
        tests = root / "tests"
        backend.mkdir()
        frontend.mkdir(parents=True)
        tests.mkdir()
        (backend / "documented.py").write_text(
            '"""Module purpose."""\n\n'
            'def public(value):\n    """Return the supplied value."""\n'
            "    return value\n\n"
            "def _private():\n    return None\n",
            encoding="utf-8",
        )
        (frontend / "Widget.jsx").write_text(
            "/** Render a widget. */\n"
            "export function Widget() { return null; }\n",
            encoding="utf-8",
        )
        (tests / "test_example.py").write_text(
            "def test_example():\n    assert True\n",
            encoding="utf-8",
        )

        report = audit_repository.analyze(
            root,
            [
                "backend/documented.py",
                "frontend-src/src/Widget.jsx",
                "tests/test_example.py",
            ],
        )

        self.assertEqual(report["trackedFileCount"], 3)
        self.assertEqual(report["ownedSourceFileCount"], 2)
        self.assertEqual(report["categories"]["tests"]["files"], 1)
        self.assertEqual(
            report["pythonDocumentation"]["documentedModules"],
            1,
        )
        self.assertEqual(
            report["pythonDocumentation"]["documentedPublicFunctions"],
            1,
        )
        self.assertEqual(report["javascriptDocumentation"]["exports"], 1)
        self.assertEqual(report["javascriptDocumentation"]["jsdocBlocks"], 1)

    def test_missing_index_entries_are_reported_without_crashing(self):
        root = self.make_root()

        report = audit_repository.analyze(root, ["backend/deleted.py"])

        self.assertEqual(report["missingTrackedPaths"], ["backend/deleted.py"])
        self.assertEqual(report["categories"]["backend source"]["files"], 1)


if __name__ == "__main__":
    unittest.main()
