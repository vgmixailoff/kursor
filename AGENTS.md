# Excalibur BLOG Cloud Instructions

Язык: русский.

## Канон (gemini-evening-v1, с 31.08.2026)

```text
Scout? → research_start → Research
→ Gemini(TITLE+DESCRIPTION+BODY+COVER+INLINE JSON) → materialize + gates
→ Cover(отдельная обложка) ‖ Schema → Inline Visuals(скрины/схемы в BODY)
→ Indexer(llms) → Publish(WP) → Content-learner → Fixer? → merge → titles → purge
```

**Gemini 3.8 Flash** (`gemini-3.8-flash`) пишет всё русское для людей
одним Task Writer: TITLE, DESCRIPTION (карточка Дзена), BODY,
COVER_LINE*, COVER_PROMPT/ALT, INLINE*_ONIMAGE/ALT.
Слог: живой русский для взрослого новичка на «вы»; человек ещё не знает
агентские системы и токены, но хочет понять, зачем это нужно. Структура и
ритм зависят от фактов, без канцелярита и обязательных цитат.
BODY: `skills/dzen-article-writing/SKILL.md` — ранний ответ, развитие мысли,
конкретный пример и честные ограничения без одинаковой схемы каждого выпуска.
TITLE: искомое имя (поисковый запрос) ПЕРВЫМ («Cursor MCP: …»),
громкий, подтверждённый фактами конфликт и личная ставка по
`skills/dzen-loud-headlines/SKILL.md`; без эмодзи и «пошаговая инструкция / чек-лист 2026».
Лёгкий SEO/GEO слой: ответ в первом абзаце, question-form в title_aeo.
Один JSON → `gemini-article.json`. Агентов Title / Description / Cover-text **нет**.
Sol/Тележенька/Лебедев **не** переписывают финал. Артур — тема/канал, не слог.

**Research** — склад фактов (англ. ок).
**DESCRIPTION** в том же JSON → `description-brief.json` ≠ title ≠ opening.
**Cover** — одна GPT Image 2.5 Sunburst i2i (Kie, 1K, 16:9): TITLE в
фиксированный комикс-промпт + маскот `cover-mascot.png`. Gemini COVER_PROMPT
в Kie не отправляется.
Картинки: `shared/article-images-contract.md`: Cover только обложка;
Inline Visuals отдельно вставляет официальные скрины и схемы в BODY.

После Writer — stamp `pipeline_canon` + html_linter
(`gemini_article_gate` — один раз сразу после materialize Writer;
opening_meta / sol_rewrite_depth — не в рантайме).

Канал: https://t.me/maya_pro (не kovcheg_ai).  
Дзен: dzen.ru/artur_horosheff. Публикация только через сайт (WP → Дзен).
Не Студия руками. Не VC.ru из этого контура.

**Никто не читает уже опубликованные статьи сайта** — только
`shared/published-titles.md` для anti-dup (заголовки **≤30 дней**).
После publish папка `memory/blog/articles/<topic>/` **удаляется**.

`memory/topics/` запрещена. Scout → handoff + `signal_urls` + Wordstat.
Дневные слоты — **кейсы** агентских систем (было→собрали→получили), не
changelog. Утро 06:00 — вирал через ViralDzen (`shared/morning-viral-slot.md`).

```bash
python3 scripts/excalibur_blog_research_start.py --topic-id B111 --title "…"
```

Человеку: `shared/HOW-WE-SHIP.md`.

## Cloud Automation

**UI prompt / cron / restore:** `CLOUD-AUTOMATION.md`.  
**Cost (HARD):** `shared/cloud-cost-rules.md` — **один** cloud-агент
(Директор) на весь пайплайн. Роли = `Task(excalibur-blog-*)` в том же ране.
`/in-cloud` и `environment=cloud` **запрещены** (отдельный VM).
Writer — `gemini-3.8-flash-high` (единственный текстовый Gemini). Одна статья/run; Fixer только при open
incidents; после publish — titles 30d + purge article_dir.  
Все остальные роли: Task `model=grok-4.7-medium` и frontmatter
`grok-4.7-medium`. Пустой `model` и `inherit` дают High + Fast.
Модель самого Директора выставляется в каждой Automation UI отдельно:
Grok 4.7, Medium, Fast выключен. GitHub-файлы её не переключают.
Не заменять Agent Instructions на «Запусти плагин».

## Субагенты и общая память (HARD)

Директор **только оркестрирует**: `Task(excalibur-blog-*)` в этом ране,
тот же checkout. Сам не пишет BODY и не рисует обложку.

Единственный текстовый агент — Writer (`gemini-3.8-flash` /
Task `gemini-3.8-flash-high`). Title / Description / Cover-text удалены.
Остальные роли — `model=grok-4.7-medium` в Task и
`grok-4.7-medium` во frontmatter.
Пустой `model`, `inherit` и slug с `-fast` запрещены.

Общая память — **файлы**, не чат родителя (субагент стартует с чистого окна):
`shared/subagent-memory-contract.md`, шаблон `shared/subagent-task-prompt.md`.
Правило alwaysApply: `.cursor/rules/excalibur-blog-subagent-memory.mdc`.
Директор создаёт свежий handoff и очищает fragments до Scout; эти файлы
игнорируются git и не служат памятью между выпусками.

Роли **не** запускают вложенный Task. `/in-cloud` запрещён.

## Расписание (Europe/Moscow)

| Слот | Тип |
|------|-----|
| 06:00 | вирал (ViralDzen → своя статья) |
| 12:00 | новость дня |
| 18:00 | новость (≠ 12:00) |

Один выпуск на слот. Cron UTC: `0 3,9,15 * * *` (MSK 06 / 12 / 18), не `@daily` в полночь.
Кейс (`case-14`) — только ручной прогон, не в cron.
X читается через X MCP tools (без браузера); в тексте X не упоминается.

## Ошибка (список ЗАПРЕТОВ — так делать нельзя)

- Второй автор / rewrite-loop **поверх Gemini** (Sol выключен)
- Термин-дамп / research-брифинг в открытии финала
- Description = title или обрезка лида (двойная карточка в Дзене)
- topics / SEO-хвосты
- Writer/Gemini читают старые article.html / live-сайт как образец
- Хранение cover PNG / тел статей после publish (память = только title ≤30д)
- Publish без pipeline_canon stamp
- Scout/тема про Meta, Instagram, Facebook, X, LinkedIn, Discord, VPN —
  **запрещённые** площадки (закон РФ + Дзен), не темы для статей
- Упоминать тред/X/автора сигнала в тексте статьи
- t.me/kovcheg_ai / «Ковчег AI» — **не существует**, запрещено
- Фейковый UI вместо официального скрина
- Широкий обход репо / `/in-cloud` / второй VM на роль
- Второй параллельный пайплайн (Scalable Block = этот же контур)
- VC.ru — эта автоматизация туда **не отправляет**

## Preflight

**До Scout:** прочитать целиком `shared/dzen-content-rules.md` +
`shared/rf-blocked-entities.json` (закон РФ: Meta/Instagram/…; полный Дзен
`rules.html`). Без этого тему не выбирать.

```bash
python3 scripts/excalibur_blog_doctor.py
python3 scripts/excalibur_blog_today.py
python3 scripts/excalibur_blog_research_start.py --topic-id <id> --title "<short>"
```

Директор: `.cursor/agents/excalibur-blog-director.md` (оркестратор;
роли — Task, не сам). Карта: `shared/cursor-subagents.md`.

Хранилище канона — **git `origin/main` этого репо**. Не Cursor `open_git_pr`.
После правок: `python3 scripts/excalibur_blog_merge_to_main.py` (FF в main).
