# Cover generator decision (31.08.2026, доказательно)

## Вопрос

Может ли выбранная в Cursor модель (Gemini 3.8 Flash) **сама** генерировать
обложку «своей» image-моделью (Nano Banana)?

## Ответ: нет (по официальной документации)

Генерация изображений в Cursor — **отдельный встроенный инструмент**
(`image_generator` / `GenerateImage`), чей бэкенд — фиксированная
image-модель. Выбор chat-модели агента не определяет генератор картинок.

Доказательства (официальные источники Cursor):

1. **docs/agent/overview** — агент = Instructions + **Tools** + **Model**;
   «Image generation» перечислена в разделе **Tools**, не Model.
   https://cursor.com/docs/agent/overview
2. **Changelog 2.4 (22.01.2026)**: «Describe the image in text or upload a
   reference to guide **the underlying image generation model
   (Google Nano Banana Pro)**» — единый бэкенд для всех моделей.
   https://cursor.com/changelog/2-4
3. **docs/models/gemini-3-8-flash**: «Gemini 3.8 Flash has access to
   **all agent tools**» — идентичная фраза у Claude Sonnet 5. Т.е. инструмент
   одинаков для всех chat-моделей, не «привязан» к Gemini.
4. **Cursor forum (staff, deanrie)**: «The image generation tool really isn't
   passing size or aspect ratio parameters to the provider, so the result is
   the **Gemini default** (1K, 16:9 = 1376×768)» — бэкенд фиксированный.
   https://forum.cursor.com/t/image-generation-only-has-fixed-resolution/152764
5. **docs/cloud-agent**: Cloud Agents используют те же agent fundamentals +
   MCP + внешние API через секреты VM. Встроенный image-инструмент в
   cloud-доках явно не описан.

## Живой тест в этой сессии (31.08.2026)

Сессионная модель — **не** Gemini (kimi-k3). `GenerateImage` с каноном
чёрного холста отработал: сцена из тьмы снизу, рукописный белый текст
«Claude Code / семь правил» и «Grok Bot / шесть ролей в одном боте» —
без розовой ленты, без UI. Это доказывает: инструмент доступен **любой**
модели агента, а не только Gemini.

Ограничения встроенного инструмента:
- реальный выход ≈1536×1024 (≈3:2) при запрошенном 16:9 — соотношение
  сторон не гарантировано (подтверждает цитату staff про фикс. 1376×768);
- официальный логотип продукта справа рисуется **неточно** (выдуманный знак);
- нет гарантии наличия инструмента в каждом Cloud-run.

## Канон для Cover-агента

Генератор обложки — **только Kie GPT Image 2** (как и было в контуре):

```text
KIE_API_KEY → scripts/excalibur_blog_kie_gpt_image2_api.py
(batch cover/t2i-batch.json, model gpt-image-2-5-sunburst-image-to-image,
1K 16:9, mascot cover-mascot.png via File Upload)
— единственный путь: гарантированный 16:9, async polling, retry-политика.
Нет KIE_API_KEY → COVER BLOCKER (не рисовать PIL-заглушку, не MCP-обход).
```

Встроенный Cursor `GenerateImage` (Nano Banana Pro) — **не** используем:
нет гарантированного 16:9 (реальный выход ≈3:2), неточный логотип продукта,
нет гарантии наличия инструмента в Cloud-run. Он остаётся доказательством
того, что image-инструмент не привязан к chat-модели — не более.

**Не путать:** Gemini 3.8 Flash — автор текста (TITLE/BODY/COVER_LINE*/…).
Генератор картинки — Kie GPT Image 2. «Включили Gemini → рисует
Nano Banana» — неверно.

Логотип продукта на обложке: сеть рисует по имени из промпта; точный
официальный логотип надёжнее класть из `research` (официальный asset) —
см. `shared/article-images-contract.md`.
