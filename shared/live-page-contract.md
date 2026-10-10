# Live page contract

Publish считается завершённым только после проверки фактической live-страницы.

## До публикации

`article.meta.json` должен отключать добавляемые темой универсальные блоки:

```json
{
  "theme_blocks": {
    "faq": "skip",
    "quiz": "skip",
    "side_stickers": "skip"
  }
}
```

В статье остаётся ровно один тематический FAQ. Универсальный FAQ, квиз и
боковые стикеры темы не должны дублировать контент.

## После публикации

Publish запускает:

```bash
python3 scripts/excalibur_blog_live_page_gate.py \
  --permalink <permalink> \
  -o <article_dir>/live-page-report.json
```

`live-page-report.json` должен иметь `status: PASS` и подтвердить:

- HTTP 200 и ожидаемый title/body;
- один тематический FAQ, без FAQ темы;
- theme share chrome (`.article-share` / `.kz-share-band` /
  `<!-- Share buttons -->` / `<!-- Share Block in Body -->` / «Поделиться»)
  после последнего FAQ-ответа **не** считается текстом ответа — gate обрезает
  FAQ body до share row (INC-20260720-2036); карточка автора после шаринга
  не FAQ-пара;
- FAQPage JSON-LD parity с visible FAQ использует ту же нормализацию пробелов
  после strip inline `<a>`, что и `schema_gate` (INC-20260720-2028);
- dash parity: WP `wptexturize` может заменить ASCII `--` в HTML на em dash
  (`—` / `&#8212;`), пока FAQPage JSON-LD хранит `--` — gate схлопывает
  em/en dash и `--+` в один `-` (INC-20260721-1655);
- backslash parity: publish bootstrap обязан `wp_slash` post title/content/
  excerpt перед `wp_insert_post`/`wp_update_post` (INC-20260723-1254). Иначе
  literal `\` в Windows paths исчезает из visible FAQ, а FAQPage JSON-LD
  (meta + `wp_slash`) сохраняет → false FAQ mismatch;
- нет theme quiz и side stickers;
- нет дублей CTA/контента;
- cover/inline media доступны, alt честен;
  контейнер тела: `#article-content` или `#kz-article-body` / `.kz-article-content`;
  обложка: `.post-thumbnail` или `.kz-single-cover` (тема kz-single);
- schema и canonical относятся к текущей статье.

FAIL = `LIVE PAGE BLOCKER`: нельзя писать `PIPELINE DONE`, обновлять ledger как
успешно опубликованный или запускать post-run learning как успешный запуск.
