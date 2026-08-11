import unittest
from pathlib import Path


class MemoryUiContractTests(unittest.TestCase):
    def test_memory_page_exposes_owner_scoped_recall_explanation(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "frontend-src"
            / "src"
            / "features"
            / "runtime"
            / "RuntimeViews.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn('data-testid="memory-recall-explainer"', source)
        self.assertIn("Why these memories were returned", source)
        self.assertIn("owner-scoped memory", source)
        self.assertIn("Why was this recalled?", source)
        self.assertIn("matchedTerms", source)
        self.assertIn("scopeReason", source)
        self.assertIn("Relevance score", source)
        self.assertIn('data-testid={`memory-recall-details-${item.id}`}', source)


if __name__ == "__main__":
    unittest.main()
