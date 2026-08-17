import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChatUiContractTests(unittest.TestCase):
    def test_composer_groups_message_tools_and_exposes_readable_labels(self):
        source = (ROOT / "frontend-src" / "src" / "features" / "chat" / "HomeView.jsx").read_text(encoding="utf-8")
        self.assertIn('role="group" aria-label="Message tools"', source)
        self.assertIn('role="group" aria-label="Response settings"', source)
        self.assertIn('data-testid="composer-attach-button"', source)
        self.assertIn('data-testid="composer-command-button"', source)
        self.assertIn('<span className="composer-control-text">Attach</span>', source)
        self.assertIn('<span className="composer-control-text">Commands</span>', source)

    def test_message_details_show_estimated_output_tps_without_phase_percent(self):
        source = (ROOT / "frontend-src" / "src" / "features" / "chat" / "HomeView.jsx").read_text(encoding="utf-8")
        self.assertIn('data-testid="message-generation-tps"', source)
        self.assertIn("Output TPS", source)
        self.assertIn("generationMetrics", source)
        self.assertIn('status === "queued" ? "Queued"', source)
        self.assertNotIn('`${Number(task.progress || 0)}%`', source)

    def test_model_download_percent_is_rendered_only_when_trusted(self):
        source = (ROOT / "frontend-src" / "src" / "features" / "models" / "ModelsView.jsx").read_text(encoding="utf-8")
        self.assertIn("function trustedDownloadProgress", source)
        self.assertIn('download?.progressTrusted === true', source)
        self.assertIn("percentage unavailable", source)
        self.assertIn('data-testid="model-download-progress"', source)
        self.assertNotIn("dl.progress.toFixed", source)

    def test_task_drawer_uses_activity_and_tps_instead_of_unverified_progress(self):
        source = (ROOT / "frontend-src" / "src" / "features" / "tasks" / "TaskDetailsDrawer.jsx").read_text(encoding="utf-8")
        self.assertIn('label="Activity"', source)
        self.assertIn('label="Output TPS"', source)
        self.assertIn('task.generationMetrics', source)
        self.assertNotIn('label="Progress" value={`${Number(task.progress || 0)}%`}', source)


if __name__ == "__main__":
    unittest.main()
