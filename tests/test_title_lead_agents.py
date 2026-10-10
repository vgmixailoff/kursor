"""Title agent + Gemini writer pipeline."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMOVED = (
    "agents/excalibur-blog-lead.md",
    "agents/excalibur-blog-article-editor.md",
    "agents/excalibur-blog-geo-qa.md",
    "agents/excalibur-blog-hook.md",
    "agents/excalibur-blog-title.md",
    "agents/excalibur-blog-description.md",
    "agents/excalibur-blog-cover-text.md",
    "skills/lead-excalibur-blog/SKILL.md",
    "skills/article-editor-excalibur-blog/SKILL.md",
    "skills/excalibur-geo-qa/SKILL.md",
    "skills/hook-excalibur-blog/SKILL.md",
    "skills/title-excalibur-blog/SKILL.md",
    "skills/description-excalibur-blog/SKILL.md",
    "skills/cover-text-excalibur-blog/SKILL.md",
)


class TitleWriterAgentsTest(unittest.TestCase):
    def test_writer_owns_title_and_forbids_seo_tails(self) -> None:
        a = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        s = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        blob = a + s
        self.assertIn("title-brief.json", blob)
        self.assertIn("без копипаста", blob)
        self.assertNotIn('"title_id"', blob)
        self.assertNotIn('"hook_id"', blob)
        self.assertIn("DESCRIPTION", blob)

    def test_removed_agents_and_skills_gone(self) -> None:
        for rel in REMOVED:
            self.assertFalse((ROOT / rel).exists(), rel)

    def test_telezhka_files_removed(self) -> None:
        for rel in (
            "shared/SOUL.md",
            "shared/lebedev-style.md",
            "shared/soul-examples",
            "agents/excalibur-blog-sol.md",
            "skills/sol-excalibur-blog/SKILL.md",
        ):
            self.assertFalse((ROOT / rel).exists(), rel)

    def test_pipeline_canon_writer_sources(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        sources = canon["writer_allowed_sources"]
        self.assertIn("shared/gemini-article-contract.md", sources)
        self.assertIn("research-notes.md", sources)
        self.assertNotIn("shared/SOUL.md", sources)
        self.assertTrue(canon.get("sol_disabled"))
        self.assertNotIn("lead.md", sources)
        self.assertNotIn("removed_agents", canon)

    def test_director_orders_gemini(self) -> None:
        d = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Gemini", d)
        self.assertIn("DISABLED", d)
        self.assertLess(d.find("### 1–2 Research"), d.find("### 3 Gemini"))
        self.assertLess(d.find("### 3 Gemini"), d.find("### 3b Sol"))
        self.assertIn("этих агентов нет", d)
        self.assertNotIn("Task(excalibur-blog-description, model=", d)
        self.assertNotIn("Task(excalibur-blog-cover-text", d)


if __name__ == "__main__":
    unittest.main()
