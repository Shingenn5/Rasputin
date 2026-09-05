import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend.trials import scorecards, store


class TrialsScorecardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rasputin-scorecards-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for attr, value in (("DATA_DIR", root), ("DB_PATH", root / "trials.sqlite3")):
            patcher = patch.object(store, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(scorecards.audit, "log")
        patcher.start()
        self.addCleanup(patcher.stop)
        store.init_db()

    def experiment(self, metrics=None, config=None):
        exp = store.create_experiment("Scorecard fixture", config=config)
        return store.update_experiment(exp["id"], status="completed", metrics=metrics or {})

    def test_empty_measurements_are_null_including_overall(self):
        exp = self.experiment()
        card = scorecards.generate_scorecard(exp["id"])
        self.assertTrue(all(value is None for value in card["scores"].values()))
        self.assertEqual("not_measured", card["evidence"]["state"])
        self.assertEqual(card, store.get_scorecard(card["id"]))
        json.dumps(card, allow_nan=False)

    def test_request_success_is_not_accuracy_or_efficiency(self):
        exp = self.experiment({
            "successCount": 3, "errorCount": 1, "modelCount": 1,
            "totalDurationMs": 500, "results": [{"successRate": 1}],
        }, config={"datasetId": "dataset-fixture"})
        card = scorecards.generate_scorecard(exp["id"])
        self.assertEqual(75, card["scores"]["reliability"])
        self.assertEqual(75, card["scores"]["overall"])
        for category in ("accuracy", "reasoning", "performance", "efficiency", "safety", "usability"):
            self.assertIsNone(card["scores"][category], category)
        evidence = card["evidence"]
        measurement = evidence["dimensions"]["reliability"]
        self.assertEqual(4, measurement["sampleCount"])
        self.assertEqual(3, measurement["successCount"])
        self.assertIn("Not estimated", measurement["uncertainty"])
        self.assertEqual(["reliability"], evidence["dimensions"]["overall"]["includedDimensions"])
        self.assertEqual("dataset-fixture", evidence["configuredDatasetId"])
        self.assertIsNone(evidence["datasetVersion"])
        self.assertEqual(500, evidence["observations"]["totalDurationMs"])
        self.assertEqual(exp["updatedAt"], evidence["experimentUpdatedAt"])

    def test_all_failed_requests_keep_measured_zero(self):
        exp = self.experiment({"successCount": 0, "errorCount": 2})
        card = scorecards.generate_scorecard(exp["id"])
        self.assertEqual(0, card["scores"]["reliability"])
        self.assertEqual(0, card["scores"]["overall"])
        self.assertEqual("measured", card["evidence"]["dimensions"]["reliability"]["state"])

    def test_invalid_or_partial_counts_and_rounded_rates_do_not_invent_samples(self):
        for metrics in (
            {"successCount": 3},
            {"successCount": -2, "errorCount": 3},
            {"successCount": float("nan"), "errorCount": 0},
            {"successCount": float("inf"), "errorCount": 0},
            {"successCount": True, "errorCount": 0},
            {"successCount": 1.5, "errorCount": 0},
            {"results": [{"successRate": 1}], "modelCount": 4},
            {"successCount": 0, "errorCount": 0},
        ):
            with self.subTest(metrics=metrics):
                card = scorecards.generate_scorecard(self.experiment(metrics)["id"])
                self.assertIsNone(card["scores"]["reliability"])
                self.assertIsNone(card["scores"]["overall"])
                json.dumps(card, allow_nan=False)

    def test_latest_run_nested_outcomes_are_used_without_counting_old_runs(self):
        exp = self.experiment({"results": [{"successRate": 1}]})
        old = store.create_run(exp["id"])
        store.update_run(old["id"], status="completed", outputs=[{"status": "done"}] * 5)
        latest = store.create_run(exp["id"])
        store.update_run(latest["id"], status="completed", outputs=[
            {"modelKey": "fixture", "outputs": [{"status": "done"}, {"status": "error"}]},
        ])
        # Fix ordering explicitly rather than depending on clock resolution.
        with sqlite3.connect(store.DB_PATH) as conn:
            conn.execute("UPDATE runs SET created_at = 1 WHERE id = ?", (old["id"],))
            conn.execute("UPDATE runs SET created_at = 2 WHERE id = ?", (latest["id"],))
        conn.close()
        card = scorecards.generate_scorecard(exp["id"])
        self.assertEqual(50, card["scores"]["reliability"])
        detail = card["evidence"]["dimensions"]["reliability"]
        self.assertEqual(2, detail["sampleCount"])
        self.assertEqual(latest["id"], detail["runId"])

    def test_incomplete_run_outcomes_are_not_reported_as_completed_samples(self):
        exp = self.experiment()
        run = store.create_run(exp["id"])
        for outputs in (
            [{"status": "done"}, {"status": "pending"}],
            [{"status": "done"}, None],
            [{"outputs": [{"status": "done"}, None]}],
            [{"outputs": "invalid"}],
        ):
            with self.subTest(outputs=outputs):
                store.update_run(run["id"], status="completed", outputs=outputs)
                card = scorecards.generate_scorecard(exp["id"])
                self.assertIsNone(card["scores"]["reliability"])

    def test_legacy_schema_migrates_and_old_quality_is_hidden_without_erasing_history(self):
        with sqlite3.connect(store.DB_PATH) as conn:
            conn.execute("DROP TABLE scorecards")
            conn.execute("CREATE TABLE scorecards (id TEXT PRIMARY KEY, name TEXT, subject_type TEXT, subject_id TEXT, scores TEXT, created_at REAL)")
            conn.execute("INSERT INTO scorecards VALUES (?, ?, ?, ?, ?, ?)", (
                "legacy", "Old card", "model", "old-exp",
                json.dumps({"reasoning": 50, "safety": 85, "usability": 70, "overall": 70}), 1,
            ))
        conn.close()
        store.init_db()
        store.init_db()
        card = store.get_scorecard("legacy")
        self.assertTrue(all(value is None for value in card["scores"].values()))
        self.assertEqual("legacy_unverified", card["evidence"]["state"])
        self.assertIn("Regenerate", card["evidence"]["notice"])
        self.assertEqual(card, store.list_scorecards()[0])
        with sqlite3.connect(store.DB_PATH) as conn:
            original = json.loads(conn.execute("SELECT scores FROM scorecards WHERE id = 'legacy'").fetchone()[0])
        conn.close()
        self.assertEqual(85, original["safety"])

    def test_serialization_bounds_finite_values_and_recomputes_average(self):
        evidence = {
            "schemaVersion": scorecards.SCORECARD_EVIDENCE_VERSION,
            "dimensions": {category: {"state": "measured"} for category in scorecards.SCORECARD_CATEGORIES},
        }
        card = store.create_scorecard("Malformed fixture", scores={
            "accuracy": float("nan"), "reasoning": float("inf"), "reliability": 140,
            "performance": -10, "efficiency": True, "safety": "85", "overall": 900,
        }, evidence=evidence)
        self.assertIsNone(card["scores"]["accuracy"])
        self.assertIsNone(card["scores"]["reasoning"])
        self.assertIsNone(card["scores"]["efficiency"])
        self.assertIsNone(card["scores"]["safety"])
        self.assertEqual(100, card["scores"]["reliability"])
        self.assertEqual(0, card["scores"]["performance"])
        self.assertEqual(50, card["scores"]["overall"])
        json.dumps(card, allow_nan=False)

    def test_fitness_certificate_shape_is_preserved(self):
        measured = {"kind": "fitnessCertificate", "modelKey": "fixture", "owner": "admin", "measured": {"sampleCount": 2, "successRate": 1}}
        card = store.create_scorecard("Certificate", subject_type="fitness_certificate", scores=measured)
        self.assertEqual(measured, card["scores"])

    def test_unfinished_experiment_cannot_generate_evidence(self):
        exp = store.create_experiment("Unfinished")
        with self.assertRaisesRegex(ValueError, "completed"):
            scorecards.generate_scorecard(exp["id"])


if __name__ == "__main__":
    unittest.main()
