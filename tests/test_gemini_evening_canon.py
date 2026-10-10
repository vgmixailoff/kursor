"""Guard gemini-evening-v1 contracts + gates."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pad_body(parts_before: list[str], cta: str, parts_after: list[str], target: int = 4100) -> str:
    filler = (
        "<p>Ещё один короткий абзац про практику за кухонным столом: вы берёте "
        "один шаг, проверяете результат и только потом усложняете связку.</p>\n"
    )
    before = "".join(parts_before)
    after = "".join(parts_after)
    while True:
        body = before + cta + after
        # approximate visible length
        import re
        vis = re.sub(r"<[^>]+>", " ", body)
        vis = re.sub(r"\s+", " ", vis).strip()
        if len(vis) >= target and 0.20 <= body.find("t.me/maya_pro") / max(len(body), 1) <= 0.80:
            return body
        if len(vis) < target:
            before += filler
            after += filler
        elif body.find("t.me/maya_pro") / max(len(body), 1) < 0.20:
            before = filler + before
        else:
            after += filler
        if len(body) > 20000:
            return body


class GeminiEveningCanonTest(unittest.TestCase):
    def test_pipeline_canon_version(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        self.assertEqual(canon["version"], "gemini-evening-v1")
        self.assertTrue(canon["writer_is_final"])
        self.assertTrue(canon.get("sol_disabled"))
        self.assertFalse(canon["sol_is_final"])
        self.assertEqual(canon["text_model"], "gemini-3.8-flash")
        self.assertEqual(canon["cover_model"], "gpt-image-2-5-sunburst-image-to-image")
        self.assertFalse(canon["cover"]["pink_ribbon"])
        self.assertFalse(canon["cover"]["maya_pro_badge_on_cover"])

    def test_how_we_ship_and_schedule_docs(self) -> None:
        how = (ROOT / "shared/HOW-WE-SHIP.md").read_text(encoding="utf-8")
        self.assertIn("gemini-3.8-flash", how)
        self.assertIn("06:00", how)
        cloud = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("06:00", cloud)
        self.assertIn("viraldzen", cloud.casefold())
        self.assertIn("gemini-evening-v1", cloud)
        self.assertIn("ViralDzen", (ROOT / "shared/morning-viral-slot.md").read_text(encoding="utf-8"))

    def test_slot_types_and_x_mcp_scout(self) -> None:
        scout = (ROOT / "skills/scout-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        for slot in ("viral-06", "news-12", "case-14", "news-18"):
            self.assertIn(slot, scout)
        self.assertIn("search_posts_all", scout)
        self.assertIn("search_news", scout)
        # X is a signal warehouse only — never mentioned in the article.
        self.assertIn("не", scout.lower())
        cloud = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("новость", cloud)
        self.assertIn("кейс", cloud)
        self.assertIn("X MCP", cloud)

    def test_viraldzen_skill_vendored(self) -> None:
        skill = ROOT / "skills/viraldzen-collect/SKILL.md"
        self.assertTrue(skill.is_file())
        text = skill.read_text(encoding="utf-8")
        self.assertIn("viraldzen", text.casefold())
        self.assertIn("morning-viral-slot", text)

    def test_materialize_and_gate(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_gemini_materialize import materialize
        from excalibur_blog_gemini_article_gate import check_article

        body_before = [
            "<p>Grok Bot собрал контент-команду из шести ролей, и вы только жмёте да.</p>\n",
            "<h2>Как это устроено</h2>\n",
            "<p>Сначала фиксируете задачу, потом бот раскладывает роли.</p>\n",
            "<p>Один проход можно сравнить с ручной сборкой.</p>\n",
        ]
        cta = (
            "<p>В середине пути загляните в "
            '<a href="https://t.me/maya_pro">Ковчег</a>.</p>\n'
        )
        body_after = [
            "<h2>Что получили</h2>\n",
            "<p>Роли работают как смена, а не как зоопарк вкладок.</p>\n",
            "<ul><li>один вход</li><li>шесть ролей</li></ul>\n",
            "<p>Практический результат виден после первого прохода.</p>\n",
        ]
        body = _pad_body(body_before, cta, body_after, 4100)
        data = {
            "TITLE": "Grok Bot собрал контент-команду из шести ролей",
            "COVER_LINE1": "Grok Bot",
            "COVER_LINE2": "шесть ролей внутри одного бота",
            "COVER_PROMPT": (
                "Caravaggio still life with quill parchment scrolls marble bust "
                "and candle growing from pure black canvas bottom third"
            ),
            "COVER_ALT": "Grok Bot на чёрном холсте",
            "DESCRIPTION": (
                "Бот раскладывает контент-команду на шесть ролей в одном окне, "
                "а вы только подтверждаете каждый шаг."
            ),
            "BODY": body,
            "INLINE1_ONIMAGE": "было\nсобрали\nполучили",
            "INLINE1_ALT": "схема было-собрали-получили",
            "INLINE2_ONIMAGE": "роль 1\nроль 2\nроль 3",
            "INLINE2_ALT": "три роли",
            "INLINE3_ONIMAGE": "артефакт\nпольза",
            "INLINE3_ALT": "артефакт",
        }
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            report = materialize(d, data)
            self.assertEqual(report["status"], "PASS")
            self.assertTrue((d / "article.html").is_file())
            self.assertTrue((d / "cover" / "cover-text.json").is_file())
            self.assertTrue((d / "description-brief.json").is_file())
            cover = json.loads((d / "cover" / "cover-text.json").read_text(encoding="utf-8"))
            self.assertEqual(cover["canon"], "sunburst_i2i")
            gate = check_article(d)
            self.assertEqual(gate["status"], "PASS", gate)

    def test_gate_fails_kovcheg_ai_and_short_body(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_gemini_article_gate import check_article

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(
                    {
                        "TITLE": "Cursor",
                        "COVER_LINE1": "Cursor",
                        "COVER_LINE2": "тест",
                        "COVER_PROMPT": "x" * 50,
                        "COVER_ALT": "a",
                        "BODY": "<p>коротко</p>",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "article.html").write_text(
                '<p>коротко <a href="https://t.me/kovcheg_ai">x</a></p>',
                encoding="utf-8",
            )
            gate = check_article(d)
            self.assertEqual(gate["status"], "FAIL")
            joined = " ".join(gate["errors"]).casefold()
            self.assertTrue("2500" in joined or "chars" in joined)
            self.assertIn("kovcheg", joined)

    def test_cover_black_prompt_builds_t2i_batch(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_cover_black_prompt import build_batch

        batch = build_batch(
            {
                "line1": "Claude Code",
                "line2": "семь правил",
                "cover_prompt": (
                    "seven aged scrolls on dark marble with elderly hands tying "
                    "wax seal emerging from pure black canvas"
                ),
            }
        )
        self.assertEqual(batch["canon"], "black_canvas_t2i")
        args = batch["jobs"][0]["mcp_args"]
        self.assertNotIn("input_urls", args)
        self.assertEqual(args["resolution"], "1K")
        self.assertIn("Claude Code", args["prompt"])
        self.assertIn("pink ribbon", args["prompt"].casefold())

    def test_inline_fact_card_renders(self) -> None:
        import sys

        from PIL import Image

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_inline_fact_card import choose_layout, render_fact_card

        self.assertEqual(
            choose_layout(
                [
                    "Архитектура Cursor Projects",
                    "Координатор держит план",
                    "Субагенты пишут код",
                    "Общая память",
                ]
            ),
            "architecture",
        )
        self.assertEqual(
            choose_layout(
                [
                    "Самоотчет о продуктивности",
                    "Прирост на тридцать процентов",
                    "Шестикратное ускорение",
                ]
            ),
            "stats",
        )
        self.assertEqual(
            choose_layout(
                [
                    "Особенности и ограничения беты",
                    "Облачная среда по умолчанию без локального координатора",
                    "Координатор никогда не пишет программный код сам",
                ]
            ),
            "rows",
        )
        from excalibur_blog_inline_fact_card import extract_stats

        stats = extract_stats(
            [
                "Прирост принятых пулл-реквестов на тридцать процентов",
                "Шестикратное ускорение для основных пользователей",
                "Обработка от двадцати до ста задач в день",
            ]
        )
        self.assertEqual([n for n, _ in stats], ["+30%", "×6", "20–100"])
        self.assertNotIn("ь процент", stats[0][1])
        self.assertFalse(stats[1][1].casefold().startswith("ное"))
        self.assertIn("пулл", stats[0][1].casefold())
        self.assertEqual(stats[2][1], "задач в день")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "inline-01.png"
            kind = render_fact_card(
                [
                    "Архитектура Cursor Projects",
                    "Координатор держит план и управляет потоком",
                    "Субагенты параллельно пишут код и тесты",
                    "Общая память исключает повторные объяснения",
                ],
                out_path=out,
            )
            self.assertEqual(kind, "architecture")
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)
            with Image.open(out) as img:
                self.assertEqual(img.size, (1200, 675))
            overflow = Path(td) / "overflow.png"
            render_fact_card(
                [
                    "Особенности и ограничения беты",
                    "Облачная среда по умолчанию без локального координатора",
                    "Координатор никогда не пишет программный код сам",
                    "Тарифные планы и финальные лимиты пока не опубликованы",
                ],
                out_path=overflow,
                layout="rows",
            )
            with Image.open(overflow) as overflow_img:
                pix = overflow_img.load()
                dark_edge = 0
                for y in range(140, 675):
                    r, g, b = pix[1188, y][:3]
                    if r < 40 and g < 40 and b < 40:
                        dark_edge += 1
            self.assertLess(dark_edge, 8, "text must wrap inside the frame")

    def test_sol_rewrite_skips_when_gemini_json(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_sol_rewrite_depth_gate import check_article

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text("{}", encoding="utf-8")
            (d / "drafts").mkdir()
            body = "<p>" + ("слово " * 80) + "</p>"
            (d / "drafts" / "writer.html").write_text(body, encoding="utf-8")
            (d / "article.html").write_text(body, encoding="utf-8")
            report = check_article(d)
            self.assertEqual(report["status"], "PASS", report)
            self.assertTrue(report["metrics"].get("skipped"))

    def test_community_cta_single_link(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_community_cta_gate import check_html

        html = '<p><a href="https://t.me/maya_pro">Ковчег</a></p>'
        self.assertEqual(check_html(html), [])
        self.assertEqual(
            check_html('<p><a href="https://max.ru/maya_pro?utm_source=article">MAX</a></p>'),
            [],
        )
        self.assertEqual(
            check_html('<p><a href="https://kv-ai.ru/obuchenie-po-make">Обучение</a></p>'),
            [],
        )
        self.assertTrue(check_html(html + html))
        self.assertTrue(check_html('<p>без CTA</p>'))
        self.assertTrue(check_html('<a href="https://t.me/kovcheg_ai">x</a>'))

    def test_grok_bot_live_fixture_passes_gates(self) -> None:
        """Real channel export (Grok Bot) fixed per canon must pass both gates."""
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_gemini_materialize import materialize
        from excalibur_blog_gemini_article_gate import check_article

        fixture = ROOT / "tests/fixtures/gemini-article-grok-bot.json"
        self.assertTrue(fixture.is_file(), "Grok Bot live-format fixture missing")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            # The historical fixture used a three-link CTA; current articles use one.
            data["BODY"] = data["BODY"].replace(
                ' — там же <a href="https://max.ru/maya_pro">зеркало в MAX</a>, а собрать своего агента помогают на <a href="https://kv-ai.ru/obuchenie-po-make">обучении Cursor+Make+AI</a>',
                '',
            )
            (d / "gemini-article.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(materialize(d, data)["status"], "PASS")
            gate = check_article(d)
            self.assertEqual(gate["status"], "PASS", gate)
            self.assertGreaterEqual(gate["body_visible_chars"], 2500)
            self.assertLessEqual(gate["body_visible_chars"], 6500)

    def test_cover_generator_decision_documented(self) -> None:
        doc = (ROOT / "shared/cover-generator-decision.md").read_text(encoding="utf-8")
        self.assertIn("Nano Banana Pro", doc)
        self.assertIn("cursor.com/changelog/2-4", doc)
        self.assertIn("не определяет генератор", doc)
        self.assertIn("KIE_API_KEY", doc)
        # Kie is the ONLY cover generator; GenerateImage documented but unused.
        self.assertIn("только Kie GPT Image 2", doc)
        self.assertIn("не** используем", doc)
        # Cover skill must reference the decision doc.
        skill = (ROOT / "skills/cover-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("cover-generator-decision.md", skill)
        self.assertIn("COVER BLOCKER", skill)
        contract = (ROOT / "shared/blog-cover-sunburst-comic-contract.md").read_text(encoding="utf-8")
        self.assertIn("cover-generator-decision.md", contract)
        self.assertIn("cover-mascot.png", contract)
        self.assertFalse((ROOT / "shared/blog-cover-black-canvas-contract.md").exists())

    def test_all_text_roles_on_gemini(self) -> None:
        canon = json.loads((ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8"))
        roles = canon["text_roles_model"]
        self.assertEqual(roles["writer"], "gemini-3.8-flash")
        self.assertNotIn("title", roles)
        self.assertNotIn("description", roles)
        self.assertNotIn("cover_text", roles)
        text = (ROOT / "agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        self.assertIn("model: gemini-3.8-flash", text)
        cloud_agent = (ROOT / ".cursor/agents/excalibur-blog-writer.md").read_text(encoding="utf-8")
        self.assertIn("model: gemini-3.8-flash", cloud_agent)
        writer_skill = (ROOT / "skills/writer-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Модель **`gemini-3.8-flash`**", writer_skill)
        self.assertIn("model=gemini-3.8-flash-high", writer_skill)
        for gone in ("title", "description", "cover-text"):
            self.assertFalse((ROOT / f"agents/excalibur-blog-{gone}.md").exists(), gone)
        # Director and other non-text roles pin standard-speed Grok.
        director = (ROOT / "agents/excalibur-blog-director.md").read_text(encoding="utf-8")
        self.assertIn("model: grok-4.7-medium", director)
        self.assertIn("model=grok-4.7-medium", director)
        # Per-agent model mechanics documented.
        doc = (ROOT / "shared/per-agent-models.md").read_text(encoding="utf-8")
        self.assertIn("customSubagents", doc)
        self.assertIn("cursor.com/docs/subagents", doc)
        cloud = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("per-agent-models.md", cloud)

    def test_alt_texts_must_be_russian(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_gemini_article_gate import check_article

        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "gemini-article.json").write_text(
                json.dumps(
                    {
                        "TITLE": "Grok Bot",
                        "COVER_LINE1": "Grok Bot",
                        "COVER_LINE2": "шесть ролей",
                        "COVER_PROMPT": "x" * 60,
                        "COVER_ALT": "English only alt text",
                        "BODY": "<p>short</p>",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (d / "article.html").write_text("<p>short</p>", encoding="utf-8")
            gate = check_article(d)
            self.assertEqual(gate["status"], "FAIL")
            self.assertTrue(any("COVER_ALT" in e for e in gate["errors"]))

    def test_parallel_steps_documented(self) -> None:
        d = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("параллельно", d.casefold())
        self.assertIn("‖", d)
        cloud = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("ПАРАЛЛЕЛЬНО", cloud)

    def test_figures_carry_russian_figcaption_for_dzen(self) -> None:
        """Dzen renders content:encoded as-is: visible caption needs <figcaption>."""
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        from excalibur_blog_inline_fact_card import inject_inline_figures
        from excalibur_blog_cover_black_apply import inject_cover_first

        html = inject_inline_figures(
            "<h2>Цифры</h2><p>текст</p>",
            [{"slot": "inline_1", "src": "cover/inline-01.png", "alt": "Три факта о боте", "after_h2_index": 0}],
        )
        self.assertIn("<figcaption>Три факта о боте</figcaption>", html)
        html2 = inject_cover_first("<p>лид</p>", alt="Обложка про Grok Bot")
        self.assertIn("<figcaption>Обложка про Grok Bot</figcaption>", html2)
        self.assertTrue(html2.lstrip().startswith("<figure"))
        from excalibur_blog_cover_black_apply import strip_cover_figure

        stripped = strip_cover_figure(html2)
        self.assertNotIn('data-slot="cover"', stripped)
        self.assertIn("<p>лид</p>", stripped)
        contract = (ROOT / "shared/excalibur-wp-publish-contract.md").read_text(encoding="utf-8")
        self.assertIn("figcaption", contract)
        self.assertIn("enclosure", contract)


if __name__ == "__main__":
    unittest.main()
