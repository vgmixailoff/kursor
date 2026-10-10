"""Visible length check: one command, no article-in-Python calibrators."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from excalibur_blog_body_len import (  # noqa: E402
    exit_code,
    measure_body,
    measure_dir,
)
from excalibur_blog_gemini_article_gate import visible_text  # noqa: E402


def _paragraphs(n_chars: int) -> str:
    return f"<p>{'А' * n_chars}</p>"


class BodyLenTest(unittest.TestCase):
    def test_visible_matches_gate_and_range(self) -> None:
        html = _paragraphs(4200)
        self.assertEqual(len(visible_text(html)), 4200)
        report = measure_body(html)
        self.assertEqual(report["visible"], 4200)
        self.assertEqual(report["status"], "IN_RANGE")
        self.assertEqual(report["delta"], 0)
        self.assertEqual(exit_code(report), 0)

    def test_short_and_long(self) -> None:
        short = measure_body(_paragraphs(100))
        self.assertEqual(short["status"], "SHORT")
        self.assertGreater(short["delta"], 0)
        self.assertEqual(exit_code(short), 2)
        long = measure_body(_paragraphs(6600))
        self.assertEqual(long["status"], "LONG")
        self.assertEqual(exit_code(long), 2)
        self.assertEqual(measure_body(_paragraphs(2500))["status"], "IN_RANGE")
        self.assertEqual(measure_body(_paragraphs(6500))["status"], "IN_RANGE")

    def test_cli_and_forbidden_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            payload = {"BODY": _paragraphs(4000), "TITLE": "Cursor: проверка"}
            (article / "gemini-article.json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/excalibur_blog_body_len.py"),
                    "--article-dir",
                    str(article),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("status=IN_RANGE", proc.stdout)
            self.assertIn("visible=4000", proc.stdout)

            (article / "calibrate2.py").write_text("print('article')\n", encoding="utf-8")
            report = measure_dir(article)
            self.assertEqual(report["length_scripts"], ["calibrate2.py"])
            self.assertEqual(exit_code(report), 3)

    def test_writer_canon_bans_length_programs(self) -> None:
        skill = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        agent = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        prompt = (ROOT / "shared/writer-master-prompt.md").read_text(encoding="utf-8")
        for text in (skill, agent, prompt):
            self.assertIn("excalibur_blog_body_len.py", text)
            self.assertIn("calibrate", text.casefold())
        self.assertIn("не больше 3", skill.casefold())
        self.assertNotIn("4350", skill)
        self.assertIn("не вставляй статью", skill.casefold())
