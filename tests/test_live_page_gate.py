"""Live-page gate accepts legacy and kz-single theme containers."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_live_page_gate import inspect  # noqa: E402


LEGACY = """
<html><head><title>Hello</title>
<link rel="canonical" href="https://example.com/hello/">
<script type="application/ld+json">{"@type":"BlogPosting","url":"https://example.com/hello/"}</script>
</head><body>
<div class="post-thumbnail"><img src="https://example.com/cover.png" alt="Обложка"></div>
<div id="article-content">
<p>Поручать нейросетям крупные задачи.</p>
<img src="https://example.com/inline.png" alt="Схема">
</div>
</body></html>
"""

KZ_SINGLE = """
<html><head><title>Hello</title>
<link rel="canonical" href="https://example.com/hello/">
<script type="application/ld+json">{"@type":"BlogPosting","url":"https://example.com/hello/"}</script>
</head><body>
<div class="kz-single-cover">
  <div class="kz-single-cover__frame">
    <img class="kz-single-cover__img" src="https://example.com/cover.png" alt="Обложка">
  </div>
</div>
<div class="entry-content kz-article-content" itemprop="articleBody" id="kz-article-body">
<p>Поручать нейросетям крупные задачи.</p>
<img src="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==" alt="Схема" data-src="https://example.com/inline.png" class="lazyload">
</div>
</body></html>
"""


class LivePageGateThemeTest(unittest.TestCase):
    def test_legacy_containers(self) -> None:
        errors = inspect(
            LEGACY,
            expected_slug="hello",
            expected_title="Hello",
            body_probe="Поручать нейросетям крупные задачи",
            expected_permalink="https://example.com/hello/",
        )
        self.assertEqual(errors, [])

    def test_kz_single_containers(self) -> None:
        errors = inspect(
            KZ_SINGLE,
            expected_slug="hello",
            expected_title="Hello",
            body_probe="Поручать нейросетям крупные задачи",
            expected_permalink="https://example.com/hello/",
        )
        self.assertEqual(errors, [])

    def test_kz_share_band_author_card_is_not_faq_pair(self) -> None:
        html = """
<html><head><title>Hello</title>
<link rel="canonical" href="https://example.com/hello/">
<script type="application/ld+json">{"@graph":[
  {"@type":"BlogPosting","url":"https://example.com/hello/"},
  {"@type":"FAQPage","mainEntity":[
    {"@type":"Question","name":"Сколько ресурсов расходует связка агентов?",
     "acceptedAnswer":{"@type":"Answer","text":"В режиме планирования команда расходует примерно в семь раз больше токенов."}}
  ]}
]}</script>
</head><body>
<div class="kz-single-cover"><img src="https://example.com/cover.png" alt="Обложка"></div>
<div class="entry-content kz-article-content" id="kz-article-body">
<p>Поручать нейросетям крупные задачи.</p>
<h2>Частые вопросы</h2>
<h3>Сколько ресурсов расходует связка агентов?</h3>
<p>В режиме планирования команда расходует примерно в семь раз больше токенов.</p>
</div>
<!-- Share Block in Body -->
<div class="kz-share-band" id="kz-share-band">
  <span class="kz-share-title">Поделиться статьей:</span>
</div>
<div class="kz-author-card">
  <h3 class="kz-author-card__name">Артур Хорошев</h3>
  <p>CEO Maya AI · Основатель «Ковчег»</p>
</div>
</body></html>
"""
        errors = inspect(
            html,
            expected_slug="hello",
            expected_title="Hello",
            body_probe="Поручать нейросетям крупные задачи",
            expected_permalink="https://example.com/hello/",
        )
        self.assertEqual(errors, [])

    def test_duplicate_cover_in_body_fails(self) -> None:
        html = KZ_SINGLE.replace(
            "<p>Поручать нейросетям крупные задачи.</p>",
            '<figure data-slot="cover"><img src="https://example.com/cover.png" alt="Обложка"></figure>'
            "<p>Поручать нейросетям крупные задачи.</p>",
        )
        errors = inspect(
            html,
            expected_slug="hello",
            expected_title="Hello",
            body_probe="Поручать нейросетям крупные задачи",
            expected_permalink="https://example.com/hello/",
        )
        self.assertTrue(any("cover duplicated" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
