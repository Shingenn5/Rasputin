import tempfile
import unittest
from pathlib import Path

from scripts import verify_docs


class DocumentationValidationTests(unittest.TestCase):
    def make_root(self):
        temp = tempfile.TemporaryDirectory(prefix="rasputin-docs-")
        root = Path(temp.name)
        (root / "docs").mkdir()
        self.addCleanup(temp.cleanup)
        return root

    def write_handoff_contract(self, root):
        (root / "docs" / "MAINTAINER_HANDOFF.md").write_text(
            "\n".join(verify_docs.REQUIRED_HANDOFF_SNIPPETS),
            encoding="utf-8",
        )

    def test_missing_local_links_are_reported_but_fenced_examples_are_ignored(self):
        root = self.make_root()
        (root / "docs" / "good.md").write_text("# Good\n", encoding="utf-8")
        (root / "README.md").write_text(
            "[good](docs/good.md) [bad](docs/missing.md)\n\n"
            "```md\n[ignored](docs/not-real.md)\n```\n",
            encoding="utf-8",
        )

        result = verify_docs.validate(root, check_project_contracts=False)

        self.assertFalse(result["passed"])
        self.assertEqual([item["target"] for item in result["errors"]], ["docs/missing.md"])

    def test_generated_frontend_policy_rejects_stale_edit_instruction(self):
        root = self.make_root()
        (root / "README.md").write_text(
            "Edit frontend/ directly after changing the UI.\n"
            "Never hand-edit generated frontend/ files; edit frontend-src/ instead.\n",
            encoding="utf-8",
        )

        result = verify_docs.validate(root, check_project_contracts=False)

        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["kind"], "stale-generated-frontend-instruction")

    def test_project_contracts_require_onboarding_commands_and_ledger_statuses(self):
        root = self.make_root()
        (root / "README.md").write_text("# Rasputin\n", encoding="utf-8")
        onboarding = "\n".join(verify_docs.REQUIRED_ONBOARDING_SNIPPETS)
        (root / "docs" / "CODEX_ONBOARDING.md").write_text(onboarding, encoding="utf-8")
        self.write_handoff_contract(root)
        (root / "docs" / "RASPUTIN_IMPLEMENTATION_LEDGER.md").write_text(
            " ".join(verify_docs.STATUS_TOKENS), encoding="utf-8"
        )

        result = verify_docs.validate(root)

        self.assertTrue(result["passed"], result["errors"])

    def test_project_contracts_report_missing_status(self):
        root = self.make_root()
        (root / "docs" / "CODEX_ONBOARDING.md").write_text(
            "\n".join(verify_docs.REQUIRED_ONBOARDING_SNIPPETS), encoding="utf-8"
        )
        self.write_handoff_contract(root)
        (root / "docs" / "RASPUTIN_IMPLEMENTATION_LEDGER.md").write_text(
            "IMPLEMENTED VERIFIED PARTIAL PLANNED", encoding="utf-8"
        )

        result = verify_docs.validate(root)

        self.assertFalse(result["passed"])
        self.assertEqual(result["errors"][0]["kind"], "missing-ledger-status")
        self.assertEqual(result["errors"][0]["detail"], "BLOCKED")

    def test_project_contracts_require_handoff_sections(self):
        root = self.make_root()
        (root / "docs" / "CODEX_ONBOARDING.md").write_text(
            "\n".join(verify_docs.REQUIRED_ONBOARDING_SNIPPETS),
            encoding="utf-8",
        )
        (root / "docs" / "MAINTAINER_HANDOFF.md").write_text(
            "scripts\\audit_repository.py\nnpm.cmd run checkRepoSafety\n",
            encoding="utf-8",
        )
        (root / "docs" / "RASPUTIN_IMPLEMENTATION_LEDGER.md").write_text(
            " ".join(verify_docs.STATUS_TOKENS),
            encoding="utf-8",
        )

        result = verify_docs.validate(root)

        handoff_errors = [
            item for item in result["errors"]
            if item["kind"] == "missing-handoff-contract"
        ]
        self.assertEqual(
            [item["detail"] for item in handoff_errors],
            [
                "## Ownership map",
                "## Commenting standard",
                "## Definition of handoff-ready",
            ],
        )


if __name__ == "__main__":
    unittest.main()
