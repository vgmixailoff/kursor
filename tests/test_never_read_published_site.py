"""Guard that agents never read already-published site articles."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NeverReadPublishedSiteTest(unittest.TestCase):
    def test_writer_master_prompt_bans_live_site_articles(self) -> None:
        p = (ROOT / "shared/writer-master-prompt.md").read_text(encoding="utf-8")
        low = p.lower()
        self.assertIn("live-сайт", low)
        self.assertIn("article.html", low)

    def test_research_skill_bans_live_site_articles(self) -> None:
        r = (ROOT / "skills/excalibur-research/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("уже опубликованные статьи сайта", r.lower())

    def test_writer_skill_bans_live_site_articles(self) -> None:
        w = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        low = w.lower()
        self.assertTrue("live" in low or "сайт" in low, "writer skill must ban live site reads")

    def test_scout_agent_bans_published_site_articles(self) -> None:
        s = (ROOT / "agents/excalibur-blog-scout.md").read_text(encoding="utf-8")
        self.assertIn("уже опубликованные статьи сайта", s.lower())

    def test_canon_forbids_published_site_articles(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        blob = " ".join(canon["writer_forbidden_sources"]).lower()
        self.assertIn("published site articles", blob)

    def test_agents_md_warns_against_reading_site_articles(self) -> None:
        a = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("уже опубликованные статьи сайта", a.lower())


if __name__ == "__main__":
    unittest.main()
