import asyncio
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("RASPUTIN_DATA_DIR", tempfile.mkdtemp(prefix="rasputin-skill-policy-"))

from backend.engine.agent import AgentHub, AgentTask
from backend.mcp import skills


class SkillPolicyTests(unittest.TestCase):
    def test_builtins_are_declarative(self):
        for name, metadata in skills.BUILTINS.items():
            self.assertEqual(metadata.get("format"), skills.SKILL_FORMAT, name)
            self.assertNotRegex(
                metadata.get("content", ""),
                r"(?im)^\s*(?:async\s+def|def\s+run|import\s+|from\s+\S+\s+import\s+)",
            )

    def test_declared_tools_are_intersected_with_callable_tools(self):
        policy = skills.validate_policy(
            "web_research",
            "research",
            permissions={"allow_web_search": True},
            callable_tools=[
                {"id": "web_search", "callable": True},
                {"id": "fs_write", "callable": True},
            ],
        )
        self.assertEqual(policy["allowed_tool_ids"], {"web_search"})
        self.assertEqual([item["id"] for item in policy["tools"]], ["web_search"])

    def test_invalid_mode_disabled_missing_and_legacy_skills_fail_closed(self):
        with self.assertRaisesRegex(skills.SkillPolicyError, "mode not allowed"):
            skills.validate_policy(
                "web_research",
                "code",
                permissions={"allow_web_search": True},
                callable_tools=[],
            )

        skills.save_skill(
            "disabled-policy-test",
            "disabled",
            "## Workflow\nUse no tools.",
            {"format": skills.SKILL_FORMAT, "allowed_task_modes": ["research"]},
        )
        skills.set_enabled("disabled-policy-test", False)
        with self.assertRaisesRegex(skills.SkillPolicyError, "disabled"):
            skills.validate_policy("disabled-policy-test", "research", permissions={}, callable_tools=[])

        with self.assertRaisesRegex(ValueError, "skill missing"):
            skills.validate_policy("does-not-exist", "research", permissions={}, callable_tools=[])

        skills.import_skill(
            "legacy-python-test",
            "async def run(objective, plan, mcp, log):\n    return 'executed'",
            {"allowed_task_modes": ["research"]},
        )
        with self.assertRaisesRegex(skills.SkillPolicyError, "format unsupported"):
            skills.validate_policy("legacy-python-test", "research", permissions={}, callable_tools=[])
        with patch("backend.engine.agent.security.load", return_value={}):
            with self.assertRaisesRegex(skills.SkillPolicyError, "format unsupported"):
                AgentHub().start(
                    "must reject before task creation",
                    model="dry-run",
                    skill="legacy-python-test",
                    workspace_path=".",
                    mode="research",
                )

    def test_execute_injects_untrusted_skill_context_and_never_uses_sandbox(self):
        hub = AgentHub()
        task = AgentTask(
            "Find current findings",
            "dry-run",
            "web_research",
            workspace_path=".",
            mode="research",
        )
        task.permission_snapshot = {"allow_web_search": True}
        hub._agent_tools = lambda _task, _phase: [
            {"id": "web_search", "callable": True},
            {"id": "fs_write", "callable": True},
        ]
        captured = {}

        async def governed(_task, _phase, _role, sections, tools=None):
            captured["sections"] = sections
            captured["tools"] = tools
            return "done"

        hub.governed_chat = governed
        result = asyncio.run(hub.execute(task, "one step"))
        self.assertEqual(result, "done")
        self.assertEqual([item["id"] for item in captured["tools"]], ["web_search"])
        rendered = "\n".join(str(item.get("content", "")) for item in captured["sections"])
        self.assertIn("BEGIN UNTRUSTED CONTENT (declarative skill instructions)", rendered)
        self.assertNotIn("backend.core.sandbox", rendered)

        source = (Path(__file__).resolve().parents[1] / "backend" / "engine" / "agent.py").read_text(encoding="utf-8")
        execute_source = source.split("    async def execute(self, task, plan):", 1)[1].split("    async def reflect", 1)[0]
        self.assertNotIn("backend.core.sandbox", execute_source)
        self.assertNotIn("run_skill_in_sandbox", execute_source)


if __name__ == "__main__":
    unittest.main()
