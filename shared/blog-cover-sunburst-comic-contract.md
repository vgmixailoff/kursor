# Cover — комикс GPT Image 2.5 Sunburst i2i

Канон обложки: **одна** billed-генерация Kie
`gpt-image-2-5-sunburst-image-to-image`, **16:9**, **1K**.

Gemini **не** пишет промпт для Kie. В шаблон подставляется только `TITLE`.

## Вход

1. Заголовок статьи — `--title`, иначе `gemini-article.json` `TITLE`,
   иначе `article.meta.json` `title`.
2. Фиксированный промпт: `shared/cover-sunburst-comic-prompt.txt`
   (`{{ЗАГОЛОВОК_СТАТЬИ}}` → TITLE). Сам заголовок **на картинке не печатать**.
3. Маскот-референс: `memory/cover/assets/cover-mascot.png`
   (чёрный круглый блоб, два овальных глаза). Не розовый динозавр,
   не `maya_pro_avatar.jpg`.

## Команды

```bash
python3 scripts/excalibur_blog_cover_sunburst_i2i.py --article-dir <dir>
python3 scripts/excalibur_blog_kie_gpt_image2_api.py \
  --article-dir <dir> \
  --batch cover/t2i-batch.json \
  --result cover/t2i-result.json \
  --model gpt-image-2-5-sunburst-image-to-image
python3 scripts/excalibur_blog_cover_black_apply.py --article-dir <dir>
```

Batch: `canon: sunburst_i2i`, `prefer_local_reference: true`.
Плейсхолдер `https://unused.invalid/cover-mascot.png` в `input_urls`
нужен только чтобы i2i-схема прошла валидацию; перед createTask скрипт
заливает локальный PNG через Kie File Stream Upload.

Нет `KIE_API_KEY` → COVER BLOCKER (не PIL, не встроенный GenerateImage).

## Кадр

- Горизонтальный editorial-комикс, хук + панч.
- Видимый текст — только русский / кириллица, короткие реплики.
- Бейдж `t.me/maya_pro` на обложке — **нельзя**.
- Нельзя: розовая лента, quad collage, фейковый UI, PIL/Playfair буквы.

Чёрный холст Караваджо (`gpt-image-2-text-to-image`) — **legacy**.
Не собирать `cover_black_prompt.py` для новых выпусков.

Генератор картинки — Kie, не chat-модель: `shared/cover-generator-decision.md`.
