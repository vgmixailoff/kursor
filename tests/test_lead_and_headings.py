"""Guard Gemini final prose (no Sol rewrite over Gemini)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GONE = (
    "skills/excalibur-geo-qa/SKILL.md",
    "skills/article-editor-excalibur-blog/SKILL.md",
    "skills/lead-excalibur-blog/SKILL.md",
    "skills/hook-excalibur-blog/SKILL.md",
    "agents/excalibur-blog-geo-qa.md",
    "agents/excalibur-blog-article-editor.md",
    "agents/excalibur-blog-lead.md",
    "agents/excalibur-blog-hook.md",
)


class WriterMeaningSolFinalTest(unittest.TestCase):
    def test_master_prompt_is_gemini_final(self) -> None:
        p = (ROOT / "shared/writer-master-prompt.md").read_text(encoding="utf-8")
        low = p.lower()
        self.assertIn("gemini-article.json", low)
        self.assertIn("gemini-3.8-flash", low)
        self.assertIn("3000–6000", p)
        self.assertIn("sol", low)  # says Sol does not rewrite

    def test_removed_skills_and_agents_absent(self) -> None:
        for rel in GONE:
            self.assertFalse((ROOT / rel).exists(), rel)

    def test_writer_outputs_gemini_json(self) -> None:
        a = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        self.assertIn("gemini-article.json", a)
        self.assertIn("gemini-3.8-flash", a)

    def test_pipeline_canon_gemini_is_final(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertIs(canon.get("writer_is_final"), True)
        self.assertIs(canon.get("sol_is_final"), False)
        self.assertEqual(canon.get("writer_json_output"), "gemini-article.json")
        self.assertEqual(canon.get("writer_output"), "article.html")

    def test_research_notes_not_prose_template(self) -> None:
        r = (ROOT / "skills/excalibur-research/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("не пиши готовые h2", r.lower())


if __name__ == "__main__":
    unittest.main()
