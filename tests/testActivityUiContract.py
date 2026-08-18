import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TASKS = (ROOT / "frontend-src/src/features/tasks/TasksView.jsx").read_text(encoding="utf-8")
STYLES = (ROOT / "frontend-src/src/styles/rasputin.css").read_text(encoding="utf-8")


class ActivityUiContractTests(unittest.TestCase):
    def test_system_health_does_not_claim_unmeasured_values(self):
        self.assertNotIn("Online - 32ms", TASKS)
        self.assertNotIn(">Connected</div>", TASKS)
        self.assertNotIn("Active - 12.4 MB", TASKS)
        self.assertGreaterEqual(TASKS.count("Unknown - refresh to check"), 3)
        self.assertIn("Refresh activity", TASKS)

    def test_recovery_controls_are_operable_or_bounded(self):
        self.assertIn("onClick={onDetails} disabled={!onDetails}>Debug Stack Trace", TASKS)
        self.assertIn("onClick={onDetails} disabled={!onDetails}><FileText", TASKS)
        self.assertIn("disabled={!task.logs?.length && !task.trace?.length}", TASKS)
        self.assertIn("No task logs or trace are available to download.", TASKS)
        self.assertIn("Array.isArray(task?.logs)", TASKS)
        self.assertIn("Array.isArray(task?.trace)", TASKS)

    def test_activity_tabs_have_responsive_keyboard_friendly_contract(self):
        self.assertIn('role="tablist"', TASKS)
        self.assertIn('role="tab"', TASKS)
        self.assertIn("aria-selected={tab === t}", TASKS)
        self.assertIn(".activity-tabs-scroll", STYLES)
        self.assertIn("overflow-x: auto", STYLES)
        self.assertIn("Scroll for more activity views", STYLES)


if __name__ == "__main__":
    unittest.main()
