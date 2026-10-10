"""Guard Dzen content rules wiring into style/gates."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DzenContentRulesTest(unittest.TestCase):
    def test_dzen_rules_file_present(self) -> None:
        text = (ROOT / "shared/dzen-content-rules.md").read_text(encoding="utf-8")
        low = text.lower()
        self.assertIn("ненормативн", low)
        self.assertIn("кликбейт", low)
        self.assertIn("комментар", low)
        self.assertIn("dzen.ru/help", low)

    def test_gemini_contract_bans_mat_for_dzen(self) -> None:
        rules = (ROOT / "shared/dzen-content-rules.md").read_text(encoding="utf-8")
        self.assertIn("ненормативн", rules.lower())
        contract = (ROOT / "shared/gemini-article-contract.md").read_text(encoding="utf-8")
        self.assertIn("3000–6000", contract)

    def test_dzen_rules_applied_to_writer_pipeline(self) -> None:
        text = (ROOT / "shared/dzen-content-rules.md").read_text(encoding="utf-8")
        self.assertIn("Title / Gemini", text)
        self.assertNotIn("GEO QA", text)

    def test_doctor_requires_dzen_rules(self) -> None:
        doc = (ROOT / "scripts/excalibur_blog_doctor.py").read_text(encoding="utf-8")
        self.assertIn("shared/dzen-content-rules.md", doc)


if __name__ == "__main__":
    unittest.main()
