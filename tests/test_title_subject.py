"""Guard Title subject and Wordstat ≤1 rules."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TitleSubjectWordstatTest(unittest.TestCase):
    def test_writer_requires_subject_in_h1(self) -> None:
        s = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        a = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        blob = (s + a).lower()
        self.assertIn("тема", blob)
        self.assertIn("искомое имя", s.lower())
        self.assertIn("заданная поисковая тема", s.lower())

    def test_title_agent_removed(self) -> None:
        self.assertFalse((ROOT / "agents/excalibur-blog-title.md").exists())
        self.assertFalse((ROOT / "skills/title-excalibur-blog/SKILL.md").exists())
        director = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Task(excalibur-blog-title, model=", director)
        self.assertIn("этих агентов нет", director)

    def test_scout_wordstat_at_most_one_call(self) -> None:
        s = (ROOT / "skills/scout-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        low = s.lower()
        self.assertIn("максимум **1**", low)
        self.assertNotIn("несколько вызовов", low)
        self.assertNotIn("2–4", s)

    def test_research_wordstat_at_most_one_call(self) -> None:
        r = (ROOT / "skills/excalibur-research/SKILL.md").read_text(encoding="utf-8")
        low = r.lower()
        self.assertIn("максимум **1**", low)
        self.assertNotIn("несколько вызовов", low)
        self.assertNotIn("2–4", r)

    def test_writer_owns_h1_subject_not_hidden(self) -> None:
        w = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        t = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        blob = (w + t).lower()
        self.assertTrue("тема" in blob or "h1" in blob)


if __name__ == "__main__":
    unittest.main()
