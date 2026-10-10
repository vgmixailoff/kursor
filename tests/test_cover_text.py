"""Guard cover-text gate and prompt TEXT LOCK (no overlay: network draws text)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CoverTextTest(unittest.TestCase):
    def test_gate_pass_on_clear_russian_strings(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "hook": "Cursor стал дешевле на треть",
                "highlight": "дешевле",
                "sticky": "новой модели нет",
                "inline_labels": {
                    "inline_1": ["заявление 3 августа", "минус 20–30%", "без новой модели"],
                    "inline_2": ["с экраном", "без экрана", "до 80%"],
                    "inline_3": ["MCP", "навыки", "экран"],
                },
            }
        )
        self.assertEqual(verdict["status"], "PASS")

    def test_gate_blocks_english_headline(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "hook": "Token burn rate",
                "highlight": "burn",
                "sticky": "",
                "inline_labels": {
                    "inline_1": ["токены", "экран"],
                    "inline_2": ["токены", "экран"],
                    "inline_3": ["токены", "экран"],
                },
            }
        )
        self.assertEqual(verdict["status"], "BLOCK")
        self.assertTrue(any("Latin words" in e for e in verdict["errors"]))

    def test_gate_blocks_highlight_outside_hook(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "hook": "Cursor стал дешевле на треть",
                "highlight": "бюджет",
                "sticky": "",
                "inline_labels": {
                    "inline_1": ["токены", "экран"],
                    "inline_2": ["токены", "экран"],
                    "inline_3": ["токены", "экран"],
                },
            }
        )
        self.assertEqual(verdict["status"], "BLOCK")

    def test_legacy_quad_scripts_removed(self) -> None:
        for rel in (
            "scripts/excalibur_blog_cover_quad_prompt.py",
            "scripts/excalibur_blog_quad_apply.py",
            "scripts/excalibur_blog_cover_quad_split.py",
            "scripts/excalibur_blog_quad_manifest.py",
            "shared/blog-cover-quad-canvas-contract.md",
        ):
            self.assertFalse((ROOT / rel).exists(), rel)

    def test_evening_cover_text_gate(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "canon": "sunburst_i2i",
                "line1": "Agents API",
                "line2": "шесть ролей внутри одного бота",
                "cover_prompt": (
                    "candlelit quill parchment scrolls marble bust growing from "
                    "pure black canvas bottom half Caravaggio chiaroscuro"
                ),
                "highlight": "",
            }
        )
        self.assertEqual(verdict["status"], "PASS", verdict)
        self.assertEqual(verdict["canon"], "sunburst_i2i")

    def test_evening_cover_text_gemini_live(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "canon": "sunburst_i2i",
                "line1": "Gemini Live",
                "line2": "разговор без пауз",
                "cover_prompt": "Маскот в наушниках говорит в микрофон за рабочим столом, пока в воздухе крутятся шестерёнки",
                "highlight": "",
            }
        )
        self.assertEqual(verdict["status"], "PASS", verdict)
        self.assertEqual(verdict["canon"], "sunburst_i2i")

    def test_evening_cover_text_gemini_antigravity(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "canon": "sunburst_i2i",
                "line1": "Gemini Antigravity",
                "line2": "прежний каркас скоро отключат",
                "cover_prompt": "Комиксная сцена в стиле Sunburst: за столом сидит рыжий кот-инженер в очках",
                "highlight": "",
            }
        )
        self.assertEqual(verdict["status"], "PASS", verdict)
        self.assertEqual(verdict["canon"], "sunburst_i2i")

    def test_evening_cover_text_blocks_digits(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_text_gate import validate_cover_text

        verdict = validate_cover_text(
            {
                "canon": "black_canvas_t2i",
                "line1": "Claude Code",
                "line2": "семь правил 2026",
                "cover_prompt": "x" * 60,
            }
        )
        self.assertEqual(verdict["status"], "BLOCK")

        versioned_name = validate_cover_text(
            {
                "canon": "sunburst_i2i",
                "line1": "GPT-5",
                "line2": "проверка новой модели",
                "cover_prompt": "x" * 60,
            }
        )
        self.assertEqual(versioned_name["status"], "PASS", versioned_name)


if __name__ == "__main__":
    unittest.main()
