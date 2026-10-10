"""Guard orchestrator uses same-run Task subagents + Gemini 3.8 Flash."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_AGENTS = ("writer",)
ROLE_AGENTS = (
    "scout",
    "research",
    "writer",
    "schema",
    "cover",
    "indexer",
    "publish",
    "fixer",
    "content-learner",
)


class SubagentOrchestratorTest(unittest.TestCase):
    def test_memory_and_docs_exist(self) -> None:
        for rel in (
            "shared/subagent-memory-contract.md",
            "shared/cursor-subagents.md",
            "shared/per-agent-models.md",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_director_delegates_via_task(self) -> None:
        skill = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        agent = (ROOT / "agents/excalibur-blog-director.md").read_text(encoding="utf-8")
        self.assertIn("Task(excalibur-blog-writer", skill)
        self.assertIn("gemini-3.8-flash-high", skill)
        self.assertIn("environment=cloud", skill)
        self.assertIn("/in-cloud", skill)
        self.assertNotIn("все роли делает сам", agent)
        self.assertIn("model: grok-4.7-medium", agent)
        self.assertIn("model=grok-4.7-medium", agent)

    def test_cost_rules_allow_same_run_task(self) -> None:
        cost = (ROOT / "shared/cloud-cost-rules.md").read_text(encoding="utf-8")
        self.assertIn("Обязательно", cost)
        self.assertIn("Task(excalibur-blog-", cost)
        self.assertIn("/in-cloud", cost)
        self.assertIn("gemini-3.8-flash", cost)
        self.assertIn("origin/main", cost)
        self.assertIn("open_git_pr", cost)

    def test_text_roles_gemini_38(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertEqual(canon["text_model"], "gemini-3.8-flash")
        for role in TEXT_AGENTS:
            path = ROOT / f"agents/excalibur-blog-{role}.md"
            text = path.read_text(encoding="utf-8")
            self.assertIn("model: gemini-3.8-flash", text, role)
            cursor = ROOT / f".cursor/agents/excalibur-blog-{role}.md"
            self.assertTrue(cursor.is_file(), cursor)
            self.assertIn("model: gemini-3.8-flash", cursor.read_text(encoding="utf-8"), role)

    def test_role_agent_files_exist(self) -> None:
        for role in ROLE_AGENTS:
            self.assertTrue((ROOT / f"agents/excalibur-blog-{role}.md").is_file(), role)
            self.assertTrue((ROOT / f".cursor/agents/excalibur-blog-{role}.md").is_file(), role)

    def test_shared_memory_is_wired(self) -> None:
        agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("shared/subagent-memory-contract.md", agents_md)
        self.assertIn("Task(excalibur-blog-*)", agents_md)
        rule = (ROOT / ".cursor/rules/excalibur-blog-subagent-memory.mdc").read_text(
            encoding="utf-8"
        )
        self.assertIn("alwaysApply: true", rule)
        self.assertIn("subagent-memory-contract.md", rule)
        prompt = (ROOT / "shared/subagent-task-prompt.md").read_text(encoding="utf-8")
        self.assertIn("не вызывай Task", prompt)
        for role in ROLE_AGENTS:
            text = (ROOT / f"agents/excalibur-blog-{role}.md").read_text(encoding="utf-8")
            self.assertIn("Не вызывай Task", text, role)
            cursor = (ROOT / f".cursor/agents/excalibur-blog-{role}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Не вызывай Task", cursor, role)

    def test_merge_script_defaults_to_origin_main(self) -> None:
        src = (ROOT / "scripts/excalibur_blog_merge_to_main.py").read_text(encoding="utf-8")
        self.assertIn("git push origin HEAD:main", src)
        self.assertIn("open_git_pr", src)
        self.assertIn("if not args.pr and not args.via_pr", src)

    def test_only_writer_overrides_automation_model(self) -> None:
        grok_roles = (
            "scout",
            "research",
            "schema",
            "cover",
            "inline-visuals",
            "indexer",
            "publish",
            "fixer",
            "content-learner",
        )
        for role in grok_roles:
            for folder in ("agents", ".cursor/agents"):
                text = (ROOT / folder / f"excalibur-blog-{role}.md").read_text(encoding="utf-8")
                self.assertIn("model: grok-4.7-medium", text, f"{folder}/{role}")
                self.assertNotIn("-fast", text, f"{folder}/{role}")
        writer = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        self.assertIn("model: gemini-3.8-flash", writer)
        self.assertNotIn("grok-4.7", writer)
        skill = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("model=grok-4.7-medium", skill)
        self.assertIn("gemini-3.8-flash-high", skill)
        self.assertNotIn("model=inherit", skill)
        models = (ROOT / "shared/per-agent-models.md").read_text(encoding="utf-8")
        self.assertIn("model=grok-4.7-medium", models)
        self.assertIn("`-fast`", models)

    def test_plugin_version_mentions_task(self) -> None:
        plugin = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertIn("Task", plugin["description"])
        self.assertEqual(plugin["version"], "0.11.0")


if __name__ == "__main__":
    unittest.main()
