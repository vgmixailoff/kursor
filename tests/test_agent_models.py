"""Non-writer roles pin Grok 4.7 Medium without Fast; Writer stays Gemini."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROK = "grok-4.7-medium"


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    header = text.split("---", 2)[1]
    return dict(line.split(":", 1) for line in header.splitlines() if ":" in line)


class AgentModelsTest(unittest.TestCase):
    def test_only_writer_overrides_to_gemini(self) -> None:
        for folder in (ROOT / "agents", ROOT / ".cursor" / "agents"):
            files = sorted(folder.glob("excalibur-blog-*.md"))
            self.assertGreaterEqual(len(files), 11)
            for path in files:
                fields = frontmatter(path)
                expected = " gemini-3.8-flash" if path.stem.endswith("-writer") else f" {GROK}"
                self.assertEqual(fields.get("model"), expected, str(path))
                self.assertNotIn("-fast", fields.get("model", ""), str(path))
                self.assertTrue(fields.get("name", "").strip(), str(path))
                self.assertTrue(fields.get("description", "").strip(), str(path))

    def test_docs_pin_medium_and_writer_exception(self) -> None:
        doc = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("model=grok-4.7-medium", doc)
        self.assertIn("model=gemini-3.8-flash-high", doc)
        self.assertNotIn("model=inherit", doc)
        self.assertIn("**Для самой Automation / Директора:** Grok 4.7, Medium, Fast выключен", doc)
        self.assertIn("они не переключают уже сохранённую", doc)
        skill = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("model=grok-4.7-medium", skill)
        self.assertNotIn("model=inherit", skill)


if __name__ == "__main__":
    unittest.main()
