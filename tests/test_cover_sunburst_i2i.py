"""Sunburst comic cover: TITLE into saved prompt + mascot i2i batch."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_cover_sunburst_i2i import (  # noqa: E402
    PLACEHOLDER_URL,
    TITLE_TOKEN,
    build_batch,
    fill_prompt,
)
from excalibur_blog_kie_gpt_image2_api import (  # noqa: E402
    MODEL_GPT_IMAGE_2_5_SUNBURST_I2I,
    batch_mcp_args,
    is_dummy_input_url,
    resolve_kie_model,
)


class CoverSunburstI2iTest(unittest.TestCase):
    def setUp(self) -> None:
        self.template = (ROOT / "shared/cover-sunburst-comic-prompt.txt").read_text(
            encoding="utf-8"
        )
        self.mascot = ROOT / "memory/cover/assets/cover-mascot.png"

    def test_template_has_title_token_twice_and_no_spoken_aside(self) -> None:
        self.assertEqual(self.template.count(TITLE_TOKEN), 2)
        self.assertIn("обязательно", self.template)
        self.assertNotIn("Для начала сохрани", self.template)
        self.assertIn("НИГДЕ на изображении не печатай", self.template)

    def test_fill_prompt_replaces_title_only(self) -> None:
        title = "Claude Code собрал команду из шести субагентов"
        filled = fill_prompt(self.template, title)
        self.assertNotIn(TITLE_TOKEN, filled)
        self.assertEqual(filled.count(title), 2)
        self.assertIn("обязательно", filled)

    def test_fill_prompt_rejects_missing_token(self) -> None:
        with self.assertRaises(ValueError):
            fill_prompt("комикс без токена", "Тема")

    def test_mascot_file_is_the_black_blob(self) -> None:
        self.assertTrue(self.mascot.is_file())
        self.assertGreater(self.mascot.stat().st_size, 100_000)
        header = self.mascot.read_bytes()[:8]
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")

    def test_build_batch_wires_sunburst_and_mascot(self) -> None:
        title = "Cursor сам закрыл баг за одну смену"
        batch = build_batch(title=title, template=self.template)
        self.assertEqual(batch["canon"], "sunburst_i2i")
        self.assertTrue(batch["prefer_local_reference"])
        self.assertEqual(batch["local_reference"], "memory/cover/assets/cover-mascot.png")
        self.assertEqual(batch["cover_hero_mode"], "mascot")
        args = batch["jobs"][0]["mcp_args"]
        self.assertEqual(args["input_urls"], [PLACEHOLDER_URL])
        self.assertEqual(args["aspect_ratio"], "16:9")
        self.assertEqual(args["resolution"], "1K")
        self.assertEqual(args["background"], "opaque")
        self.assertNotIn(TITLE_TOKEN, args["prompt"])
        self.assertIn(title, args["prompt"])
        self.assertEqual(batch["validation"]["model"], MODEL_GPT_IMAGE_2_5_SUNBURST_I2I)

    def test_cli_writes_batch_from_gemini_title(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as td:
            article = Path(td) / "article"
            article.mkdir()
            (article / "gemini-article.json").write_text(
                json.dumps({"TITLE": "Grok Bot собрал контент-команду"}, ensure_ascii=False),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/excalibur_blog_cover_sunburst_i2i.py"),
                    "--article-dir",
                    str(article),
                    "--root",
                    str(ROOT),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            batch = json.loads((article / "cover" / "t2i-batch.json").read_text(encoding="utf-8"))
            self.assertEqual(batch["canon"], "sunburst_i2i")
            self.assertIn("Grok Bot собрал контент-команду", batch["jobs"][0]["mcp_args"]["prompt"])

    def test_kie_resolves_sunburst_from_batch_without_cli_model(self) -> None:
        batch = build_batch(title="Тема теста", template=self.template)
        model = resolve_kie_model(cli_model="", batch=batch, is_t2i=False)
        self.assertEqual(model, MODEL_GPT_IMAGE_2_5_SUNBURST_I2I)

    def test_kie_batch_mcp_args_sunburst_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            batch_path = Path(td) / "t2i-batch.json"
            batch_path.write_text(
                json.dumps(
                    build_batch(title="Новая тема для обложки", template=self.template),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            payload = batch_mcp_args(batch_path, model=MODEL_GPT_IMAGE_2_5_SUNBURST_I2I)
            self.assertEqual(payload["aspect_ratio"], "16:9")
            self.assertEqual(payload["resolution"], "1K")
            self.assertEqual(payload["background"], "opaque")
            self.assertEqual(payload["input_urls"], [PLACEHOLDER_URL])
            self.assertIn("Новая тема для обложки", payload["prompt"])

    def test_dummy_mascot_url_is_not_fetched(self) -> None:
        self.assertTrue(is_dummy_input_url(PLACEHOLDER_URL))
        self.assertFalse(is_dummy_input_url("https://example.com/cover.png"))

    def test_pipeline_canon_points_at_sunburst(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertEqual(canon["cover"]["mode"], "sunburst_i2i")
        self.assertEqual(canon["cover_mascot"], "memory/cover/assets/cover-mascot.png")
        self.assertTrue(canon["cover"]["no_title_on_image"])


if __name__ == "__main__":
    unittest.main()
