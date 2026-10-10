"""Scout --check-query must catch Cyrillic queries vs Latin ledger/live slugs.

INC-20260727-0805: «автопостинг вк» previously returned NO CANNIBALIZATION while
WP13778 /avtoposting-vk-make-google-sheets/ was already published.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_scout_helper import (  # noqa: E402
    check_overlap,
    normalize_and_tokenize,
    transliterate_ru,
)


class ScoutHelperQuerySlugCoverTests(unittest.TestCase):
    def test_transliterate_avtoposting(self) -> None:
        self.assertEqual(transliterate_ru("автопостинг"), "avtoposting")
        self.assertEqual(normalize_and_tokenize("автопостинг вк"), {"avtop", "vk"})
        self.assertEqual(
            normalize_and_tokenize("avtoposting-vk-make-google-sheets"),
            {"avtop", "vk", "make", "googl", "sheet"},
        )

    def test_vk_autoposting_covers_ledger_slug(self) -> None:
        topics = [
            {
                "topic_id": "WP13778",
                "primary_query": "avtoposting vk make google sheets",
                "slug": "avtoposting-vk-make-google-sheets",
                "priority": "published",
            }
        ]
        warnings = check_overlap("автопостинг вк", topics, {"WP13778"})
        critical = [w for w in warnings if w["severity"] == "CRITICAL"]
        self.assertTrue(critical, warnings)
        self.assertTrue(
            any("SLUG KEYWORD COVER" in w["message"] for w in critical),
            critical,
        )
        self.assertEqual(critical[0]["topic_id"], "WP13778")

    def test_unrelated_query_no_slug_cover(self) -> None:
        topics = [
            {
                "topic_id": "WP13778",
                "primary_query": "avtoposting vk make google sheets",
                "slug": "avtoposting-vk-make-google-sheets",
                "priority": "published",
            }
        ]
        warnings = check_overlap("cookie баннер на сайт", topics, set())
        self.assertFalse(
            any("SLUG KEYWORD COVER" in str(w.get("message") or "") for w in warnings),
            warnings,
        )

    def test_exact_primary_still_critical(self) -> None:
        topics = [
            {
                "topic_id": "B25",
                "primary_query": "ai агенты для бизнеса",
                "slug": "ai-agenty-dlya-biznesa",
                "priority": "published",
            }
        ]
        warnings = check_overlap("ai агенты для бизнеса", topics, {"B25"})
        self.assertTrue(
            any("EXACT MATCH" in w["message"] for w in warnings if w["severity"] == "CRITICAL"),
            warnings,
        )


if __name__ == "__main__":
    unittest.main()
