# Topic Focus Contract (HARD)

**Обновлено:** 2026-08-06
**Владелец:** Scout + `scripts/excalibur_blog_topic_focus.py` + `research_start`

Этот контракт — **жёсткий gate**, не «советы». Soft-инструкции Scout уже 4 раза
провалились: пайплайн уходил в PageSpeed / Метрику / Вебмастер / Директ /
индексацию вместо ядра канала. B137 — в Meta (запрещена в РФ) без чтения
полного Дзен-канона.

**До Scout обязательно:** `shared/dzen-content-rules.md` +
`shared/rf-blocked-entities.json`.

## Ядро (ALLOW — новая тема обязана попасть сюда)

Новая тема **обязана** содержать минимум один маркер ядра в title
(проверяется вместе со slug):

- Cursor / вайбкодинг / Composer / Cloud Agents / Automations (Cursor)
- субагенты / `.cursor/rules` / Ruleset / skills / MCP
- AI-агенты, LLM-модели и их продуктовые новости (новая модель, релиз,
  фича), если это про **автоматизацию/контент/агентную работу**, а не
  абстрактный AI-хайп — и **не** продукт из RF DENY (Meta/…)
- лидогенерация / автоворонка на агентах или Make/n8n
- автопостинг / контент-завод **разрешённых** каналов (Telegram, VK, Дзен, MAX)
- сборка сайтов/лендингов через Cursor
- **свежие новости и обзоры дня** из AI/автоматизации — если субъект
  не RF-blocked

## Свежие новости (NEWS REVIEW — разрешено)

Scout может выбрать **новость сегодняшнего дня** (AI, LLM, агенты,
автоматизация, инструменты контента) и написать **обзор**, а не только how-to.

Правила новостной статьи:
1. Сигнал = реальный источник этой недели (`signal_urls` обязателен).
2. Статья — **наш разбор**: что случилось, кому это важно, что делать
   читателю — по-человечески, живым русским (`shared/gemini-article-contract.md`).
3. Полный Дзен-канон (`shared/dzen-content-rules.md`, в т.ч. `rules.html`):
   не «обзор комментариев», не кликбейт, не оценка как факт, источник
   назван конкретно; закон РФ.
4. Не абстрактный AI-пафос без связи с читателем блога.
5. Не каждый день только новости — чередуем с how-to.
6. Субъект новости ∉ `shared/rf-blocked-entities.json` (Meta, Instagram, …).

## Жёсткий запрет (DENY — перекрывает ALLOW)

Запрещены как **самостоятельные** темы блога (даже если в заголовке есть
слово «Cursor»):

| Кластер | Примеры запрета |
|--------|------------------|
| Скорость сайта | PageSpeed, Core Web Vitals, LCP/INP/CLS, «проверить скорость сайта» |
| Счётчики/цели | GA4, Google Analytics, цели Метрики, Вебвизор, UTM-метки |
| Рекламные кабинеты | Яндекс Директ, ретаргетинг Директа, VK Ads как how-to кабинета |
| Индексация/кабинеты поиска | Яндекс Вебмастер «добавить сайт», Google Search Console |
| Чистый SEO-аудит без агента | «скорость загрузки», «индексация сайта» без Cursor-агентного workflow |
| Абстрактный AI-хайп без применения | «новая AGI модель», если читателю нечего с ней делать |
| **RF / Дзен DENY heroes** | Meta, Facebook, Instagram, Threads, Muse Code/Spark, LinkedIn, Twitter/X, Discord, Signal/Viber-how-to, VPN/обход блокировок |

**Исключение уже опубликованных** исторических статей (B91–B99, старый
Instagram-автопостинг, B124 Meta и т.п.) — остаются в ledger как факт.
**Новые** карточки и `research_start` по запрещённым формулировкам —
`TOPIC FOCUS BLOCKER`.

**meta-теги SEO** — не Meta Platforms; DENY не срабатывает на `meta-тег*`.

## Кто проверяет

1. **Директор до Scout:** прочитал `dzen-content-rules.md` + rf-blocked.
2. Scout **до** handoff:
   ```bash
   python3 scripts/excalibur_blog_topic_focus.py --text "<title>"
   python3 scripts/excalibur_blog_scout_helper.py --check-focus "<title>"
   ```
3. `excalibur_blog_scout_helper.py --check-query` автоматически гоняет focus gate.
4. `excalibur_blog_research_start.py --title` — BLOCK до SERP, если off-focus.
5. `excalibur_blog_today.py` — всегда `needs_scout` (пул topics удалён).

## Внешний сигнал (Scout)

Новая тема обязана опираться на **свежий** канал/новостной сигнал этой недели
(`signal_urls` в handoff). Запрещено выбирать тему только как «следующий номер
серии» из `published-titles.md` без внешнего хайпа.

- Fixer **не** удаляет и **не** ослабляет этот контракт / скрипт / Дзен-канон.
- Doctor проверяет наличие `shared/topic-focus-contract.md`,
  `shared/dzen-content-rules.md`, `shared/rf-blocked-entities.json` и
  `scripts/excalibur_blog_topic_focus.py`.
