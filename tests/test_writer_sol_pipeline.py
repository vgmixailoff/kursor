"""Guard Gemini evening-canon writer contracts (replaces Writer→Sol finality)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WriterSolContractsTest(unittest.TestCase):
    def test_pipeline_canon_gemini_final(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertTrue(canon["writer_is_final"])
        self.assertFalse(canon["sol_is_final"])
        self.assertTrue(canon.get("sol_disabled"))
        self.assertEqual(canon["writer_json_output"], "gemini-article.json")
        self.assertEqual(canon["writer_output"], "article.html")
        self.assertIn("shared/gemini-article-contract.md", canon["writer_allowed_sources"])
        self.assertTrue(canon["opening_rules"].get("gemini_owns_opening"))
        self.assertFalse(canon["opening_rules"].get("sol_owns_opening"))

    def test_sol_agent_and_skill_removed(self) -> None:
        self.assertFalse((ROOT / "agents/excalibur-blog-sol.md").exists())
        self.assertFalse((ROOT / "skills/sol-excalibur-blog/SKILL.md").exists())
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertTrue(canon.get("sol_disabled"))

    def test_writer_outputs_gemini_json(self) -> None:
        skill = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("gemini-article.json", skill)
        self.assertIn("gemini-3.8-flash", skill)
        self.assertIn("DISABLED", skill)

    def test_director_orders_gemini_before_stamp(self) -> None:
        d = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Gemini", d)
        self.assertIn("DISABLED", d)
        self.assertLess(d.find("### 3 Gemini"), d.find("### 4 Stamp"))

    def test_soul_files_removed(self) -> None:
        self.assertFalse((ROOT / "shared/SOUL.md").exists())
        self.assertFalse((ROOT / "shared/soul-examples").exists())


if __name__ == "__main__":
    unittest.main()
