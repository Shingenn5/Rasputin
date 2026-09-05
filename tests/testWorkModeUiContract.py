import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkModeUiContractTests(unittest.TestCase):
    def test_dashboard_exposes_separate_workstation_and_assistant_entry_points(self):
        source = (ROOT / "frontend-src" / "src" / "features" / "dashboard" / "DashboardView.jsx").read_text(encoding="utf-8")
        self.assertIn('data-testid="work-mode-switcher"', source)
        self.assertIn('aria-label="Workstation and Assistant modes"', source)
        self.assertIn('data-testid="dashboard-open-workstation"', source)
        self.assertIn('data-testid="dashboard-open-assistant"', source)
        self.assertIn("sharing the local safety and context boundaries", source)

    def test_minimal_sidebar_keeps_named_workstation_navigation(self):
        source = (ROOT / "frontend-src" / "src" / "components" / "shell" / "DashSidebar.jsx").read_text(encoding="utf-8")
        self.assertIn('aria-label="Workstation and assistant navigation"', source)
        self.assertIn('role="group"', source)
        self.assertIn('ariaLabel: "Chat workstation"', source)
        # The dashboard test covers Assistant entry; the daily sidebar stays minimal.
        self.assertIn('aria-label={item.ariaLabel || item.label}', source)


if __name__ == "__main__":
    unittest.main()
