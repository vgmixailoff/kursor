"""Titles-only memory: 30-day window + purge helpers."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_published_titles import (  # noqa: E402
    build_titles,
    humanize_slug,
    load_ledger_rows,
    parse_iso_date,
)
from excalibur_blog_memory_purge import (  # noqa: E402
    published_topic_ids,
    topic_from_dirname,
)


class TitlesOnlyMemoryTest(unittest.TestCase):
    def test_parse_iso_date(self) -> None:
        self.assertEqual(parse_iso_date("2026-08-11"), date(2026, 8, 11))
        self.assertIsNone(parse_iso_date("nope"))

    def test_build_titles_respects_30_day_window(self) -> None:
        as_of = date(2026, 8, 11)
        rows = build_titles(
            ROOT,
            statuses={"published"},
            days=30,
            as_of=as_of,
            previous_titles={},
        )
        cutoff = as_of - timedelta(days=30)
        self.assertGreater(len(rows), 10)
        for row in rows:
            d = parse_iso_date(row["date"])
            self.assertIsNotNone(d)
            assert d is not None
            self.assertGreaterEqual(d, cutoff, row)
            self.assertEqual(row["status"], "published")

    def test_shared_titles_file_mentions_30_day_window(self) -> None:
        text = (ROOT / "shared/published-titles.md").read_text(encoding="utf-8")
        self.assertIn("30", text)
        self.assertIn("anti-dup", text.lower())
        self.assertNotIn("draft_ready", text)

    def test_topic_from_dirname(self) -> None:
        self.assertEqual(
            topic_from_dirname("B159-openai-vypustila-kibermodel-tolko-dlya-zaschitnikov"),
            "B159",
        )

    def test_published_topic_ids_nonempty(self) -> None:
        ids = published_topic_ids(ROOT)
        self.assertIn("B159", ids)
        self.assertTrue(len(ids) > 50)

    def test_humanize_slug_is_not_a_publish_title(self) -> None:
        """Purge used to refresh titles after deleting article.meta.json."""
        self.assertEqual(
            humanize_slug("claude-code-sem-agentov-vmesto-studii"),
            "Claude code sem agentov vmesto studii",
        )
        text = (ROOT / "shared/published-titles.md").read_text(encoding="utf-8")
        self.assertIn("Claude Code: как запустить семь агентов вместо студии", text)
        self.assertNotIn("Claude code sem agentov vmesto studii", text)



if __name__ == "__main__":
    unittest.main()
