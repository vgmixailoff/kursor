"""Local image preflight must catch broken evidence before WordPress upload."""
from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_inline_fact_card import inject_inline_figures  # noqa: E402
from excalibur_blog_inline_visual import build_batch, inject, load_plan, render_fallback  # noqa: E402
from excalibur_blog_gemini_article_gate import check_article  # noqa: E402
from excalibur_blog_kie_gpt_image2_api import batch_mcp_args, resolve_kie_model  # noqa: E402
from excalibur_blog_wp_publish import validate_local_article_images  # noqa: E402


class ArticleImagesTest(unittest.TestCase):
    def test_missing_local_image_blocks_publish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = ('<figure><img src="cover/official-01.png" alt="Тарифы">'
                    '<figcaption>Тарифы сервиса</figcaption></figure>')
            errors = validate_local_article_images(Path(tmp), html)
            self.assertTrue(any("inline image missing" in error for error in errors))

    def test_official_image_requires_source_caption_and_alt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            cover = article / "cover"
            cover.mkdir()
            Image.new("RGB", (16, 16), "white").save(cover / "official-01.png")
            bad = '<figure><img src="cover/official-01.png" alt=""></figure>'
            errors = validate_local_article_images(article, bad)
            self.assertTrue(any("missing alt" in error for error in errors))
            self.assertTrue(any("missing visible figcaption" in error for error in errors))
            self.assertTrue(any("missing source URL" in error for error in errors))
            good = ('<figure data-source-url="https://example.org/pricing">'
                    '<img src="cover/official-01.png" alt="Таблица тарифов">'
                    '<figcaption>Тарифы на официальном сайте</figcaption></figure>')
            self.assertEqual(validate_local_article_images(article, good), [])

    def test_diagram_never_falls_to_article_end(self) -> None:
        html = '<p>Что изменилось.</p><h2>Как это работает</h2><p>Объяснение.</p><p>Вывод.</p>'
        panel = [{"slot": "inline_1", "src": "cover/inline-01.png", "alt": "Схема",
                  "after_h2_index": 7}]
        output = inject_inline_figures(html, panel)
        self.assertLess(output.index('data-slot="inline_1"'), output.index("<p>Вывод.</p>"))

    def test_diagram_uses_writer_slot(self) -> None:
        html = ('<p>Вступление.</p><h2>Разбор</h2><p>Нужное объяснение.</p>'
                '<figure data-slot="inline_1"></figure><p>Следующий довод.</p>')
        panel = [{"slot": "inline_1", "src": "cover/inline-01.png", "alt": "Схема",
                  "after_h2_index": 0}]
        self.assertTrue(any("unfilled inline image slot" in error for error in
                            validate_local_article_images(Path("."), html)))
        output = inject_inline_figures(html, panel)
        self.assertLess(output.index("Нужное объяснение"), output.index('data-slot="inline_1"'))
        self.assertLess(output.index('data-slot="inline_1"'), output.index("Следующий довод"))

    def test_diagram_escapes_writer_alt_in_html(self) -> None:
        html = '<p>Разбор.</p><figure data-slot="inline_1"></figure>'
        output = inject_inline_figures(html, [{"slot": "inline_1", "src": "cover/inline-01.png",
                                               "alt": 'Задача "А" & результат'}])
        self.assertIn('alt="Задача &quot;А&quot; &amp; результат"', output)

    def test_screenshot_caption_must_be_paired_and_russian(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            (article / "gemini-article.json").write_text(json.dumps({
                "TITLE": "Cursor: что изменилось", "COVER_LINE1": "Cursor",
                "SCREENSHOT1_ALT": "Settings panel",
            }, ensure_ascii=False), encoding="utf-8")
            (article / "article.html").write_text("<p>Короткий текст.</p>", encoding="utf-8")
            errors = check_article(article)["errors"]
            self.assertTrue(any("SCREENSHOT1_ALT and SCREENSHOT1_CAPTION" in e for e in errors))
            self.assertTrue(any("SCREENSHOT1_ALT must be Russian" in e for e in errors))

    def test_inline_visual_plan_uses_writer_labels_and_separate_kie_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            (article / "cover").mkdir()
            (article / "gemini-article.json").write_text(
                '{"BODY":"<p>Как это работает.</p><figure data-slot=\\"inline_1\\"></figure>",'
                '"INLINE1_ONIMAGE":"Путь задачи\\nЗапрос\\nПроверка\\nРезультат",'
                '"INLINE1_ALT":"Путь задачи от запроса до результата"}', encoding="utf-8")
            (article / "cover" / "inline-visual-plan.json").write_text(
                '{"slot":"inline_1","type":"process","why":"пояснить порядок"}',
                encoding="utf-8")
            plan, _, lines = load_plan(article)
            batch = build_batch(plan, lines, "Белая бумага и чёрные линии.")
            self.assertEqual(batch["model"], "gpt-image-2-text-to-image")
            self.assertEqual(batch["validation"]["labels"], lines)
            self.assertIn("Запрос", batch["jobs"][0]["mcp_args"]["prompt"])
            self.assertNotIn("cover.png", str(batch))
            batch_path = article / "cover" / "inline-visual-batch.json"
            batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(resolve_kie_model(cli_model="", batch=batch, is_t2i=True),
                             "gpt-image-2-text-to-image")
            self.assertEqual(batch_mcp_args(batch_path, model="gpt-image-2-text-to-image")["aspect_ratio"],
                             "16:9")

    def test_ai_visual_injects_only_body_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            (article / "cover").mkdir()
            Image.new("RGB", (16, 16), "white").save(article / "cover" / "inline-01.png")
            body = ('<p>Объяснение.</p><figure data-slot="inline_1"></figure>'
                    '<p>Следующая мысль.</p>')
            (article / "article.html").write_text(body, encoding="utf-8")
            inject(article, "inline_1", "Путь задачи")
            updated = (article / "article.html").read_text(encoding="utf-8")
            self.assertIn('src="cover/inline-01.png"', updated)
            self.assertLess(updated.index('data-slot="inline_1"'), updated.index("Следующая мысль"))

    def test_fallback_is_monochrome_and_uses_selected_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp)
            out = render_fallback(article, {"slot": "inline_2", "type": "process"},
                                  ["Как идёт задача", "Запрос", "Проверка", "Ответ"])
            self.assertEqual(out.name, "inline-02.png")
            with Image.open(out) as image:
                self.assertEqual(image.size, (1200, 675))
                pixels = image.tobytes()
                self.assertTrue(all(pixels[i] == pixels[i + 1] == pixels[i + 2]
                                    for i in range(0, len(pixels), 3)))


if __name__ == "__main__":
    unittest.main()
