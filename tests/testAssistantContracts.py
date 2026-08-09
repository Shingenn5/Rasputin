import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


# Keep this contract suite away from the developer database.  The runtime
# store resolves its data directory when backend modules are imported.
os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-assistant-contracts-"))

from fastapi.testclient import TestClient

from backend import main
from backend.api.core import current_user, hub
from backend.assistant import contracts
from backend.assistant import runtime
from backend.core import runtime_store
from backend.core import security
from backend.core import workspace
from backend.engine import agent
from backend.engine import context as context_governor


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
        self.assertTrue(capability_data["contextCapsules"]["approvalRequired"])
        workflows = {item["id"]: item for item in capability_data["workflows"]}
        self.assertEqual(workflows["assistant"]["mode"], "chat")
        self.assertEqual(workflows["assistant"]["role"], "main")
        self.assertEqual(workflows["coding"]["mode"], "code")
        self.assertEqual(workflows["coding"]["role"], "coder")
        self.assertTrue(capability_data["security"]["brokerOnly"])
        self.assertIn("docker_status", capability_data["broker"]["dispatchSupportedOperations"])
        self.assertIn("open_vscode", capability_data["broker"]["dispatchSupportedOperations"])
        self.assertIn("start_coding_task", capability_data["broker"]["dispatchSupportedOperations"])
        metadata = next(item for item in capability_data["broker"]["dispatchOperationMetadata"] if item["operation"] == "open_vscode")
        self.assertTrue(metadata["hostMutation"])
        control_operations = capability_data["controlOperations"]
        open_definition = next(
            item for item in (control_operations.values() if isinstance(control_operations, dict) else control_operations)
            if item["operation"] == "open_vscode"
        )
        self.assertEqual(open_definition["label"], "Open VS Code")

        patched = self.client.patch("/api/assistant/profile", json={"displayName": "Rasputin Prime"})
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["data"]["displayName"], "Rasputin Prime")

    def test_command_router_is_allowlisted_preview_only_and_approval_explicit(self):
        original_security = security.load()
        security.save({**original_security, "allow_docker_control": True, "allow_shell_execution": False})
        try:
            recognized = self.client.post(
                "/api/assistant/command-preview",
                json={"command": "Please check Docker status"},
            )
            self.assertEqual(recognized.status_code, 200, recognized.text)
            data = recognized.json()["data"]
            self.assertEqual(data["contractVersion"], "0.1")
            self.assertEqual(data["route"]["status"], "recognized")
            self.assertEqual(data["route"]["operation"], "docker_status")
            self.assertEqual(data["route"]["matchedAlias"], "check docker status")
            self.assertTrue(data["route"]["supportedByBroker"])
            self.assertTrue(data["approval"]["required"])
            self.assertEqual(data["approval"]["state"], "review_required")
            self.assertFalse(data["approval"]["created"])
            self.assertEqual(data["execution"]["mode"], "preview_only")
            self.assertFalse(data["execution"]["started"])
            self.assertFalse(data["execution"]["sideEffects"])

            blocked = self.client.post(
                "/api/assistant/command-preview",
                json={"command": "open VS Code", "workspacePath": "."},
            )
            self.assertEqual(blocked.status_code, 200, blocked.text)
            blocked_data = blocked.json()["data"]
            self.assertEqual(blocked_data["route"]["status"], "blocked")
            self.assertIn("security_flag_disabled:allow_shell_execution", blocked_data["route"]["blockedReasons"])
            self.assertEqual(blocked_data["approval"]["state"], "blocked")

            unsupported = self.client.post(
                "/api/assistant/command-preview",
                json={"command": "run the tests"},
            )
            self.assertEqual(unsupported.status_code, 200, unsupported.text)
            unsupported_data = unsupported.json()["data"]
            self.assertEqual(unsupported_data["route"]["status"], "blocked")
            self.assertEqual(unsupported_data["route"]["operation"], "run_test")
            self.assertIn("operation_not_supported_by_broker", unsupported_data["route"]["blockedReasons"])

            unknown = self.client.post(
                "/api/assistant/command-preview",
                json={"command": "send an email to my friend"},
            )
            self.assertEqual(unknown.status_code, 200, unknown.text)
            unknown_data = unknown.json()["data"]
            self.assertEqual(unknown_data["route"]["status"], "needs_clarification")
            self.assertIsNone(unknown_data["operationPreview"])
            self.assertIn("docker_status", unknown_data["route"]["suggestedOperations"])

            unsafe = self.client.post(
                "/api/assistant/command-preview",
                json={"command": "docker status; rm -rf /"},
            )
            self.assertEqual(unsafe.status_code, 200, unsafe.text)
            unsafe_data = unsafe.json()["data"]
            self.assertEqual(unsafe_data["route"]["status"], "rejected")
            self.assertFalse(unsafe_data["execution"]["started"])
        finally:
            security.save(original_security)

    def test_approved_plan_can_start_one_governed_code_task_with_capsule_receipt(self):
        capsule = runtime.create_context_capsule(
            owner_id="contract-test",
            objective="Carry the reviewed coding handoff into a Code task",
            workspace_ref=".",
            context_query="approved coding evidence",
        )
        self.assertEqual(self.client.post(f"/api/assistant/context-capsules/{capsule['id']}/approve", json={}).status_code, 200)
        created = self.client.post(
            "/api/assistant/plans",
            json={
                "objective": "Run the governed coding task",
                "contextCapsuleId": capsule["id"],
                "modelPack": {
                    "packId": "contract-coder",
                    "entries": [{"id": "coder", "role": "coder", "modelKey": "dry-run", "required": True}],
                },
                "requestedOperations": ["start_coding_task"],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        plan = created.json()["data"]
        self.assertEqual(plan["plan"]["blockers"], [])
        self.assertTrue(plan["plan"]["execution"]["coding"]["ready"])
        self.assertEqual(plan["plan"]["execution"]["coding"]["modelKey"], "dry-run")
        plan_id = plan["id"]
        self.assertEqual(self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={}).status_code, 200)
        handoff = self.client.post(
            f"/api/assistant/plans/{plan_id}/handoffs",
            json={"operation": "start_coding_task"},
        ).json()["data"]
        self.assertEqual(handoff["status"], "pending_approval")
        self.assertEqual(self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare").status_code, 200)

        # Keep the contract test deterministic: prove the bridge creates and
        # records the task without running a model worker in this request.
        with patch.object(hub, "_schedule_queued_task", lambda _task: None):
            dispatched = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
        self.assertEqual(dispatched.status_code, 200, dispatched.text)
        data = dispatched.json()["data"]
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["request"]["operation"], "start_coding_task")
        self.assertTrue(data["request"]["executionStarted"])
        self.assertTrue(data["request"]["hostMutation"])
        self.assertTrue(data["request"]["sideEffects"])
        result = data["request"]["result"]
        self.assertEqual(result["mode"], "code")
        self.assertEqual(result["model"], "dry-run")
        self.assertEqual(result["contextCapsuleId"], capsule["id"])
        task = hub.tasks[result["taskId"]]
        self.assertEqual(task.context_capsule_id, capsule["id"])
        self.assertIn("assistant_handoff_started", [item["kind"] for item in task.trace])

        repeated = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["data"]["request"]["result"]["taskId"], result["taskId"])

    def test_voice_preview_reports_missing_audio_models_without_starting_io(self):
        response = self.client.post(
            "/api/assistant/voice-preview",
            json={
                "modelPack": {
                    "packId": "voice-core",
                    "entries": [
                        {"id": "conversation", "role": "main", "modelKey": "main-vllm"},
                    ],
                },
                "conversationId": "session-voice-1",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["loop"], ["transcribe", "reason", "synthesize"])
        self.assertFalse(data["ready"])
        self.assertIn("voice:transcribe:model_not_registered", data["blockers"])
        self.assertIn("voice:synthesize:model_not_registered", data["blockers"])
        self.assertEqual(data["conversationId"], "session-voice-1")
        self.assertFalse(data["execution"]["audioIoStarted"])
        self.assertFalse(data["execution"]["transcriptionStarted"])
        self.assertFalse(data["execution"]["synthesisStarted"])
        self.assertEqual(data["policy"]["microphoneAccess"], "not_started")
        self.assertEqual(data["policy"]["speakerAccess"], "not_started")

    def test_voice_preview_resolves_role_compatible_models(self):
        models = [
            {"key": "stt-local", "role": "speech_to_text", "provider": "whisper", "runtime_status": "reachable", "enabled": True, "managed": False},
            {"key": "main-local", "role": "main", "provider": "llama.cpp", "runtime_status": "reachable", "enabled": True, "managed": False},
            {"key": "tts-local", "role": "text_to_speech", "provider": "piper", "runtime_status": "reachable", "enabled": True, "managed": False},
        ]
        with patch("backend.assistant.runtime.model_registry.all_models", return_value=models):
            response = self.client.post(
                "/api/assistant/voice-preview",
                json={
                    "modelPack": {
                        "packId": "voice-core",
                        "entries": [
                            {"id": "input", "role": "speech_to_text", "modelKey": "stt-local"},
                            {"id": "conversation", "role": "main", "modelKey": "main-local"},
                            {"id": "output", "role": "text_to_speech", "modelKey": "tts-local"},
                        ],
                    },
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertTrue(data["ready"])
        self.assertEqual(data["blockers"], [])
        self.assertTrue(all(stage["status"] == "ready" for stage in data["stages"]))
        self.assertFalse(data["execution"]["started"])
        self.assertFalse(data["execution"]["modelsStarted"])
        self.assertFalse(data["execution"]["audioIoStarted"])

    def test_context_preview_exposes_owner_scoped_cross_workspace_contract(self):
        response = self.client.post(
            "/api/assistant/context-preview",
            json={
                "objective": "Recall the current project direction",
                "contextQuery": "project direction",
                "workspacePath": ".",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["workspaceRef"], ".")
        self.assertTrue(data["policy"]["ownerScoped"])
        self.assertTrue(data["policy"]["crossWorkspace"])
        self.assertTrue(data["policy"]["noUnscopedDatabaseReads"])
        self.assertFalse(data["policy"]["sensitiveIncluded"])

        main.app.dependency_overrides[current_user] = lambda: {"username": "member-test", "role": "member"}
        sensitive = self.client.post(
            "/api/assistant/context-preview",
            json={"objective": "Review private context", "includeSensitive": True},
        )
        self.assertEqual(sensitive.status_code, 403, sensitive.text)
        self.assertEqual(sensitive.json()["error"]["code"], "permissionDenied")

    def test_context_preview_keeps_selected_workflow_session_explicit(self):
        coding = hub.create_session(
            "Coding history",
            ".",
            "coder-local",
            "code",
            "general",
            "",
            "contract-test",
        )
        hub._add_message(
            coding["session"]["id"],
            None,
            "user",
            "Use the coding workflow to repair the failing test.",
        )
        hub._add_message(
            coding["session"]["id"],
            None,
            "assistant",
            "Coding handoff: run the focused test before changing unrelated files.",
        )
        response = self.client.post(
            "/api/assistant/context-preview",
            json={
                "objective": "Continue the approved coding work",
                "sessionId": coding["session"]["id"],
                "workspacePath": ".",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["selectedSession"]["id"], coding["session"]["id"])
        self.assertEqual(data["selectedSession"]["mode"], "code")
        self.assertEqual(data["selectedSession"]["messageCount"], 2)
        self.assertFalse(data["selectedSession"]["messagesTruncated"])
        self.assertEqual(
            [message["content"] for message in data["selectedSession"]["messages"]],
            [
                "Use the coding workflow to repair the failing test.",
                "Coding handoff: run the focused test before changing unrelated files.",
            ],
        )
        self.assertTrue(data["policy"]["ownerScoped"])

        planned = self.client.post(
            "/api/assistant/plans",
            json={
                "objective": "Plan the next coding handoff",
                "sessionId": coding["session"]["id"],
                "contextQuery": "coding handoff",
            },
        )
        self.assertEqual(planned.status_code, 200, planned.text)
        self.assertEqual(
            planned.json()["data"]["plan"]["context"]["selectedSession"]["id"],
            coding["session"]["id"],
        )
        self.assertEqual(
            planned.json()["data"]["plan"]["context"]["selectedSession"]["messages"][1]["role"],
            "assistant",
        )

        other = hub.create_session(
            "Other owner history",
            ".",
            "main-local",
            "chat",
            "general",
            "",
            "other-owner",
        )
        denied = self.client.post(
            "/api/assistant/context-preview",
            json={"objective": "Do not cross owner boundaries", "sessionId": other["session"]["id"]},
        )
        self.assertEqual(denied.status_code, 400, denied.text)
        self.assertEqual(denied.json()["error"]["code"], "badRequest")

    def test_sensitive_context_preview_requires_admin(self):
        main.app.dependency_overrides[current_user] = lambda: {"username": "member-test", "role": "member"}
        response = self.client.post(
            "/api/assistant/plan-preview",
            json={"objective": "Review private context", "includeSensitive": True},
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"]["code"], "permissionDenied")

    def test_context_capsule_requires_review_and_keeps_provenance(self):
        coding = hub.create_session(
            "Capsule coding history",
            ".",
            "coder-local",
            "code",
            "general",
            "",
            "contract-test",
        )
        hub._add_message(coding["session"]["id"], None, "user", "Keep this coding handoff explicit.")
        created = self.client.post(
            "/api/assistant/context-capsules",
            json={
                "objective": "Prepare the next coding handoff",
                "contextQuery": "coding handoff",
                "sessionId": coding["session"]["id"],
                "workspacePath": ".",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        capsule = created.json()["data"]
        self.assertEqual(capsule["status"], "preview")
        self.assertEqual(capsule["provenance"]["sourceSessionId"], coding["session"]["id"])
        self.assertEqual(capsule["context"]["selectedSession"]["messages"][0]["content"], "Keep this coding handoff explicit.")

        blocked = self.client.post(
            "/api/assistant/plans",
            json={"objective": "Use the reviewed coding context", "contextCapsuleId": capsule["id"]},
        )
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(blocked.json()["error"]["code"], "assistantContextCapsuleNotApproved")

        approved = self.client.post(f"/api/assistant/context-capsules/{capsule['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["data"]["status"], "approved")

        planned = self.client.post(
            "/api/assistant/plans",
            json={"objective": "Use the reviewed coding context", "contextCapsuleId": capsule["id"]},
        )
        self.assertEqual(planned.status_code, 200, planned.text)
        plan = planned.json()["data"]["plan"]
        self.assertEqual(plan["contextSource"], "approved_capsule")
        self.assertEqual(plan["context"]["capsule"]["id"], capsule["id"])
        self.assertEqual(plan["context"]["capsule"]["status"], "approved")

        other = runtime.create_context_capsule(
            owner_id="other-owner",
            objective="Private capsule",
            workspace_ref=".",
            context_query="private",
        )
        denied = self.client.get(f"/api/assistant/context-capsules/{other['id']}")
        self.assertEqual(denied.status_code, 400, denied.text)
        self.assertEqual(denied.json()["error"]["code"], "badRequest")

    def test_context_capsule_expiry_is_visible_before_review(self):
        capsule = runtime_store.create_assistant_context_capsule(
            owner_id="contract-test",
            objective="Short-lived context",
            workspace_ref=".",
            context={"query": "short-lived"},
            expires_in_seconds=300,
        )
        with patch("backend.core.runtime_store.now", return_value=capsule["expires_at"] + 1):
            fetched = runtime_store.get_assistant_context_capsule("contract-test", capsule["id"])
        self.assertEqual(fetched["status"], "expired")

    def test_approved_context_capsule_can_start_task_with_bounded_receipt(self):
        source_session = hub.create_session(
            "Receipt source", ".", "dry-run", "chat", "general", "", "contract-test",
        )
        hub._add_message(
            source_session["session"]["id"],
            None,
            "user",
            "Approved source detail must reach the governed prompt.",
        )
        capsule = runtime.create_context_capsule(
            owner_id="contract-test",
            objective="Carry the reviewed coding handoff into execution",
            workspace_ref=".",
            session_id=source_session["session"]["id"],
            context_query="coding handoff",
        )
        approved = self.client.post(f"/api/assistant/context-capsules/{capsule['id']}/approve", json={})
        self.assertEqual(approved.status_code, 200, approved.text)

        with patch.object(hub, "_schedule_queued_task", lambda _task: None):
            created = self.client.post(
                "/api/tasks",
                json={
                    "objective": "Use the approved coding handoff",
                    "model": "dry-run",
                    "mode": "chat",
                    "workspacePath": ".",
                    "contextCapsuleId": capsule["id"],
                },
            )
        self.assertEqual(created.status_code, 200, created.text)
        task_data = created.json()["data"]
        self.assertEqual(task_data["contextCapsuleId"], capsule["id"])
        self.assertIsNone(task_data.get("contextCapsule"))

        task = hub.tasks[task_data["id"]]
        captured = []

        async def scripted_chat(model_key, messages, tools=None, on_delta=None, reasoning="auto"):
            captured.append(messages[0]["content"])
            return "governed response", []

        hub._load_context_capsule(task)
        sections = [context_governor.section("task", "Task", task.objective, required=True, priority=0)]
        rich_model = {"key": "dry-run", "compatibility": {"status": "compatible", "promptProfile": "standard"}}
        with patch("backend.engine.agent._chat", scripted_chat), patch("backend.engine.agent.model_registry.get_model", return_value=rich_model):
            result = asyncio.run(hub.governed_chat(task, "chat", "main", sections))
        self.assertEqual(result, "governed response")
        self.assertEqual(task.context_capsule_receipt["id"], capsule["id"])
        self.assertIn("Approved shared context", captured[0])
        self.assertIn("Approved source detail", captured[0])
        self.assertIn("context_capsule_injected", [item["kind"] for item in task.trace])
        self.assertIn("context_capsule_attached", [item["kind"] for item in task.trace])
        self.assertNotIn("context_json", task_data)

        detail = self.client.get(f"/api/tasks/{task_data['id']}")
        self.assertEqual(detail.status_code, 200, detail.text)
        trace_kinds = [item["kind"] for item in detail.json()["data"]["trace"]]
        self.assertIn("context_capsule_attached", trace_kinds)
        self.assertIn("context_capsule_injected", trace_kinds)

    def test_task_rejects_unapproved_context_capsule_before_queueing(self):
        capsule = runtime.create_context_capsule(
            owner_id="contract-test",
            objective="Needs explicit review",
            workspace_ref=".",
            context_query="review me",
        )
        with patch.object(hub, "_schedule_queued_task", lambda _task: self.fail("task should not queue")):
            blocked = self.client.post(
                "/api/tasks",
                json={
                    "objective": "Do not run before review",
                    "model": "dry-run",
                    "mode": "chat",
                    "workspacePath": ".",
                    "contextCapsuleId": capsule["id"],
                },
            )
        self.assertEqual(blocked.status_code, 409, blocked.text)
        self.assertEqual(blocked.json()["error"]["code"], "assistantContextCapsuleNotApproved")

    def test_queued_task_rechecks_capsule_expiry_at_runtime(self):
        capsule = runtime_store.create_assistant_context_capsule(
            owner_id="contract-test",
            objective="Expire before the queued worker starts",
            workspace_ref=".",
            context={"query": "queued expiry"},
            expires_in_seconds=300,
        )
        runtime_store.transition_assistant_context_capsule(
            "contract-test", capsule["id"], "approved", actor="contract-test",
        )
        task = agent.AgentTask(
            "Run only while the capsule is valid",
            "dry-run",
            "general",
            mode="chat",
            workspace_path=".",
            context_capsule_id=capsule["id"],
        )
        task.owner_id = "contract-test"
        with patch("backend.core.runtime_store.now", return_value=capsule["expires_at"] + 1):
            with self.assertRaisesRegex(RuntimeError, "expired"):
                agent.AgentHub()._load_context_capsule(task)
        self.assertEqual(task.trace[-1]["kind"], "context_capsule_blocked")
        self.assertEqual(task.trace[-1]["detail"]["reason"], "expired")

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

            pending_prepare = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(pending_prepare.status_code, 409, pending_prepare.text)
            self.assertEqual(pending_prepare.json()["error"]["code"], "assistantApprovalRequired")

            approved = self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={})
            self.assertEqual(approved.status_code, 200, approved.text)
            refreshed = self.client.get(f"/api/assistant/handoffs/{handoff['id']}")
            self.assertEqual(refreshed.status_code, 200, refreshed.text)
            refreshed_data = refreshed.json()["data"]
            self.assertEqual(refreshed_data["brokerStatus"], "approved_for_broker")
            self.assertFalse(refreshed_data["policy"]["executionStarted"])
            self.assertFalse(refreshed_data["policy"]["sideEffects"])

            prepared = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(prepared.status_code, 200, prepared.text)
            prepared_data = prepared.json()["data"]
            self.assertEqual(prepared_data["status"], "ready_for_broker")
            self.assertEqual(prepared_data["brokerStatus"], "ready_for_broker")
            self.assertEqual(prepared_data["request"]["contractVersion"], "0.1")
            self.assertFalse(prepared_data["request"]["executionStarted"])
            self.assertFalse(prepared_data["request"]["sideEffects"])
            self.assertFalse(prepared_data["policy"]["executionStarted"])

            repeated_prepare = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(repeated_prepare.status_code, 200, repeated_prepare.text)
            self.assertEqual(repeated_prepare.json()["data"]["status"], "ready_for_broker")
        finally:
            security.save(original_security)

    def test_broker_preparation_rechecks_current_security(self):
        original_security = security.load()
        security.save({**original_security, "allow_shell_execution": True})
        try:
            created = self.client.post(
                "/api/assistant/plans",
                json={"objective": "Run the local test", "requestedOperations": ["run_test"]},
            )
            self.assertEqual(created.status_code, 200, created.text)
            plan_id = created.json()["data"]["id"]
            self.assertEqual(self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={}).status_code, 200)
            handoff = self.client.post(
                f"/api/assistant/plans/{plan_id}/handoffs",
                json={"operation": "run_test"},
            ).json()["data"]
            self.assertEqual(self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={}).status_code, 200)

            security.save({**original_security, "allow_shell_execution": False})
            blocked = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(blocked.status_code, 409, blocked.text)
            self.assertEqual(blocked.json()["error"]["code"], "assistantOperationBlocked")
            self.assertFalse(self.client.get(f"/api/assistant/handoffs/{handoff['id']}").json()["data"]["policy"]["executionStarted"])
        finally:
            security.save(original_security)

    def test_read_only_broker_dispatch_requires_approval_and_is_idempotent(self):
        original_security = security.load()
        security.save({**original_security, "allow_docker_control": True})
        try:
            created = self.client.post(
                "/api/assistant/plans",
                json={"objective": "Inspect local model containers", "requestedOperations": ["docker_status"]},
            )
            self.assertEqual(created.status_code, 200, created.text)
            plan_id = created.json()["data"]["id"]
            self.assertEqual(created.json()["data"]["plan"]["blockers"], [])
            self.assertEqual(self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={}).status_code, 200)
            handoff = self.client.post(
                f"/api/assistant/plans/{plan_id}/handoffs",
                json={"operation": "docker_status"},
            ).json()["data"]

            not_ready = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
            self.assertEqual(not_ready.status_code, 409, not_ready.text)
            self.assertEqual(not_ready.json()["error"]["code"], "assistantHandoffNotReady")

            approved = self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={})
            self.assertEqual(approved.status_code, 200, approved.text)
            prepared = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(prepared.status_code, 200, prepared.text)

            observed = {"enabled": True, "containers": [{"name": "voice-model", "state": "running"}], "count": 1}
            with patch("backend.assistant.broker.warsat.containers", return_value=observed) as adapter:
                dispatched = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
                self.assertEqual(dispatched.status_code, 200, dispatched.text)
                dispatched_data = dispatched.json()["data"]
                self.assertEqual(dispatched_data["status"], "completed")
                self.assertEqual(dispatched_data["brokerStatus"], "completed")
                self.assertEqual(dispatched_data["request"]["dispatchStatus"], "completed")
                self.assertEqual(dispatched_data["request"]["dispatchContractVersion"], "0.1")
                self.assertEqual(dispatched_data["request"]["result"]["count"], 1)
                self.assertFalse(dispatched_data["request"]["sideEffects"])
                self.assertFalse(dispatched_data["request"]["hostMutation"])
                self.assertFalse(dispatched_data["policy"]["executionStarted"])
                self.assertEqual(adapter.call_count, 1)

                repeated = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
                self.assertEqual(repeated.status_code, 200, repeated.text)
                self.assertEqual(repeated.json()["data"]["status"], "completed")
                self.assertEqual(adapter.call_count, 1)

            approval_state = self.client.get("/api/approvals")
            self.assertEqual(approval_state.status_code, 200, approval_state.text)
            approval_record = next(item for item in approval_state.json()["data"]["approvals"] if item["id"] == handoff["approvalId"])
            self.assertEqual(approval_record["status"], "executed")
        finally:
            security.save(original_security)

    def test_open_vscode_dispatch_is_scoped_to_approved_workspace_and_fixed_argv(self):
        original_security = security.load()
        original_host_shell = workspace.is_host_shell_allowed(".")
        security.save({**original_security, "allow_shell_execution": True})
        try:
            with patch("backend.core.sandbox_exec.grant_workspace_acl"), patch("backend.core.sandbox_exec.revoke_workspace_acl"):
                workspace.set_host_shell("project-root", True)
            created = self.client.post(
                "/api/assistant/plans",
                json={"objective": "Open the approved project in VS Code", "requestedOperations": ["open_vscode"]},
            )
            self.assertEqual(created.status_code, 200, created.text)
            plan = created.json()["data"]
            self.assertEqual(plan["plan"]["blockers"], [])
            operation = plan["plan"]["localControl"]["operations"][0]
            self.assertEqual(operation["status"], "planned")
            self.assertTrue(operation["dispatch"]["hostMutation"])
            self.assertEqual(self.client.post(f"/api/assistant/plans/{plan['id']}/approve", json={}).status_code, 200)
            handoff = self.client.post(
                f"/api/assistant/plans/{plan['id']}/handoffs",
                json={"operation": "open_vscode"},
            ).json()["data"]
            self.assertEqual(self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={}).status_code, 200)
            prepared = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare")
            self.assertEqual(prepared.status_code, 200, prepared.text)
            self.assertEqual(prepared.json()["data"]["actionState"], "prepared")
            self.assertTrue(prepared.json()["data"]["request"]["plannedHostMutation"])

            with patch("backend.assistant.broker.shutil.which", return_value="C:\\fake\\code.cmd"), patch(
                "backend.assistant.broker.subprocess.Popen", return_value=SimpleNamespace(pid=31415)
            ) as launcher:
                dispatched = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
                self.assertEqual(dispatched.status_code, 200, dispatched.text)
                data = dispatched.json()["data"]
                self.assertEqual(data["status"], "completed")
                self.assertEqual(data["actionState"], "completed")
                self.assertTrue(data["request"]["result"]["launched"])
                self.assertEqual(data["request"]["result"]["pid"], 31415)
                self.assertTrue(data["request"]["sideEffects"])
                self.assertTrue(data["request"]["hostMutation"])
                self.assertTrue(data["request"]["executionStarted"])
                self.assertTrue(data["policy"]["sideEffects"])
                self.assertTrue(data["policy"]["hostMutation"])
                args, kwargs = launcher.call_args
                self.assertEqual(args[0][1], "--reuse-window")
                self.assertEqual(args[0][2], data["request"]["result"]["workspace"])
                self.assertIs(kwargs["shell"], False)
                self.assertNotIn("command", data["request"])

                repeated = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
                self.assertEqual(repeated.status_code, 200, repeated.text)
                self.assertEqual(launcher.call_count, 1)
        finally:
            with patch("backend.core.sandbox_exec.grant_workspace_acl"), patch("backend.core.sandbox_exec.revoke_workspace_acl"):
                workspace.set_host_shell("project-root", original_host_shell)
            security.save(original_security)

    def test_open_vscode_dispatch_fails_closed_when_cli_is_missing(self):
        original_security = security.load()
        original_host_shell = workspace.is_host_shell_allowed(".")
        security.save({**original_security, "allow_shell_execution": True})
        try:
            with patch("backend.core.sandbox_exec.grant_workspace_acl"), patch("backend.core.sandbox_exec.revoke_workspace_acl"):
                workspace.set_host_shell("project-root", True)
            created = self.client.post(
                "/api/assistant/plans",
                json={"objective": "Open the project in VS Code", "requestedOperations": ["open_vscode"]},
            )
            self.assertEqual(created.status_code, 200, created.text)
            plan_id = created.json()["data"]["id"]
            self.assertEqual(self.client.post(f"/api/assistant/plans/{plan_id}/approve", json={}).status_code, 200)
            handoff = self.client.post(
                f"/api/assistant/plans/{plan_id}/handoffs",
                json={"operation": "open_vscode"},
            ).json()["data"]
            self.assertEqual(self.client.post(f"/api/approvals/{handoff['approvalId']}/approve", json={}).status_code, 200)
            self.assertEqual(self.client.post(f"/api/assistant/handoffs/{handoff['id']}/prepare").status_code, 200)
            with patch("backend.assistant.broker.shutil.which", return_value=None), patch(
                "backend.assistant.broker.subprocess.Popen"
            ) as launcher:
                failed = self.client.post(f"/api/assistant/handoffs/{handoff['id']}/dispatch", json={})
                self.assertEqual(failed.status_code, 503, failed.text)
                self.assertEqual(failed.json()["error"]["code"], "assistantBrokerDependencyMissing")
                launcher.assert_not_called()
            state = self.client.get(f"/api/assistant/handoffs/{handoff['id']}")
            self.assertEqual(state.status_code, 200, state.text)
            self.assertEqual(state.json()["data"]["actionState"], "failed")
            self.assertFalse(state.json()["data"]["policy"]["sideEffects"])
        finally:
            with patch("backend.core.sandbox_exec.grant_workspace_acl"), patch("backend.core.sandbox_exec.revoke_workspace_acl"):
                workspace.set_host_shell("project-root", original_host_shell)
            security.save(original_security)


if __name__ == "__main__":
    unittest.main()
