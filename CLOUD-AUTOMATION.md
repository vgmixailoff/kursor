# Excalibur BLOG — Cloud Automation

Единственный источник правды для **Cursor Automations UI**.

## Как должно работать (HARD)

```text
ОДИН запуск Automation = ОДИН cloud-агент (Директор / оркестратор).
Субагентные РОЛИ (Scout, Research, Gemini/Writer, Schema, Cover, Inline Visuals, …)
— Task(excalibur-blog-*) В ТОМ ЖЕ ране, тот же checkout.
Так Writer получает Gemini 3.8 Flash.

ЗАПРЕЩЕНЫ /in-cloud и Task(..., environment=cloud) —
это ОТДЕЛЬНЫЙ VM (в UI Trigger=Subagent каждые 1–4 мин → взрыв токенов).
```

Плагин (`.cursor-plugin` + `agents/` + `skills/`) задаёт **роли**.
Директор **обязан** вызвать `Task` на каждую роль. Сам BODY не пишет.
Цепочка одна. Запуск один. Готово.

**Модель ролей, кроме Writer:** Grok 4.7 Medium, Fast выключен.
Frontmatter: `grok-4.7-medium`.
В Task: `model=grok-4.7-medium`. Поле не опускать и не ставить `inherit`:
пустой слот платформа подменяет на FAST, а `inherit` копирует родителя.
Голый `grok-4.7` в Cloud — это High + Fast. Writer остаётся на Gemini.

**Модель самого Директора задаётся отдельно в настройке Automation → Model:**
Grok 4.7, effort Medium, Fast выключен. Поле `model` в файле агента и
параметры `Task` меняют только субагентов; они не переключают уже сохранённую
Automation. Изменение этого файла в GitHub тоже не меняет её настройку в UI.

Тестовый прогон может быть в любой час. Слот берётся из `СЛОТ=` в промпте
(или cron), не из времени на часах.

## Канон ролей (gemini-evening-v1)

```text
Scout? → research_start → Research
→ Gemini (gemini-article.json: TITLE+DESCRIPTION+BODY+COVER+INLINE)
→ materialize + gemini_article_gate
→ Schema || Cover (отдельная обложка)
→ Inline Visuals (официальные скрины и схемы в BODY)
→ Indexer → Publish → Content-learner → Fixer? → merge → titles → purge
```

- Gemini → `gemini-article.json` + `article.html` (весь русский текст)
- Sol **выключен** (не переписывать финал)
- DESCRIPTION в том же JSON Writer → `description-brief.json`
- Cover → одна Kie GPT Image 2.5 Sunburst i2i (строки из Writer JSON)
- Inline Visuals → скрины и, если нужна, одна AI-схема на белом фоне
- После publish: titles 30d + `memory_purge.py --drop-topic`

См. `AGENTS.md`, `shared/pipeline-canon.json`, `shared/HOW-WE-SHIP.md`,
`shared/cloud-cost-rules.md`, `shared/cursor-subagents.md`,
`shared/subagent-memory-contract.md`.

## Расписание (Europe/Moscow) — как у живого канала

Три запуска в сутки — **не** `@daily` в полночь. Канон cron в UTC:

```text
0 3,9,15 * * *
```

| Cron (UTC) | MSK | Слот | Тип выпуска |
|------------|-----|------|-------------|
| `0 3` | **06:00** | viral-06 | **вирал** — ViralDzen → своя статья |
| `0 9` | **12:00** | news-12 | **новость** дня (AI/агенты) |
| `0 15` | **18:00** | news-18 | **новость** (≠ теме 12:00) |

Один выпуск на слот. X/Twitter читается через X MCP tools
(`search_news` / `search_posts_all` / `get_trends_by_woeid`) — без браузера;
в статье X/тред/автор не упоминаются. Утро — вирал
(`shared/morning-viral-slot.md` + skill `viraldzen-collect`).
Кейс из X (`case-14`) — только ручной прогон с `СЛОТ=case-14`, не в cron.
Публикация только WP/сайт.

Если Cursor Automations UI хранит cron в UTC — ставь `0 3,9,15 * * *`.
Если UI в локали MSK — `0 6,12,18 * * *`.
Директор берёт `СЛОТ` из cron-триггера: UTC 3→viral-06, 9→news-12, 15→news-18.

## Automation prompt

Скопируй **целиком** в Agent Instructions. Не «Запусти плагин».

Для **утреннего** Automation добавь первой строкой:
`СЛОТ=viral-06` и читай `shared/morning-viral-slot.md` + `skills/viraldzen-collect`.
Для дневных cron: `СЛОТ=news-12` / `news-18` — Scout берёт сигнал через X MCP
(`search_news`), без браузера. Ручной кейс: `СЛОТ=case-14` + `search_posts_all`.

```text
Ты Директор Excalibur BLOG — ОРКЕСТРАТОР одного cloud-запуска.

HARD — Cloud Automation:
- ОБЯЗАТЕЛЬНО вызывать Task(excalibur-blog-*) на каждую роль (scout, research, writer, schema, cover, inline-visuals, indexer, publish, fixer?, learner).
- Единственный Gemini: Writer, model=gemini-3.8-flash-high. Не вызывать Title / Description / Cover-text.
- Все остальные Task: model=grok-4.7-medium (Grok 4.7 Medium, Fast выключен). Поле model не опускать и не ставить inherit: пустой слот платформа меняет на FAST, inherit копирует HiFast родителя. Slug с -fast запрещён.
- ЗАПРЕЩЕНО Task(..., environment=cloud), /in-cloud, /autopilot, Task(excalibur-blog-director).
- Isolation / worktree роли запрещены — общая память = файлы одного checkout (shared/subagent-memory-contract.md).
- Одна статья на этот run. Не стартовать вторую тему.
- Не читать весь memory/blog, llms-full.txt, чужие article.html, live-сайт.
- Игнорируй Automation Memory со старым swarm (Voice/Thesis/Critic/…) и старым Writer→Sol и старым баном «вообще без Task».
- Модель текста для людей: один Writer gemini-3.8-flash — TITLE, DESCRIPTION, BODY, COVER_LINE*, alt, INLINE*. Живой русский для взрослого новичка на «вы»; структура и ритм под конкретные факты, без обязательных цитат и одинакового шаблона. TITLE: Writer применяет `skills/dzen-loud-headlines/SKILL.md`; BODY: `skills/dzen-article-writing/SKILL.md` внутри **того же** Task. Искомое имя в TITLE ПЕРВЫМ («Cursor MCP: …»), затем сильный конфликт и личная ставка из фактов, без пустого кликбейта, эмодзи и «пошаговая инструкция». Один CTA в середине с одной уместной ссылкой из разрешённых. Sol/Тележенька НЕ переписывают финал.
- Картинки: Cover делает только отдельную обложку. Inline Visuals отдельно выбирает скрин или одну схему/таблицу в BODY для взрослого новичка; белый фон, чёрная графика от руки. Не выдумывать цифры.
- Публикация только через WP-скрипт сайта. Не Студия Дзена. Не VC.ru.

Прочитай целиком:
- AGENTS.md
- shared/cloud-cost-rules.md
- shared/subagent-memory-contract.md
- skills/director-excalibur-blog/SKILL.md

Не загружай в контекст Директора целиком `CLOUD-AUTOMATION.md` (этот
промпт уже передан), `shared/HOW-WE-SHIP.md` (памятка человеку),
`shared/cursor-subagents.md` и контракты Writer/Cover/Inline Visuals.
Каждая роль сама читает только свои контракты. `shared/pipeline-canon.json`
проверяют скрипты; при конкретной ошибке открой нужный раздел файла.

Preflight (один раз, Директор сам):
python3 scripts/excalibur_blog_doctor.py
python3 scripts/excalibur_blog_today.py

До Scout создай заново `.cursor/excalibur-blog-handoff.md` с датой и
текущим `СЛОТ`; удали фрагменты предыдущего выпуска из
`.cursor/excalibur-blog-fragments/`. Эти runtime-файлы не берутся из git,
поэтому старый выпуск не может стать контекстом нового.

До Scout — целиком:
shared/dzen-content-rules.md + shared/rf-blocked-entities.json

Пайплайн (Директор оркестрирует Task, не делает роли сам):
0) Если СЛОТ=viral-06 — Task(scout) с ViralDzen collect, выбрать карточку по теме канала + виральности, без упоминания исходника дальше
1) Scout? — Task(excalibur-blog-scout) (10/18 = новости, 14 = кейс)
2) research_start --topic-id … --title "…"
3) Research — Task(excalibur-blog-research) (факты; official_screenshot_urls)
4) Gemini — Task(excalibur-blog-writer, model=gemini-3.8-flash-high)
   → gemini-article.json сразу в файл (TITLE/DESCRIPTION/BODY/COVER_*/INLINE_*)
   TITLE — по skills/dzen-loud-headlines/SKILL.md; BODY — по skills/dzen-article-writing/SKILL.md внутри одного Writer; отдельных авторов нет.
   Длину считает только python3 scripts/excalibur_blog_body_len.py --article-dir …
   Ориентир 3000–6000; лишь мимо 2500–6500 — правка одного-двух абзацев, не больше 3 раз.
   Запрещено вставлять статью в Python (calibrate, test_precise, test_target).
   python3 scripts/excalibur_blog_gemini_materialize.py --article-dir …
   python3 scripts/excalibur_blog_gemini_article_gate.py --article-dir …
   FAIL → Writer точечно исправляет исходный JSON в этом Task; при техническом обрыве resume того же Writer, Директор фразы не правит
5) shell: pipeline_canon --stamp + html_linter
   (gemini_article_gate уже после Writer; opening_meta / sol_rewrite — не звать)
6) Schema ‖ Cover ПАРАЛЛЕЛЬНО Task; Cover Sunburst i2i (одна генерация,
   TITLE + маскот, не COVER_PROMPT), только featured image. Cover-text агента
   нет — строки из Writer JSON. Cover не меняет article.html.
   python3 scripts/excalibur_blog_cover_sunburst_i2i.py …
   python3 scripts/excalibur_blog_kie_gpt_image2_api.py --batch cover/t2i-batch.json --model gpt-image-2-5-sunburst-image-to-image …
   python3 scripts/excalibur_blog_cover_black_apply.py --article-dir …
6b) Inline Visuals — Task(excalibur-blog-inline-visuals) после завершения
    Schema ‖ Cover: проверенные скрины у нужного абзаца; если механизму
    нужна схема, выбрать один из process/comparison/table/stats/
    relationships/decision и сгенерировать максимум одну. Ошибки букв
    или цифр → локальная точная схема без второго платного вызова.
7) Indexer — Task, mode titles+current; Publish — Task (WP)
8) Content-learner — Task после PASS Publish, до очистки article_dir.
9) Fixer только если rg '^status: open' memory/pipeline-fix-queue.md (не пример из шаблона)
10) merge_to_main в **origin/main этого git** (не GitHub PR, не open_git_pr)
    python3 scripts/excalibur_blog_merge_to_main.py
11) python3 scripts/excalibur_blog_published_titles.py --days 30
    python3 scripts/excalibur_blog_memory_purge.py --drop-topic <ID>

Секреты только из Cloud Secrets. Не печатай ключи.
```

## UI checklist

| Поле | Значение |
|---|---|
| Status | Inactive → один Test run → Active |
| Agent Instructions | блок **Automation prompt** выше (+ строка СЛОТ=) |
| Automation Memory | короткий канон gemini-evening-v1; без swarm / без Sol-rewrite |
| Cron | `0 3,9,15 * * *` (UTC) = 06 / 12 / 18 MSK |
| Model | **Для самой Automation / Директора:** Grok 4.7, Medium, Fast выключен. Это поле нужно изменить в каждой действующей Automation; модели ролей заданы отдельно (`shared/per-agent-models.md`) |
| Repo | `vgmixailoff/kursor` / `main` |

Per-agent модели: механика и расклад — `shared/per-agent-models.md`.
Frontmatter `model: gemini-3.8-flash` стоит у Writer. Остальные роли — `grok-4.7-medium` и Task `model=grok-4.7-medium`.

Security review / Agent approval для этого репо — **OFF**.

## Builds

Cloud [Builds](https://cursor.com/docs/cloud-agent/builds) / `.cursor/environment.json`
готовят **один** snapshot на запуск. Они не заменяют запрет `/in-cloud`.
Нужен warm/reuse build — ок; обычный `Task` в том же ране — нужен.

В snapshot/requirements: `viraldzen` из GitHub (`requirements.txt`).
