"""Guard human-first → gemini-evening writer contracts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WriterEditorialContractsTest(unittest.TestCase):
    def test_writer_master_is_gemini(self) -> None:
        prompt = (ROOT / "shared/writer-master-prompt.md").read_text(encoding="utf-8")
        self.assertIn("gemini-article.json", prompt)
        self.assertIn("research-notes.md", prompt)
        self.assertIn("gemini-3.8-flash", prompt)
        self.assertIn("3000–6000", prompt)
        self.assertNotIn("lead.md", prompt)

        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertIn("shared/gemini-article-contract.md", canon["writer_allowed_sources"])
        self.assertTrue(canon["writer_is_final"])

    def test_writer_skill_gemini(self) -> None:
        skill = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("gemini-article.json", skill)
        self.assertIn("gemini-3.8-flash", skill)

    def test_article_writing_skill_is_wired_to_the_same_writer(self) -> None:
        path = "skills/dzen-article-writing/SKILL.md"
        article_skill = (ROOT / path).read_text(encoding="utf-8")
        self.assertTrue(article_skill.startswith("---\nname: dzen-article-writing\n"))
        self.assertEqual(
            article_skill,
            (ROOT / ".cursor" / path).read_text(encoding="utf-8"),
        )
        for rel in (
            "skills/writer-excalibur-blog/SKILL.md",
            "agents/excalibur-blog-writer.md",
            ".cursor/agents/excalibur-blog-writer.md",
            "shared/writer-master-prompt.md",
            "skills/director-excalibur-blog/SKILL.md",
        ):
            self.assertIn(path, (ROOT / rel).read_text(encoding="utf-8"), rel)
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertIn(path, canon["writer_allowed_sources"])
        self.assertIn(path, (ROOT / "scripts/excalibur_blog_research_start.py").read_text(encoding="utf-8"))
        self.assertIn(path, (ROOT / "scripts/excalibur_blog_doctor.py").read_text(encoding="utf-8"))
        for rel in ("writer-excalibur-blog", "director-excalibur-blog"):
            self.assertEqual(
                (ROOT / "skills" / rel / "SKILL.md").read_text(encoding="utf-8"),
                (ROOT / ".cursor/skills" / rel / "SKILL.md").read_text(encoding="utf-8"),
            )
        self.assertIn("model: gemini-3.8-flash", (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8"))
        self.assertIn("Task(excalibur-blog-writer, model=gemini-3.8-flash-high)", (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8"))

    def test_soul_layer_removed(self) -> None:
        self.assertFalse((ROOT / "shared/SOUL.md").exists())
        self.assertFalse((ROOT / "shared/soul-examples").exists())

    def test_pipeline_canon_sol_disabled(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertTrue(canon.get("sol_disabled"))
        self.assertFalse(canon["sol_is_final"])
        self.assertTrue(canon["writer_is_final"])
        self.assertIn("memory/blog/articles/*/article.html", canon["writer_forbidden_sources"])

    def test_published_titles_script_never_reads_html(self) -> None:
        source = (ROOT / "scripts/excalibur_blog_published_titles.py").read_text(encoding="utf-8")
        self.assertIn("article.meta.json", source)
        self.assertIn("never article.html", source.lower())
        self.assertNotIn('/ "article.html"', source)
        self.assertNotIn('article_dir / "article.html"', source)

    def test_published_titles_builds_from_meta_only(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_published_titles import write_titles

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared"
            shared.mkdir(parents=True)
            (shared / "published-articles.md").write_text(
                "# ledger\n\n"
                "| date | topic_id | slug | url | status |\n"
                "|------|----------|------|-----|--------|\n"
                "| 2026-07-01 | B01 | demo-slug | /demo-slug/ | published |\n",
                encoding="utf-8",
            )
            article_dir = root / "memory" / "blog" / "articles" / "B01-demo-slug"
            article_dir.mkdir(parents=True)
            (article_dir / "article.meta.json").write_text(
                '{"topic_id":"B01","slug":"demo-slug","title":"Демо заголовок"}\n',
                encoding="utf-8",
            )
            (article_dir / "article.html").write_text(
                "<p>BODY MUST NOT APPEAR IN TITLES FILE</p>\n",
                encoding="utf-8",
            )
            out_dir = root / "out"
            result = write_titles(root, article_dir=out_dir, days=None)
            text = (out_dir / "published-titles-only.md").read_text(encoding="utf-8")
            self.assertEqual(result["count"], 1)
            self.assertIn("Демо заголовок", text)
            self.assertNotIn("BODY MUST NOT APPEAR", text)

    def test_legacy_writer_ready_gate_removed(self) -> None:
        self.assertFalse((ROOT / "scripts/excalibur_blog_writer_ready_gate.py").exists())
        self.assertFalse((ROOT / "agents/excalibur-blog-article-editor.md").exists())


if __name__ == "__main__":
    unittest.main()
