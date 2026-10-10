---
name: scout-excalibur-blog
description: Slot topics — viral (ViralDzen), news, case via X MCP — never invented series.
---

# Scout — тема по слоту

## Слоты (Europe/Moscow)

| Слот | Тип | Источник |
|------|-----|----------|
| 06:00 | **вирал** | ViralDzen (`shared/morning-viral-slot.md`), без браузера Дзена |
| 12:00 | **новость** | свежее событие дня про AI/агентов/инструменты (cron `0 9` UTC) |
| 14:00 | **кейс** | кейс агентских систем из X — **только ручной** `СЛОТ=case-14` |
| 18:00 | **новость** | вторая новость дня (cron `0 15` UTC; не повторять 12:00) |

## X / Twitter — как искать (HARD)

X доступен через **X MCP tools** в сессии агента (без браузера, без логина):

- `search_news` — новостные сюжеты (слоты 10/18)
- `search_posts_all` — посты/треды с кейсами (слот 14)
- `get_trends_by_woeid` — тренды как фон

### Что ищем (темы канала)

Ядро — `shared/topic-focus-contract.md` (HARD gate). Живые примеры уже
вышедшего: «xAI выкатил Grok Bot для Cursor Ultra» (B161), «Cursor
/automate собирает триггер из одного предложения» (B164), «Anthropic
показала сговор и саботаж в рое агентов» (B165), «Cloudflare вставила
сайтам WebMCP для агентов» (B154).

Запросы для `search_posts_all` / `search_news` (крути и комбинируй):

- **Агенты и их продукты:** «Grok Bot», «Cursor agent», «Claude Code»,
  «ChatGPT agent», «OpenAI agent», «Gemini agent», «MCP server»
- **Кейсы (слот 14):** «AI agent case», «agent workflow», «built with
  Cursor», «agent automation», «content factory agent» — ищем форму
  «было → собрали → получили» с артефактом (скрин, репо, цифры)
- **Новости (слоты 10/18):** релиз/фича/лимит/прайсинг у продуктов ядра —
  «Cursor», «Claude», «ChatGPT», «Grok», «Make», «n8n», «Cloudflare agents»

Отбор: смысл для канала (агенты/автоматизация) + живой отклик
(лайки/репосты/обсуждение). Не брать абстрактный AI-хайп без применения
и всё из DENY-списка фокус-контракта (PageSpeed, Метрика-цели, Директ,
Вебмастер, SEO-аудит без агента).

Правила:

1. X — **склад сигнала**. В статье **не** упоминать тред, автора, X,
   твиттер. Текст звучит как полностью свой.
2. Кейс из X обязан быть проверен: Research подтверждает механику по
   **официальным** докам, а итог и цифры — по артефакту самого кейса.
   Если подтверждения результата нет, выбери другой кейс или опиши
   только проверенную возможность продукта (без ссылок на X).
3. RF DENY: не вести читателя в X/Instagram/Facebook/LinkedIn/Discord;
   VPN — DENY. Для CTA допустима одна ссылка по теме: Ковчег `t.me/maya_pro`, MAX `max.ru/maya_pro` или обучение `kv-ai.ru/obuchenie-po-make`.

## Wordstat

Максимум **1** вызов `wordstat_get_top_requests` на роль (одна фраза темы).
Если MCP Wordstat недоступен — skip и пиши `WORDSTAT SKIP` / `WORDSTAT PARTIAL`
с причиной. Не multi-turn Wordstat. `totalCount`-only = `WORDSTAT PARTIAL`
с числом.

## Anti-dup

`shared/published-titles.md` ≤30 дней + темы уже вышедшего дня
(новость 18:00 ≠ новость 12:00).

## Handoff

```text
=== EXCALIBUR BLOG SCOUT ===
topic_id: B…
title: <3–8 слов>
slot: viral-06 | news-12 | case-14 | news-18
external_signal: <1 фраза>
signal_urls:
- <url официального источника, не x.com>
signal_accessed: YYYY-MM-DD
wordstat: …
incident_report: none
```

## Жёсткие запреты

- Придумать тему из воздуха / «продолжим серию» из published-titles
- RF DENY heroes (`shared/rf-blocked-entities.json` + dzen-content-rules)
- `t.me/kovcheg_ai` (канала нет)
- `memory/topics/`, SEO-хвосты
- Ссылаться в статье на X/тред/автора сигнала
- Читать уже опубликованные статьи сайта как образец

Директор затем:

```bash
python3 scripts/excalibur_blog_research_start.py --topic-id <ID> --title "<title>"
```
