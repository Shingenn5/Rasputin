import os
import tempfile
import unittest


# Keep this contract suite away from the developer database.  The runtime
# store resolves its data directory when backend modules are imported.
os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-assistant-contracts-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api.core import current_user
from backend.assistant import contracts
from backend.core import security


class AssistantContractTests(unittest.TestCase):
    def setUp(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "contract-test", "role": "admin"}
        self.client = TestClient(main.app, base_url="http://127.0.0.1", raise_server_exceptions=False)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_profile_contract_keeps_safety_policy_immutable(self):
        profile = contracts.merge_profile(
            contracts.default_profile("contract-test"),
            {
                "display_name": "Friday",
                "local_control_policy": {"broker_only": False},
                "persona": {"summary": "A concise local partner.", "traits": ["direct"]},
            },
            "contract-test",
        )
        self.assertEqual(profile["display_name"], "Friday")
        self.assertEqual(profile["persona"]["summary"], "A concise local partner.")
        self.assertTrue(profile["local_control_policy"]["broker_only"])
        self.assertFalse(profile["local_control_policy"]["model_containers_have_host_access"])

    def test_agent_graph_rejects_cycles(self):
        with self.assertRaisesRegex(ValueError, "acyclic"):
            contracts.normalize_agents(
                [
                    {"id": "one", "role": "planner", "dependsOn": ["two"]},
                    {"id": "two", "role": "executor", "dependsOn": ["one"]},
                ],
                "ship the change",
            )

    def test_plan_preview_is_explicitly_side_effect_free(self):
        response = self.client.post(
            "/api/assistant/plan-preview",
            json={
                "objective": "Open VS Code and run the tests",
                "agents": [
                    {"id": "planner", "role": "planner"},
                    {"id": "coder", "role": "coder", "dependsOn": ["planner"]},
                ],
                "requestedOperations": ["open_vscode", "run_test", "not_a_broker_operation"],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["execution"]["mode"], "preview_only")
        self.assertFalse(data["execution"]["started"])
        self.assertFalse(data["execution"]["hostActionsStarted"])
        self.assertFalse(data["delegation"]["execution"]["started"])
        self.assertTrue(all(not step["sideEffects"] for step in data["delegation"]["agents"]))
        operation_states = {item["operation"]: item for item in data["localControl"]["operations"]}
        self.assertEqual(operation_states["open_vscode"]["status"], "blocked")
        self.assertEqual(operation_states["run_test"]["status"], "blocked")
        self.assertEqual(operation_states["not_a_broker_operation"]["status"], "blocked")
        self.assertIn("control:open_vscode:security_flag_disabled:allow_shell_execution", data["blockers"])

    def test_profile_and_capability_routes_are_available(self):
        capabilities = self.client.get("/api/assistant/capabilities")
        self.assertEqual(capabilities.status_code, 200, capabilities.text)
        capability_data = capabilities.json()["data"]
        self.assertIn("speech_to_text", capability_data["voiceRoles"])
        self.assertTrue(capability_data["security"]["brokerOnly"])

        patched = self.client.patch("/api/assistant/profile", json={"displayName": "Rasputin Prime"})
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["data"]["displayName"], "Rasputin Prime")

    def test_sensitive_context_preview_requires_admin(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "member-test", "role": "member"}
        response = self.client.post(
            "/api/assistant/plan-preview",
            json={"objective": "Review private context", "includeSensitive": True},
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"]["code"], "permissionDenied")

    def test_persisted_plan_stays_side_effect_free_through_review(self):
        created = self.client.post(
            "/api/assistant/plans",
            json={"objective": "Prepare a local test run"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        record = created.json()["data"]
        self.assertTrue(record["id"].startswith("aplan_"))
        self.assertEqual(record["status"], "preview")
        self.assertEqual(record["handoff"]["status"], "review_required")
        self.assertFalse(record["handoff"]["executionStarted"])

        plan_id = record["id"]
        listed = self.client.get("/api/assistant/plans")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertTrue(any(item["id"] == plan_id for item in listed.json()["data"]["plans"]))

        fetched = self.client.get(f"/api/assistant/plans/{plan_id}")
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["data"]["id"], plan_id)

        approved = self.client.post(
            f"/api/assistant/plans/{plan_id}/approve",
            json={"note": "Reviewed locally"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        approved_data = approved.json()["data"]
        self.assertEqual(approved_data["status"], "approved")
        self.assertEqual(approved_data["handoff"]["status"], "awaiting_broker")
        self.assertFalse(approved_data["handoff"]["brokerRequestCreated"])
        self.assertFalse(approved_data["handoff"]["executionStarted"])

        repeated = self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={})
        self.assertEqual(repeated.status_code, 400, repeated.text)

    def test_blocked_plan_cannot_be_approved(self):
        created = self.client.post(
            "/api/assistant/plans",
            json={"objective": "Run tests", "requestedOperations": ["run_test"]},
        )
        self.assertEqual(created.status_code, 200, created.text)
        plan_id = created.json()["data"]["id"]
        blocked = self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={})
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(blocked.json()["error"]["code"], "assistantPlanBlocked")

    def test_named_model_pack_can_be_reused_by_preview(self):
        saved = self.client.post(
            "/api/assistant/model-packs",
            json={
                "packId": "voice-core",
                "version": "0.1",
                "entries": [
                    {"id": "input", "role": "speech_to_text", "capabilities": ["audio.transcribe"]},
                    {"id": "output", "role": "text_to_speech", "capabilities": ["audio.synthesize"]},
                ],
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        saved_data = saved.json()["data"]
        self.assertEqual(saved_data["packId"], "voice-core")
        self.assertFalse(saved_data["launchPolicy"]["started"])

        listed = self.client.get("/api/assistant/model-packs")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertTrue(any(item["packId"] == "voice-core" for item in listed.json()["data"]["packs"]))

        preview = self.client.post(
            "/api/assistant/plan-preview",
            json={"objective": "Start a voice conversation", "modelPackId": "voice-core"},
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        preview_data = preview.json()["data"]
        self.assertEqual(preview_data["modelPackSource"], "saved")
        self.assertEqual(preview_data["modelPack"]["packId"], "voice-core")
        self.assertFalse(preview_data["execution"]["modelsStarted"])

        deleted = self.client.delete("/api/assistant/model-packs/voice-core")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        missing = self.client.get("/api/assistant/model-packs/voice-core")
        self.assertEqual(missing.status_code, 400, missing.text)

    def test_broker_handoff_stops_at_existing_approval_boundary(self):
        original_security = security.load()
        security.save({**original_security, "allow_shell_execution": True})
        try:
            created = self.client.post(
                "/api/assistant/plans",
                json={"objective": "Run the approved local test", "requestedOperations": ["run_test"]},
            )
            self.assertEqual(created.status_code, 200, created.text)
            plan_id = created.json()["data"]["id"]
            approved_plan = self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={})
            self.assertEqual(approved_plan.status_code, 200, approved_plan.text)

            handoff_response = self.client.post(
                f"/api/assistant/plans/{plan_id}/handoffs",
                json={"operation": "run_test"},
            )
            self.assertEqual(handoff_response.status_code, 200, handoff_response.text)
            handoff = handoff_response.json()["data"]
            self.assertEqual(handoff["status"], "pending_approval")
            self.assertEqual(handoff["brokerStatus"], "awaiting_approval")
            self.assertEqual(handoff["approval"]["actionType"], "assistant_broker_operation")
            self.assertFalse(handoff["policy"]["executionStarted"])

            approved = self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={})
            self.assertEqual(approved.status_code, 200, approved.text)
            refreshed = self.client.get(f"/api/assistant/handoffs/{handoff['id']}")
            self.assertEqual(refreshed.status_code, 200, refreshed.text)
            refreshed_data = refreshed.json()["data"]
            self.assertEqual(refreshed_data["brokerStatus"], "approved_for_broker")
            self.assertFalse(refreshed_data["policy"]["executionStarted"])
            self.assertFalse(refreshed_data["policy"]["sideEffects"])
        finally:
            security.save(original_security)


if __name__ == "__main__":
    unittest.main()
