"""Tests for Dzenчик living-speech title rules, light SEO/GEO layer, and article gates."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_gemini_article_gate import check_article
from excalibur_blog_pipeline_canon import stamp_article, load_canon


class DzenTitleAndBodyRulesTest(unittest.TestCase):
    def test_dzen_title_rules_in_contracts(self) -> None:
        contracts = [
            (ROOT / "shared/gemini-article-contract.md").read_text(encoding="utf-8"),
            (ROOT / "shared/writer-master-prompt.md").read_text(encoding="utf-8"),
            (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8"),
        ]
        for c in contracts:
            self.assertIn("TITLE", c)
            self.assertIn("имя", c.lower())
            self.assertIn("заголов", c.lower())
        self.assertIn("не начинай все заголовки", contracts[2].lower())

    def test_gate_fails_emoji_in_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(
                    {
                        "TITLE": "💻 Cursor MCP: как подключить серверы без кода",
                        "COVER_LINE1": "Cursor MCP",
                        "COVER_LINE2": "подключение серверов",
                        "COVER_PROMPT": "x" * 60,
                        "COVER_ALT": "Обложка про серверы",
                        "BODY": "<p>" + ("живое слово " * 500) + "</p>",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = check_article(d)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("emoji" in e.lower() for e in report["errors"]))

    def test_gate_fails_template_phrase_in_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(
                    {
                        "TITLE": "Cursor: пошаговая инструкция для подключения серверов",
                        "COVER_LINE1": "Cursor",
                        "COVER_LINE2": "подключение серверов",
                        "COVER_PROMPT": "x" * 60,
                        "COVER_ALT": "Обложка про серверы",
                        "BODY": "<p>" + ("живое слово " * 500) + "</p>",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report = check_article(d)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("template phrase" in e.lower() for e in report["errors"]))

    def test_gate_fails_kantselyarit_in_body(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(
                    {
                        "TITLE": "Cursor MCP: как подключить серверы без кода",
                        "COVER_LINE1": "Cursor MCP",
                        "COVER_LINE2": "подключение серверов",
                        "COVER_PROMPT": "x" * 60,
                        "COVER_ALT": "Обложка про серверы",
                        "BODY": (
                            "<p>Важно отметить, что инструмент работает отлично. "
                            + ("живое слово " * 450)
                            + "</p>"
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "article.html").write_text(
                "<p>Важно отметить, что инструмент работает отлично. "
                + ("живое слово " * 450)
                + "</p>",
                encoding="utf-8",
            )
            report = check_article(d)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("канцелярит" in e.lower() for e in report["errors"]))

    def test_pipeline_canon_sets_title_aeo_question_form(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "article.html").write_text(
                "<p>Первый абзац статьи живой речью отвечает на поисковый запрос.</p>\n",
                encoding="utf-8",
            )
            (d / "title-brief.json").write_text(
                json.dumps(
                    {
                        "h1": "Cursor MCP: как подключить серверы без кода",
                        "title": "Cursor MCP: как подключить серверы без кода",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "description-brief.json").write_text(
                json.dumps(
                    {
                        "description": "Разбираем подключение серверов MCP в Cursor без кода: настройка конфига и проверка связки на практике.",
                        "verdict": "PASS",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stamp_article(d, ROOT)
            meta = json.loads((d / "article.meta.json").read_text(encoding="utf-8"))
            meta_ab = meta.get("meta_ab", {})
            self.assertEqual(meta["title"], "Cursor MCP: как подключить серверы без кода")
            self.assertEqual(meta_ab["title_seo"], "Cursor MCP: как подключить серверы без кода")
            self.assertEqual(meta_ab["title_ctr"], "Cursor MCP: как подключить серверы без кода")
            self.assertEqual(meta_ab["title_aeo"], "Cursor MCP: как подключить серверы без кода?")

    def test_stamp_overwrites_stale_meta_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "article.html").write_text(
                "<p>Первый абзац.</p>\n", encoding="utf-8"
            )
            (d / "article.meta.json").write_text(
                json.dumps(
                    {"title": "Старый заголовок", "h1": "Старый заголовок"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "title-brief.json").write_text(
                json.dumps(
                    {
                        "h1": "Cursor MCP: новый заголовок из Gemini",
                        "title": "Cursor MCP: новый заголовок из Gemini",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "description-brief.json").write_text(
                json.dumps(
                    {
                        "description": "Разбираем подключение серверов MCP в Cursor без кода: настройка конфига и проверка связки на практике.",
                        "verdict": "PASS",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stamp_article(d, ROOT)
            meta = json.loads((d / "article.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["title"], "Cursor MCP: новый заголовок из Gemini")
            self.assertEqual(meta["h1"], "Cursor MCP: новый заголовок из Gemini")


if __name__ == "__main__":
    unittest.main()
