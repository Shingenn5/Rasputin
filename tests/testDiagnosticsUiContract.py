import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend-src" / "src" / "features" / "settings" / "DiagnosticsSettings.jsx").read_text(encoding="utf-8")


class DiagnosticsUiContractTests(unittest.TestCase):
    def test_diagnostics_and_recovery_expose_accessible_lifecycle_states(self):
        for marker in (
            'data-testid="diagnostic-loading"',
            'data-testid="recovery-loading"',
            'data-testid={error.context === "recovery" ? "recovery-error" : "diagnostic-error"}',
            'data-testid="recovery-result"',
        ):
            self.assertIn(marker, SOURCE)
        self.assertIn('data-testid={results.status === "healthy" ? "diagnostic-success" : "diagnostic-status"}', SOURCE)
        self.assertIn('role="status" aria-live="polite"', SOURCE)
        self.assertIn('role="alert" aria-live="assertive"', SOURCE)
        self.assertIn('<strong>Next:</strong>', SOURCE)

    def test_failed_operator_conditions_have_frontend_remediation_fallbacks(self):
        expected_guidance = (
            "stale runtime ownership",
            "unavailable tool provider",
            "Docker Desktop and WSL",
            "workspace membership and approval permissions",
            "correct the reported dependency or permission",
        )
        for guidance in expected_guidance:
            self.assertIn(guidance, SOURCE)
        self.assertIn("function nextActionFor(check)", SOURCE)
        self.assertIn("check.nextAction", SOURCE)

    def test_recovery_contracts_and_destructive_confirmation_remain_intact(self):
        for endpoint in (
            "/api/recovery/backup",
            "/api/recovery/export",
            "/api/recovery/delete-preview",
            "/api/recovery/delete",
        ):
            self.assertIn(endpoint, SOURCE)
        self.assertIn('window.confirm("Delete your Rasputin sessions, tasks, memory, and assistant records? This cannot be undone.")', SOURCE)
        self.assertIn('confirmation: "DELETE MY RASPUTIN DATA"', SOURCE)
        self.assertIn("dryRun: false", SOURCE)


if __name__ == "__main__":
    unittest.main()
