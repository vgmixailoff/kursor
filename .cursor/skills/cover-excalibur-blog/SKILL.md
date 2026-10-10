---
name: cover-excalibur-blog
description: "④ Cover: ONE GPT Image 2.5 Sunburst i2i comic + official screens + diagrams."
---

# Cover — только отдельная обложка

Читай `shared/blog-cover-sunburst-comic-contract.md`. Команды Kie ниже
достаточны для обычного запуска; `shared/kie-gpt-image-api-contract.md`
открывай только при ошибке API или неясном ответе генератора.

Обложка — featured image сайта и RSS для Дзена. **Не вставляй её в BODY**
и не трогай `article.html`. Официальные скрины и схемы внутри статьи делает
отдельный `excalibur-blog-inline-visuals`. Читатель — взрослый новичок;
визуальная метафора должна быть понятной без знания агентов и токенов.

## Обложка (одна billed-генерация)

Генератор — **только Kie GPT Image 2.5 Sunburst**
(`shared/cover-generator-decision.md`; встроенный GenerateImage не используем).

Gemini **не** пишет Kie-промпт и **не** вызывается повторно. TITLE и
COVER_LINE* уже в `gemini-article.json` / `cover/cover-text.json` после
Writer materialize. Вставляй TITLE в `shared/cover-sunburst-comic-prompt.txt`.
Референс маскота — `memory/cover/assets/cover-mascot.png`. Не вызывай
агентов Title / Description / Cover-text.

```bash
python3 scripts/excalibur_blog_cover_sunburst_i2i.py --article-dir <dir>
python3 scripts/excalibur_blog_kie_gpt_image2_api.py \
  --article-dir <dir> \
  --batch cover/t2i-batch.json \
  --result cover/t2i-result.json \
  --model gpt-image-2-5-sunburst-image-to-image
python3 scripts/excalibur_blog_cover_black_apply.py --article-dir <dir>
```

Нет `KIE_API_KEY` → COVER BLOCKER.

Не вызывай `cover_black_prompt.py` для новых выпусков.

`cover.png` — featured image. В теле обложку не дублируй.

Запрещено на обложке: розовая лента, quad collage, бейдж t.me,
ноутбуки/UI, letterbox-планка, PIL/Playfair буквы, печать TITLE на кадре.

## Legacy

`cover_black_prompt.py` / чёрный холст Караваджо — не для новых выпусков.
`quad-mcp-batch` / pink collage — тоже нет.

## Kie

При `KIE_API_KEY` — только async Kie script. Одна createTask на обложку.
Не жечь 3–4 попытки «на красоту».

```text
=== EXCALIBUR BLOG COVER ===
canon: sunburst_i2i
output: cover/cover.png (featured image only)
```
