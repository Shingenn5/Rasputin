import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import release_evidence as evidence


NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
MODEL = {"artifactSha256": "a" * 64, "runtimeSha256": "b" * 64, "configSha256": "c" * 64}


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rasputin-evidence-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "evidence.json"
        (self.directory / "proof.txt").write_bytes(b"operator-reviewed proof fixture")
        self.subject = {
            "source": {"commit": "d" * 40, "dirty": True, "sha256": "e" * 64},
            "target": "native-host",
            "package": {"kind": "source", "sha256": "e" * 64},
            "models": {role: copy.deepcopy(MODEL) for role in evidence.ROLES},
        }

    def record(self, row="operatorUx", kind="browser-test", environment="source", **changes):
        record = {
            "id": f"{row}-{kind}", "row": row, "type": kind,
            "source": copy.deepcopy(self.subject["source"]),
            "target": self.subject["target"],
            "package": copy.deepcopy(self.subject["package"]),
            "environment": {"kind": environment, "platform": "windows", "machineId": "test-host", "owner": self.subject["target"], "hardwareId": "test-hardware"},
            "models": {role: copy.deepcopy(MODEL) for role in evidence.ROW_MODELS.get(row, set())},
            "timestamp": NOW.isoformat(), "outcome": "passed",
            "artifacts": [{"path": "proof.txt", "sha256": hashlib.sha256(b"operator-reviewed proof fixture").hexdigest()}],
        }
        record.update(changes)
        return record

    def complete(self, desktop=False):
        if desktop:
            self.subject["target"] = "desktop"
            self.subject["package"] = {"kind": "desktop-package", "sha256": "f" * 64}
        environment = "installed" if desktop else "source"
        records = [
            self.record("nativeDeployment", "installed-package" if desktop else "source-probe", environment),
            self.record("modelRuntime", "model-runtime", environment),
            self.record("coderMission", "live-coder", environment),
            self.record("voiceTurn", "live-voice", environment),
            self.record("lastingMemory", "browser-test", environment),
            self.record("safeOrchestration", "browser-test", environment),
            self.record("recovery", "recovery", "clean-machine" if desktop else "source"),
            self.record("operatorUx", "browser-test", environment),
        ]
        if desktop:
            records.append(self.record("nativeDeployment", "clean-machine", "clean-machine"))
        return records

    def evaluate(self, records, automated=True):
        self.path.write_text(json.dumps({"schemaVersion": 1, "records": records}), encoding="utf-8")
        return evidence.evaluate(self.path, self.subject, automated_passed=automated, now=NOW)

    def row(self, result, name):
        return next(row for row in result["rows"] if row["id"] == name)

    def test_missing_evidence_keeps_every_nonautomated_contract_row_open(self):
        result = evidence.evaluate(None, self.subject, automated_passed=True, now=NOW)
        self.assertFalse(result["passed"])
        self.assertEqual(set(evidence.ROWS), {row["id"] for row in result["rows"]})
        self.assertEqual(8, sum(row["status"] == "open" for row in result["rows"]))

    def test_matching_current_evidence_can_close_native_and_desktop(self):
        for desktop in (False, True):
            with self.subTest(desktop=desktop):
                result = self.evaluate(self.complete(desktop))
                self.assertTrue(result["passed"], result["rejectedRecords"])
                self.assertTrue(all(row["status"] == "passed" for row in result["rows"]))

    def test_automated_failure_cannot_be_overridden_by_imported_records(self):
        self.assertFalse(self.evaluate(self.complete(), automated=False)["passed"])

    def test_source_or_mocked_coder_evidence_cannot_close_live_mission(self):
        for kind in ("source-test", "mocked-workflow", "browser-test"):
            with self.subTest(kind=kind):
                records = self.complete()
                records[2]["type"] = kind
                result = self.evaluate(records)
                self.assertFalse(result["passed"])
                self.assertEqual("open", self.row(result, "coderMission")["status"])

    def test_source_environment_does_not_certify_installed_desktop(self):
        records = self.complete(desktop=True)
        for record in records:
            record["environment"]["kind"] = "source"
        result = self.evaluate(records)
        self.assertFalse(result["passed"])
        self.assertEqual("open", self.row(result, "nativeDeployment")["status"])

    def test_desktop_requires_installed_and_clean_machine_evidence(self):
        records = self.complete(desktop=True)
        self.assertFalse(self.evaluate(records[:-1])["passed"])

    def test_latest_failed_result_overrides_older_pass_even_with_timestamp_tie(self):
        records = self.complete()
        failure = self.record(id="later-failure", outcome="failed")
        result = self.evaluate(records + [failure])
        self.assertFalse(result["passed"])
        self.assertIn("latest evidence failed", self.row(result, "operatorUx")["missing"][0])

    def test_stale_future_and_timezone_less_timestamps_are_rejected(self):
        timestamps = [NOW - timedelta(days=8), NOW + timedelta(minutes=6), NOW.replace(tzinfo=None)]
        for timestamp in timestamps:
            with self.subTest(timestamp=timestamp):
                result = self.evaluate([self.record(timestamp=timestamp.isoformat())])
                self.assertEqual(1, len(result["rejectedRecords"]))

    def test_source_commit_dirty_digest_target_and_package_must_match(self):
        for field, key, value in (
            ("source", "commit", "1" * 40), ("source", "dirty", False),
            ("source", "sha256", "1" * 64), ("package", "sha256", "1" * 64),
        ):
            with self.subTest(field=field, key=key):
                record = self.record()
                record[field][key] = value
                self.assertTrue(self.evaluate([record])["rejectedRecords"])
        self.assertTrue(self.evaluate([self.record(target="desktop")])["rejectedRecords"])

    def test_model_role_requires_matching_selected_artifact_runtime_and_config(self):
        for key in MODEL:
            with self.subTest(key=key):
                record = self.record("coderMission", "live-coder")
                record["models"]["coder"][key] = "1" * 64
                self.assertTrue(self.evaluate([record])["rejectedRecords"])
        record = self.record("coderMission", "live-coder", models={})
        self.assertTrue(self.evaluate([record])["rejectedRecords"])
        self.subject["models"].pop("coder")
        self.assertTrue(self.evaluate([self.record("coderMission", "live-coder")])["rejectedRecords"])

    def test_voice_requires_all_three_selected_models_and_hardware(self):
        record = self.record("voiceTurn", "live-voice")
        del record["models"]["tts"]
        self.assertTrue(self.evaluate([record])["rejectedRecords"])
        record = self.record("voiceTurn", "live-voice")
        record["environment"]["hardwareId"] = None
        self.assertTrue(self.evaluate([record])["rejectedRecords"])

    def test_artifact_must_exist_and_match_hash(self):
        for artifact in ({"path": "missing.txt", "sha256": "a" * 64}, {"path": "proof.txt", "sha256": "a" * 64}):
            self.assertTrue(self.evaluate([self.record(artifacts=[artifact])])["rejectedRecords"])
        self.assertTrue(self.evaluate([self.record(artifacts=[])])["rejectedRecords"])

    def test_artifact_cannot_escape_directory_or_use_windows_streams(self):
        for path in ("../proof.txt", "..\\proof.txt", "/proof.txt", "C:\\proof.txt", "proof.txt:secret", "https://example.test/proof"):
            with self.subTest(path=path):
                record = self.record()
                record["artifacts"][0]["path"] = path
                self.assertTrue(self.evaluate([record])["rejectedRecords"])

    def test_artifact_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-proof-outside-") as outside:
            target = Path(outside) / "proof.txt"
            target.write_bytes(b"operator-reviewed proof fixture")
            try:
                (self.directory / "outside.txt").symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is unavailable on this Windows account")
            record = self.record()
            record["artifacts"][0]["path"] = "outside.txt"
            self.assertTrue(self.evaluate([record])["rejectedRecords"])

    def test_schema_is_strict_bounded_and_rejects_duplicate_ids(self):
        for patch_record in ({"extra": "field"}, {"row": "imaginary"}, {"outcome": "skipped"}, {"type": "operator-says-ready"}):
            self.assertTrue(self.evaluate([self.record(**patch_record)])["rejectedRecords"])
        self.assertTrue(self.evaluate([self.record(), self.record()])["rejectedRecords"])
        self.assertTrue(self.evaluate([self.record(id=str(index)) for index in range(129)])["rejectedRecords"])
        for document in ('{"schemaVersion":1,"schemaVersion":1,"records":[]}', '{"schemaVersion":true,"records":[]}', '{"schemaVersion":2,"records":[]}', '[]', 'bad json'):
            self.path.write_text(document, encoding="utf-8")
            self.assertTrue(evidence.evaluate(self.path, self.subject, automated_passed=True, now=NOW)["rejectedRecords"])
        self.path.write_bytes(b" " * (evidence.MAX_DOCUMENT_BYTES + 1))
        self.assertTrue(evidence.evaluate(self.path, self.subject, automated_passed=True, now=NOW)["rejectedRecords"])

    def test_attachment_byte_limit_is_enforced(self):
        with patch.object(evidence, "MAX_ARTIFACT_BYTES", 2):
            self.assertTrue(self.evaluate([self.record()])["rejectedRecords"])

    def test_bundle_byte_limit_counts_repeated_attachment_reads(self):
        records = [self.record(id="one"), self.record(id="two")]
        with patch.object(evidence, "MAX_BUNDLE_ARTIFACT_BYTES", 40):
            result = self.evaluate(records)
        self.assertEqual(1, result["acceptedRecordCount"])
        self.assertEqual(1, len(result["rejectedRecords"]))

    def test_malformed_nested_types_fail_closed_without_crashing(self):
        for changes in ({"row": []}, {"type": {}}, {"environment": []}, {"models": []}, {"source": None}, {"timestamp": True}, {"artifacts": [None]}):
            with self.subTest(changes=changes):
                record = self.record()
                record.update(changes)
                self.assertTrue(self.evaluate([record])["rejectedRecords"])

    def test_model_cli_parser_rejects_duplicates_missing_hashes_and_unknown_roles(self):
        value = "coder=" + ":".join(MODEL.values())
        self.assertEqual({"coder": MODEL}, evidence.parse_models([value]))
        for values in ([value, value], ["unknown=" + ":".join(MODEL.values())], ["coder=a"], ["coder=" + ":".join(MODEL.values()).upper()]):
            with self.subTest(values=values):
                with self.assertRaises(evidence.EvidenceError):
                    evidence.parse_models(values)

    def test_package_identity_hashes_actual_selected_bytes(self):
        package = self.directory / "Rasputin.exe"
        package.write_bytes(b"package one")
        first = evidence.package_identity("desktop", self.subject["source"], package)
        package.write_bytes(b"package two")
        self.assertNotEqual(first, evidence.package_identity("desktop", self.subject["source"], package))
        with self.assertRaises(evidence.EvidenceError):
            evidence.package_identity("desktop", self.subject["source"], None)


class SourceIdentityTests(unittest.TestCase):
    def test_dirty_file_changes_invalidate_evidence_even_when_commit_and_dirty_do_not_change(self):
        with tempfile.TemporaryDirectory(prefix="rasputin-source-identity-") as directory:
            root = Path(directory)
            def git(*args):
                subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args], cwd=root, check=True, capture_output=True)
            git("init")
            source = root / "source.py"
            source.write_text("version = 1", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "fixture")
            clean = evidence.source_identity(root)
            self.assertFalse(clean["dirty"])
            source.write_text("version = 2", encoding="utf-8")
            first = evidence.source_identity(root)
            source.write_text("version = 3", encoding="utf-8")
            second = evidence.source_identity(root)
            self.assertTrue(first["dirty"])
            self.assertTrue(second["dirty"])
            self.assertEqual(first["commit"], second["commit"])
            self.assertNotEqual(first["sha256"], second["sha256"])
            (root / "untracked.py").write_text("new = True", encoding="utf-8")
            self.assertNotEqual(second["sha256"], evidence.source_identity(root)["sha256"])


if __name__ == "__main__":
    unittest.main()
