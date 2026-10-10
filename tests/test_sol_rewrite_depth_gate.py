"""Sol rewrite-depth gate: fail shallow Writer→article copy-paste."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "scripts"))
from excalibur_blog_sol_rewrite_depth_gate import check_article  # noqa: E402
B160 = (
    ROOT
    / "memory/blog/articles/B160-nvidia-pustila-nemotron-lightning-pod-rabochih-agentov"
)


class SolRewriteDepthGateTest(unittest.TestCase):
    def test_script_exists_but_not_in_runtime_chain(self) -> None:
        self.assertTrue(
            (ROOT / "scripts/excalibur_blog_sol_rewrite_depth_gate.py").is_file()
        )
        structure = (ROOT / "scripts/excalibur_blog_structure_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("excalibur_blog_sol_rewrite_depth_gate.py", structure)
        self.assertNotIn("excalibur_blog_opening_meta_gate.py", structure)
        self.assertNotIn("excalibur_blog_gemini_article_gate.py", structure)
        director = (ROOT / "skills/director-excalibur-blog/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("gemini_article_gate", director)
        self.assertIn("Не звать `opening_meta_gate`", director)
        self.assertNotIn(
            "excalibur_blog_opening_meta_gate.py",
            director,
        )
        self.assertNotIn(
            "excalibur_blog_sol_rewrite_depth_gate.py",
            director,
        )
        # Stamp step must not re-run gemini_article_gate.py as a shell command.
        stamp = director.split("### 4 Stamp")[1].split("### 5")[0]
        self.assertNotIn("excalibur_blog_gemini_article_gate.py", stamp)
        canon = json.loads(
            (ROOT / "shared/pipeline-canon.json").read_text(encoding="utf-8")
        )
        self.assertIn("sol_rewrite_depth", canon)
        self.assertEqual(
            canon["sol_rewrite_depth"].get("disabled_when_canon"), "gemini-evening-v1"
        )
        self.assertFalse(canon["sol_rewrite_depth"].get("runtime", True))
        # Sol skill removed under gemini-evening-v1.
        self.assertFalse((ROOT / "skills/sol-excalibur-blog/SKILL.md").exists())

    def test_pass_on_deep_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "drafts").mkdir()
            (d / "drafts" / "writer.html").write_text(
                "<p>Смысл: агент крутится сутками и жрёт дорогую модель на кликах.</p>\n"
                "<h2>Факты</h2>\n"
                "<p><b>Архитектура:</b> 30B MoE, 3B active, NVFP4 endpoint.</p>\n"
                "<p>Партнёр A — минус 58% cost на бенчмарке.</p>\n",
                encoding="utf-8",
            )
            (d / "article.html").write_text(
                "<p>Дорогая модель на круглосуточных кликах — как платить "
                "оркестратору за работу курьера.</p>\n"
                "<h2>Что вышло</h2>\n"
                "<p>Вендор отдал рутину отдельной быстрой open-модели, а выбор "
                "смены — отдельному диспетчеру. Планируешь редко, кликаешь часто.</p>\n"
                "<p>Внутренние проценты экономии — пилоты, не обещание вашему счёту.</p>\n",
                encoding="utf-8",
            )
            (d / "article.meta.json").write_text(
                json.dumps({"h1": "Рутина агента на дешёвой смене"}, ensure_ascii=False),
                encoding="utf-8",
            )
            report = check_article(d)
            self.assertEqual(report["status"], "PASS", report)

    def test_fail_on_near_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "drafts").mkdir()
            body = (
                "<p>Always-on агент живёт не одним умным запросом в час. "
                "Он крутится сутками и жрёт фронтир на рутине.</p>\n"
                "<h2>Два релиза</h2>\n"
                "<p><b>Архитектура:</b> open 30B MoE / 3B active Hybrid Mamba.</p>\n"
                "<p><b>Задача модели:</b> execution layer — tool calls и валидация.</p>\n"
                "<p><b>Установка:</b> uv tool install nemo-switchyard для proxy.</p>\n"
                "<p>Boomi — 100% domain-routing, 59% traffic на faster model.</p>\n"
            )
            (d / "drafts" / "writer.html").write_text(body, encoding="utf-8")
            # Styled lead + mostly same body (B160 pattern).
            article = (
                "<p>Многие люди уверены: круглосуточному агенту нужен один мозг. "
                "Им кажется — одна дорогая модель справится. Точнее, крутится он "
                "не мыслями. Почему никто не хочет дешёвую смену?</p>\n"
                "<h2>Два релиза</h2>\n"
                "<p><b>Архитектура:</b> open 30B MoE / 3B active Hybrid Mamba.</p>\n"
                "<p><b>Задача модели:</b> execution layer — tool calls и валидация.</p>\n"
                "<p><b>Установка:</b> uv tool install nemo-switchyard для proxy.</p>\n"
                "<p>Boomi — 100% domain-routing, 59% traffic на faster model.</p>\n"
            )
            (d / "article.html").write_text(article, encoding="utf-8")
            (d / "article.meta.json").write_text(
                json.dumps({"h1": "NVIDIA Lightning"}, ensure_ascii=False),
                encoding="utf-8",
            )
            report = check_article(d)
            self.assertEqual(report["status"], "BLOCK", report)
            joined = " ".join(report["errors"]).casefold()
            self.assertTrue(
                "verbatim" in joined
                or "jaccard" in joined
                or "label-dump" in joined
                or "formula" in joined,
                report,
            )

    def test_b160_fails_rewrite_depth(self) -> None:
        if not B160.is_dir():
            self.skipTest("B160 artifacts missing")
        report = check_article(B160)
        self.assertEqual(report["status"], "BLOCK", report)
        self.assertGreater(report["metrics"]["verbatim_ratio"], 0.30)


if __name__ == "__main__":
    unittest.main()
