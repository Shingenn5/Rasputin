import unittest
from pathlib import Path


class V1ReleaseContractDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[1] / "docs" / "RASPUTIN_V1_RELEASE_CONTRACT.md"
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_contract_is_present_and_has_exactly_ten_slices(self):
        self.assertTrue(self.path.is_file())
        self.assertEqual(self.text.count("### Slice "), 10)
        self.assertIn("## Stop rule", self.text)
        self.assertIn("## Explicit non-goals", self.text)

    def test_contract_names_supported_paths_and_release_evidence(self):
        for phrase in (
            "Docker Server",
            "Native Server",
            "Windows Desktop",
            "macOS",
            "Linux",
            "scripts/verify_release_candidate.py",
            "scripts/verify_deployment_matrix.py",
            "scripts/rehearse_restore.py",
        ):
            self.assertIn(phrase, self.text)

    def test_contract_keeps_long_term_scope_out_of_v1(self):
        for phrase in (
            "custom Rasputin fine-tuning",
            "always-listening microphone",
            "arbitrary autonomous computer control",
            "external MCP server",
            "blind mixed-card vLLM tensor parallelism",
        ):
            self.assertIn(phrase, self.text)
        self.assertIn("post-v1", self.text)
        self.assertIn("backlog", self.text)
