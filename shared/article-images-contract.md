# Article images (evening canon) — cover + useful evidence

Cover делает **только обложку** `cover/cover.png`: featured image в WP и
RSS `enclosure` для Дзена. Inline Visuals отдельно делает картинки **внутри
BODY**. Не добавляй схемы для достижения числа кадров. Обложку в BODY не
вставляй: герой сайта и RSS уже её показывают.

## Обложка (кадр 1)

Kie `gpt-image-2-5-sunburst-image-to-image`, комикс с маскотом.
См. `shared/blog-cover-sunburst-comic-contract.md`.  
Бейдж `t.me/maya_pro` на обложке — **нельзя**. TITLE на кадре не печатать.

```bash
python3 scripts/excalibur_blog_cover_sunburst_i2i.py --article-dir <dir>
python3 scripts/excalibur_blog_kie_gpt_image2_api.py \
  --article-dir <dir> \
  --batch cover/t2i-batch.json \
  --result cover/t2i-result.json \
  --model gpt-image-2-5-sunburst-image-to-image
python3 scripts/excalibur_blog_cover_black_apply.py --article-dir <dir>
```

Одна billed-генерация. Не жечь 3–4 попытки «на красоту».

## A) Официальные скриншоты внутри статьи — Inline Visuals

Если у источника есть таблица, тарифы, метрики, changelog, UI с цифрами —

1. Cloud-агент **сам** открывает браузер (`computerUse` / browser).
2. Идёт на **официальный** URL (справка, блог продукта, доки).
3. Сохраняет настоящий кадр страницы в `cover/official-*.png`.
4. Проверяет, что на PNG виден нужный фрагмент и читаются важные цифры.
   Кадр с окном согласия, ошибкой, меню вместо факта или мелким текстом
   не вставляет; фиксирует причину и использует ссылку либо схему по фактам.
5. Ставит `<figure data-source-url="https://официальный-адрес">` сразу после
   абзаца, который объясняет увиденное. Внутри нужны `<img src="cover/official-*.png"
   alt="...">` и короткий русский `<figcaption>`: что именно видно и при
   необходимости ссылка на официальный источник. Не складывает скрины в конце.

Не сток. Не фейковый интерфейс. Не перерисовывать таблицу с нуля, если
живой кадр есть.

Если схема с английскими подписями — взять кадр как есть и **только**
заменить английский текст на русский (те же иконки, сетка, композиция).
Новых персонажей / likeness с нуля без исходника — нельзя.

В Research зафиксируй `official_screenshot_urls: [...]`.

## B) Свои диаграммы внутри статьи — Inline Visuals

Если скрин не объясняет механизм, Inline Visuals решает, нужна ли одна
рукописная схема. Он выбирает формат (`process`, `comparison`, `table`,
`stats`, `relationships`, `decision`) по проверенным фактам и строкам Writer.
Стиль — `shared/inline-visual-style.md`; точная процедура —
`skills/inline-visuals-excalibur-blog/SKILL.md`. При ошибке AI-надписей
используется локальный рендер без повторной платной генерации:

```bash
python3 scripts/excalibur_blog_inline_visual.py fallback --article-dir <dir>
```

Это **диаграмма** (схема действий, сравнение, таблица или развилка),
не белый слайд с обрезанным абзацем. Текст на картинке = `INLINE*_ONIMAGE`.
Не выдумывать подписи. Не плакат-слоган. Не lifestyle.
Рекламный бейдж на объясняющей схеме не нужен.

## Порядок в HTML

1. featured `cover/cover.png` — отдельно от BODY
2. Официальные скрины рядом с утверждением, которое они подтверждают
3. Схемы / диаграммы только когда проясняют мысль

Каждый `<figure>` несёт `<figcaption>` с русским текстом (= alt) — иначе
Дзен не покажет видимую подпись (alt в RSS не рендерится).

Перед публикацией локальные изображения должны открываться, иметь русский
`alt` и видимую подпись. Для `official-*.png` обязателен `data-source-url`;
публикация останавливается, если файл пропал или подпись отсутствует.
